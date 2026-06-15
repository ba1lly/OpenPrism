"""Backend interface + factory.

A backend turns a model reference into a completion. Model references are always
`provider/model`; because some model ids themselves contain slashes
(e.g. opencode's `requesty/xai/grok-4`), we split on the FIRST slash only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelInfo:
    ref: str            # full reference, e.g. "google/gemini-2.5-flash"
    provider: str       # provider id
    model: str          # model id (may contain slashes)
    name: str = ""      # human display name, if known
    connected: bool = True


def split_ref(ref: str, default_provider: str = "") -> tuple[str, str]:
    """`provider/model` -> (provider, model). Bare ref -> (default_provider, ref)."""
    if "/" in ref:
        provider, model = ref.split("/", 1)
        return provider, model
    return default_provider, ref


class Backend(ABC):
    """Async backend. Implementations must be safe to call concurrently."""

    name = "base"

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def complete(
        self, model_ref: str, prompt: str, system: str | None, max_tokens: int,
        tools: dict | None = None,
    ) -> tuple[str, int]:
        """Return (text, total_tokens). Raise on failure — the panel layer
        catches per-model so one failure never sinks the run. `tools` is a
        name->bool map for backends that support tool use (opencode); backends
        that can't (direct raw completions) ignore it."""
        ...

    async def default_panel(self, mode: str) -> list[str]:
        """Models to use when the caller gives no explicit panel. Default: the
        configured preset for `mode`. opencode overrides this dynamically."""
        from .. import config

        return config.resolve_panel(mode if mode in config.PANELS else None)

    async def aclose(self) -> None:
        pass


def get_backend(name: str | None = None) -> Backend:
    """Factory. `name` overrides config.BACKEND."""
    from .. import config

    backend = (name or config.BACKEND).lower()
    if backend == "opencode":
        from .opencode import OpencodeBackend

        return OpencodeBackend()
    if backend == "direct":
        from .direct import DirectBackend

        return DirectBackend()
    raise config.PrismError(f"Unknown OPENPRISM_BACKEND: {backend!r} (use 'direct' or 'opencode').")
