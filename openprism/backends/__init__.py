"""Model backends — where Prism's panel calls actually go.

- DirectBackend: Prism's own OpenAI-compatible providers (keys in .env / providers.json).
  Used by Claude Code and the standalone CLI, which have no provider registry to borrow.
- OpencodeBackend: piggybacks on a running opencode server — every provider/model the
  user has configured/authed in opencode, with zero hardcoding. Used in opencode.
"""
from .base import Backend, ModelInfo, get_backend

__all__ = ["Backend", "ModelInfo", "get_backend"]
