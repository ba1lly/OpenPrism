"""DirectBackend — Prism's own OpenAI-compatible providers.

Providers come from config.load_providers() (the Alibaba Coding Plan from .env by
default, plus anything in providers.json). Used by Claude Code and the CLI, which
have no host provider registry to borrow. A bare model id (no slash) resolves to
the default provider, preserving the original single-provider behaviour.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from .. import config
from .base import Backend, ModelInfo, split_ref


class DirectBackend(Backend):
    name = "direct"

    def __init__(self) -> None:
        self.providers = config.load_providers()
        if not self.providers:
            raise config.PrismError(
                "No providers configured. Set ALIBABA_API_KEY in .env (or add "
                "providers.json), or use OPENPRISM_BACKEND=opencode."
            )
        self.default_provider = config.DEFAULT_PROVIDER or next(iter(self.providers))
        if self.default_provider not in self.providers:
            import sys

            fallback = next(iter(self.providers))
            print(f"openprism: OPENPRISM_DEFAULT_PROVIDER={self.default_provider!r} is not "
                  f"configured; using {fallback!r} for bare model ids", file=sys.stderr)
            self.default_provider = fallback
        self._clients: dict[str, AsyncOpenAI] = {}

    def _client(self, provider_id: str) -> AsyncOpenAI:
        if provider_id not in self.providers:
            raise config.PrismError(
                f"Provider {provider_id!r} not configured. Known: {list(self.providers)}"
            )
        if provider_id not in self._clients:
            p = self.providers[provider_id]
            self._clients[provider_id] = AsyncOpenAI(api_key=p.api_key, base_url=p.base_url)
        return self._clients[provider_id]

    async def list_models(self) -> list[ModelInfo]:
        out: list[ModelInfo] = []
        for pid, p in self.providers.items():
            for m in p.models:
                ref = m if pid == self.default_provider else f"{pid}/{m}"
                out.append(ModelInfo(ref=ref, provider=pid, model=m))
        return out

    async def complete(
        self, model_ref: str, prompt: str, system: str | None, max_tokens: int,
        tools: dict | None = None,
    ) -> tuple[str, int]:
        # `tools` is ignored: direct providers are plain completions. Panelist tool
        # use (web/fetch) requires the opencode backend.
        provider_id, model = split_ref(model_ref, self.default_provider)
        client = self._client(provider_id)
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        resp = await client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens
        )
        if not getattr(resp, "choices", None):
            raise RuntimeError(f"{model}: provider returned no choices")
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        tokens = getattr(usage, "total_tokens", 0) if usage else 0
        return text, tokens

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.close()
