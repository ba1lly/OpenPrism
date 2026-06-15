"""Judge backends:
  - claude-code   : `claude -p` headless (flat-rate Max plan)            [default]
  - anthropic-api : Anthropic API (metered, raw endpoint)
  - opencode      : route the judge through the opencode server too (OPENPRISM_JUDGE_MODEL
                    must be a provider/model ref, e.g. anthropic/claude-opus-4-7)

`judge_async` is the entry point. The blocking backends run in a worker thread so
they don't block the panel's event loop.
"""
import asyncio
import subprocess

from . import config
from .backends import Backend, get_backend


async def judge_async(prompt: str, panel_backend: Backend | None = None) -> str:
    jb = config.JUDGE_BACKEND
    if jb == "opencode":
        ref = config.JUDGE_MODEL
        if "/" not in ref:
            raise config.PrismError(
                "OPENPRISM_JUDGE_BACKEND=opencode needs OPENPRISM_JUDGE_MODEL as a provider/model "
                f"ref (e.g. anthropic/claude-opus-4-7), got {ref!r}."
            )
        reuse = bool(panel_backend and panel_backend.name == "opencode")
        backend = panel_backend if reuse else get_backend("opencode")
        try:
            # The judge synthesises untrusted panel text — give it NO tools so a
            # prompt injection in a panel answer can't pivot it into bash/edit/web.
            text, _ = await backend.complete(ref, prompt, None, config.MAX_TOKENS,
                                             tools=config.panel_tools("none"))
        finally:
            if not reuse:  # don't leak a backend we created just for the judge
                await backend.aclose()
        return text.strip()
    if jb == "anthropic-api":
        return await asyncio.to_thread(_judge_anthropic, prompt)
    if jb == "claude-code":
        return await asyncio.to_thread(_judge_claude_code, prompt)
    raise config.PrismError(
        f"Unknown OPENPRISM_JUDGE_BACKEND: {jb!r} (use claude-code | anthropic-api | opencode)."
    )


def _judge_claude_code(prompt: str) -> str:
    # The judge only emits text. Deny side-effecting tools so a prompt injection
    # in untrusted panel output can't pivot `claude -p` into running commands.
    cmd = ["claude", "-p", "--model", config.JUDGE_MODEL,
           "--disallowedTools", "Bash Edit Write WebFetch WebSearch"]
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
            timeout=config.PANEL_TIMEOUT,
        )
    except FileNotFoundError as e:
        raise config.PrismError(
            "`claude` CLI not found on PATH. Install Claude Code or set "
            "OPENPRISM_JUDGE_BACKEND=anthropic-api / opencode."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise config.PrismError(f"`claude -p` judge timed out after {config.PANEL_TIMEOUT}s.") from e
    if proc.returncode != 0:
        raise config.PrismError(f"`claude -p` failed (exit {proc.returncode}): {(proc.stderr or '').strip()}")
    out = (proc.stdout or "").strip()
    if not out:
        raise config.PrismError("`claude -p` returned empty output.")
    return out


def _judge_anthropic(prompt: str) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise config.PrismError("OPENPRISM_JUDGE_BACKEND=anthropic-api but ANTHROPIC_API_KEY is not set.")
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    model = "claude-opus-4-8" if config.JUDGE_MODEL == "opus" else config.JUDGE_MODEL
    msg = client.messages.create(
        model=model, max_tokens=config.MAX_TOKENS, messages=[{"role": "user", "content": prompt}]
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
