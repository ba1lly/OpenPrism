"""`openprism doctor` — diagnose a setup without printing secrets.

Checks Python, the launcher, the configured backend (providers/keys or a
reachable opencode server), and the judge. Exits non-zero if anything is broken.
"""
from __future__ import annotations

import shutil
import sys

from . import config

OK, WARN, FAIL = "[ok]  ", "[warn]", "[FAIL]"


def _opencode_reachable() -> bool:
    try:
        import httpx

        auth = ("opencode", config.OPENCODE_PASSWORD) if config.OPENCODE_PASSWORD else None
        with httpx.Client(base_url=config.OPENCODE_URL, timeout=2.0, auth=auth) as c:
            return c.get("/provider").status_code == 200
    except Exception:  # noqa: BLE001
        return False


def run_doctor(_args=None) -> int:
    lines: list[tuple[str, str]] = []

    # Python
    py_ok = sys.version_info >= (3, 10)
    lines.append((OK if py_ok else FAIL,
                  f"Python {sys.version_info.major}.{sys.version_info.minor} "
                  f"({'>=3.10' if py_ok else 'need >=3.10'})"))

    # Launcher
    lines.append((OK if shutil.which("uvx") else WARN,
                  "uvx on PATH" if shutil.which("uvx") else "uvx not found (needed for the uvx install path)"))

    # Backend
    backend = config.BACKEND
    lines.append((OK, f"backend = {backend}"))
    if backend == "opencode":
        from .backends.opencode import _find_opencode

        exe = _find_opencode()
        lines.append((OK if exe else FAIL,
                      f"opencode binary: {exe}" if exe else "opencode binary NOT found (install it or set OPENPRISM_OPENCODE_URL)"))
        if _opencode_reachable():
            lines.append((OK, f"opencode server reachable at {config.OPENCODE_URL}"))
        elif config.OPENCODE_AUTOSERVE and exe:
            lines.append((WARN, f"no server at {config.OPENCODE_URL} — will autospawn `opencode serve` on first use"))
        else:
            lines.append((FAIL, f"no opencode server at {config.OPENCODE_URL} and autoserve off/unavailable"))
    elif backend == "direct":
        provs = config.load_providers()
        if not provs:
            lines.append((FAIL, "no providers configured (set ALIBABA_API_KEY or add providers.json)"))
        for pid, p in provs.items():
            lines.append((OK if p.api_key else FAIL,
                          f"provider '{pid}': key {'set' if p.api_key else 'MISSING'}, {len(p.models)} models"))
    else:
        lines.append((FAIL, f"unknown backend {backend!r} (use direct | opencode)"))

    # Judge
    jb = config.JUDGE_BACKEND
    lines.append((OK, f"judge backend = {jb}, model = {config.JUDGE_MODEL}"))
    if jb == "claude-code":
        lines.append((OK if shutil.which("claude") else FAIL,
                      "claude CLI on PATH" if shutil.which("claude") else "claude CLI NOT found (judge will fail)"))
    elif jb == "anthropic-api":
        lines.append((OK if config.ANTHROPIC_API_KEY else FAIL,
                      "ANTHROPIC_API_KEY set" if config.ANTHROPIC_API_KEY else "ANTHROPIC_API_KEY MISSING"))
    elif jb == "opencode":
        ok = "/" in config.JUDGE_MODEL
        lines.append((OK if ok else FAIL,
                      "judge model is a provider/model ref" if ok else
                      f"OPENPRISM_JUDGE_MODEL={config.JUDGE_MODEL!r} must be provider/model for opencode judge"))

    lines.append((OK, f"panel tools = {config.PANEL_TOOLS}"))

    print("OpenPrism doctor\n" + "-" * 40)
    for tag, msg in lines:
        print(f"  {tag} {msg}")
    failed = sum(1 for tag, _ in lines if tag == FAIL)
    print("-" * 40)
    print("All good." if not failed else f"{failed} problem(s) — see [FAIL] above.")
    return 1 if failed else 0
