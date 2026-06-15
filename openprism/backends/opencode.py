"""OpencodeBackend — piggyback on opencode's provider layer.

Talks to a local opencode HTTP server. Every provider/model the user has
configured/authed in opencode is available, discovered live from `/provider` —
NO hardcoded providers or models. opencode does all auth; Prism never sees keys.

Server resolution:
  1. OPENPRISM_OPENCODE_URL if set.
  2. otherwise http://127.0.0.1:<OPENPRISM_OPENCODE_PORT or 4096>; if nothing is
     listening there and autoserve is on (default), spawn `opencode serve` and
     wait for it — reusing the user's existing auth.json.

A completion = POST /session then POST /session/:id/message with tools disabled,
which returns a clean (non-agentic) model answer. Each panelist gets its own
session so panelists never see each other's context.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

import httpx

from .. import config
from .base import Backend, ModelInfo, split_ref


def _find_opencode() -> str | None:
    """Locate the opencode binary. The MCP server is launched by a host with a
    minimal PATH that often misses bun/npm shims, so check common install dirs."""
    exe = shutil.which("opencode")
    if exe:
        return exe
    candidates = [
        "~/.opencode/bin/opencode", "~/.bun/bin/opencode", "~/.local/bin/opencode",
        "/usr/local/bin/opencode", "/opt/homebrew/bin/opencode",
    ]
    for c in candidates:
        p = os.path.expanduser(c)
        if os.path.exists(p):
            return p
    return None


# A server we spawn ourselves is shared across backend instances (the MCP server
# builds a fresh backend per tool call) and torn down once at process exit — so we
# don't spawn/kill a server on every call or leak orphans.
_SHARED_SERVER: subprocess.Popen | None = None
_SPAWN_LOCK = threading.Lock()


def _shutdown_shared_server() -> None:
    global _SHARED_SERVER
    if _SHARED_SERVER is not None:
        _SHARED_SERVER.terminate()
        try:
            _SHARED_SERVER.wait(timeout=5)
        except Exception:  # noqa: BLE001
            _SHARED_SERVER.kill()
        _SHARED_SERVER = None


atexit.register(_shutdown_shared_server)


class OpencodeBackend(Backend):
    name = "opencode"

    def __init__(self) -> None:
        self.base_url = config.OPENCODE_URL.rstrip("/")
        scheme = urlsplit(self.base_url).scheme
        if scheme not in ("http", "https"):
            raise config.PrismError(
                f"OPENPRISM_OPENCODE_URL must be http(s), got {self.base_url!r}."
            )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(config.PANEL_TIMEOUT, connect=10.0),
            auth=(("opencode", config.OPENCODE_PASSWORD) if config.OPENCODE_PASSWORD else None),
        )
        self._ensure_server()

    @property
    def _auth(self):
        return ("opencode", config.OPENCODE_PASSWORD) if config.OPENCODE_PASSWORD else None

    # --- server lifecycle ---
    def _reachable(self) -> bool:
        try:
            with httpx.Client(base_url=self.base_url, timeout=2.0, auth=self._auth) as c:
                return c.get("/provider").status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def _ensure_server(self) -> None:
        # Use an already-running server (the user's TUI/serve, or one we spawned
        # earlier this process) if reachable at the configured URL.
        if self._reachable():
            return
        if not config.OPENCODE_AUTOSERVE:
            raise config.PrismError(
                f"No opencode server reachable at {self.base_url} and autoserve is off. "
                "Start `opencode serve` or set OPENPRISM_OPENCODE_URL."
            )
        global _SHARED_SERVER
        port = urlsplit(self.base_url).port
        if not port:
            raise config.PrismError(
                f"Can't derive a port from OPENPRISM_OPENCODE_URL={self.base_url!r} to autospawn; "
                "set OPENPRISM_OPENCODE_PORT or point at a running server."
            )
        exe = _find_opencode()
        if not exe:
            raise config.PrismError(
                "`opencode` binary not found (checked PATH, ~/.opencode/bin, ~/.bun/bin, "
                "etc.) — install opencode or set OPENPRISM_OPENCODE_URL to a running server."
            )
        # Serialise the check-then-spawn so concurrent backends don't race to start
        # two servers on the same port.
        with _SPAWN_LOCK:
            if self._reachable():  # another thread may have started it
                return
            # Capture stderr so a startup failure (port clash, bad argv, crash) has
            # a diagnostic instead of vanishing into DEVNULL.
            log = tempfile.NamedTemporaryFile(
                prefix="openprism-opencode-", suffix=".log", mode="w+", delete=False
            )
            # Spawn once per process; persists for reuse, cleaned up at exit.
            _SHARED_SERVER = subprocess.Popen(
                [exe, "serve", "--port", str(port)],
                stdout=subprocess.DEVNULL, stderr=log,
            )
            for _ in range(40):  # ~20s
                if self._reachable():
                    return
                time.sleep(0.5)
        try:
            log.flush()
            log.seek(0)
            tail = log.read()[-800:].strip()
        except Exception:  # noqa: BLE001
            tail = ""
        raise config.PrismError(
            f"Spawned `opencode serve` but it never came up on {self.base_url}."
            + (f"\n--- opencode stderr ---\n{tail}" if tail else "")
        )

    # --- Backend interface ---
    async def list_models(self) -> list[ModelInfo]:
        r = await self._client.get("/provider")
        r.raise_for_status()
        data = r.json()
        connected = set(data.get("connected", []))
        out: list[ModelInfo] = []
        for p in data.get("all", []):
            pid = p["id"]
            for mid, m in (p.get("models") or {}).items():
                out.append(ModelInfo(
                    ref=f"{pid}/{mid}", provider=pid, model=mid,
                    name=(m or {}).get("name", ""), connected=pid in connected,
                ))
        return out

    # Model id/name substrings that mark a non-chat model (skip in auto panels).
    _NON_CHAT = (
        "embed", "embedding", "rerank", "whisper", "tts", "image", "video",
        "ocr", "guard", "moderation",
    )

    async def default_panel(self, mode: str) -> list[str]:
        """Pick a diverse default: one chat model from each of up to 4 distinct
        model FAMILIES (not just providers) — so the panel is genuinely diverse,
        never two models from the same family. The user normally specifies their own."""
        models = [m for m in await self.list_models() if m.connected]

        def is_chat(m: ModelInfo) -> bool:
            s = f"{m.model} {m.name}".lower()
            return not any(k in s for k in self._NON_CHAT)

        picked: list[str] = []
        seen_families: set[str] = set()
        for m in models:
            if not is_chat(m):
                continue
            fam = config.model_family(m.ref)
            if fam in seen_families:
                continue
            seen_families.add(fam)
            picked.append(m.ref)
            if len(picked) >= 4:
                break
        if not picked:
            raise config.PrismError(
                "No connected chat models in opencode to build a default panel — "
                "specify a panel of provider/model refs."
            )
        return picked

    async def complete(
        self, model_ref: str, prompt: str, system: str | None, max_tokens: int,
        tools: dict | None = None,
    ) -> tuple[str, int]:
        provider_id, model = split_ref(model_ref)
        if not provider_id:
            raise config.PrismError(
                f"opencode model ref must be 'provider/model', got {model_ref!r}."
            )
        sess = await self._client.post("/session", json={"title": "openprism"})
        sess.raise_for_status()
        sid = sess.json().get("id")
        if not sid:
            raise RuntimeError(f"opencode/{model_ref}: session create returned no id ({sess.text[:200]})")
        # opencode enables ALL tools by default; `tools` is an explicit name->bool
        # allow/deny map. None = omit = opencode defaults (every tool). The panel
        # layer passes a restricted map (web + read-only) so panelists can browse
        # but cannot run bash/edit/write. Each panelist gets its own session.
        body = {
            "model": {"providerID": provider_id, "modelID": model},
            "parts": [{"type": "text", "text": prompt}],
        }
        if tools is not None:
            body["tools"] = tools
        if system:
            body["system"] = system
        try:
            r = await self._client.post(f"/session/{sid}/message", json=body)
            r.raise_for_status()
            d = r.json()
        finally:
            # Don't litter the user's opencode history with a session per panelist.
            try:
                await self._client.delete(f"/session/{sid}")
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
        info = d.get("info", {})
        err = info.get("error")
        if err:
            msg = (err.get("data") or {}).get("message") or err.get("name") or "unknown error"
            raise RuntimeError(f"opencode/{model_ref}: {msg}")
        text = "".join(
            p.get("text", "") for p in d.get("parts", []) if p.get("type") == "text"
        ).strip()
        tokens = (info.get("tokens") or {}).get("total", 0)
        return text, tokens

    async def aclose(self) -> None:
        # Only close this instance's HTTP client. Any server we spawned is shared
        # and lives until process exit (see _shutdown_shared_server / atexit).
        await self._client.aclose()
