"""Parallel panel dispatch — backend-agnostic.

Each panelist is one `backend.complete(model, ...)` call. They run concurrently
(asyncio.gather), so wall-clock ≈ slowest panelist, not the sum. A failing
panelist degrades to ok=False and never sinks the run.
"""
import asyncio
import time
from dataclasses import dataclass

from . import config
from .backends import Backend


@dataclass
class PanelResponse:
    model: str
    text: str | None
    ok: bool
    error: str | None = None
    latency: float = 0.0
    tokens: int = 0


async def _ask_one(
    backend: Backend, model: str, prompt: str, system: str | None, tools: dict | None
) -> PanelResponse:
    start = time.monotonic()
    try:
        text, tokens = await asyncio.wait_for(
            backend.complete(model, prompt, system, config.MAX_TOKENS, tools=tools),
            timeout=config.PANEL_TIMEOUT,
        )
        if not (text and text.strip()):
            # An empty answer is a failed panelist, not a silent valid voice.
            return PanelResponse(model, None, False, error="empty response",
                                 latency=time.monotonic() - start, tokens=tokens)
        return PanelResponse(model, text, True, latency=time.monotonic() - start, tokens=tokens)
    except Exception as e:  # noqa: BLE001 — one model failing must not kill the panel
        return PanelResponse(model, None, False, error=str(e), latency=time.monotonic() - start)


async def run_panel(
    backend: Backend, prompt: str, models: list[str], system: str | None = None,
    tools: dict | None = None,
) -> list[PanelResponse]:
    results = await asyncio.gather(*[_ask_one(backend, m, prompt, system, tools) for m in models])
    return list(results)
