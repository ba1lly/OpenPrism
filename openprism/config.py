"""Central configuration: backends, providers, presets, judge.

Two backends (see openprism.backends):
  - direct   : Prism's own OpenAI-compatible providers (keys here / providers.json)
  - opencode : piggyback on a running opencode server (all its providers/models)
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Load .env from the repo root by ABSOLUTE path — the MCP server is launched from
# arbitrary cwds, so a cwd-relative load would silently miss the key.
_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:  # dotenv optional at runtime if env is set another way
    pass


class PrismError(RuntimeError):
    """User-facing config/runtime problem. Caught by the CLI (printed cleanly) and
    surfaced as a tool error by the MCP server — never a bare SystemExit, which
    would kill a host's MCP connection."""


# --- Backend selection ---
# opencode is the recommended default: every provider/model you've authed in
# opencode, no keys here. Set 'direct' to use your own provider keys instead.
BACKEND = os.getenv("OPENPRISM_BACKEND", "opencode").lower()  # opencode | direct

# --- Direct backend: providers ---
ALIBABA_API_KEY = os.getenv("ALIBABA_API_KEY", "")
ALIBABA_BASE_URL = os.getenv(
    "ALIBABA_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_PROVIDER = os.getenv("OPENPRISM_DEFAULT_PROVIDER", "alibaba")


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    models: list[str] = field(default_factory=list)


def load_providers() -> dict[str, "Provider"]:
    """Default Alibaba provider from .env, plus any in providers.json at repo root.

    providers.json: {"<id>": {"base_url": "...", "api_key": "env:VAR" | "sk-...",
    "models": ["..."]}}. `env:VAR` reads the key from the environment.
    """
    providers: dict[str, Provider] = {}
    if ALIBABA_API_KEY:
        providers["alibaba"] = Provider("alibaba", ALIBABA_BASE_URL, ALIBABA_API_KEY, KNOWN_MODELS)
    pj = _ROOT / "providers.json"
    if pj.exists():
        try:
            raw = json.loads(pj.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise PrismError(f"providers.json is not valid JSON: {e}") from e
        if not isinstance(raw, dict):
            raise PrismError("providers.json must be a JSON object of {provider: {...}}.")
        for pid, cfg in raw.items():
            if pid.startswith("_") or not isinstance(cfg, dict):
                continue  # skip comment/doc keys like "_comment"
            if "base_url" not in cfg:
                raise PrismError(f"providers.json: '{pid}' is missing required 'base_url'.")
            key = cfg.get("api_key", "")
            if key.startswith("env:"):
                env_name = key[4:]
                key = os.getenv(env_name, "")
                if not key:
                    import sys

                    print(f"openprism: providers.json '{pid}' wants ${env_name} but it is unset",
                          file=sys.stderr)
            providers[pid] = Provider(pid, cfg["base_url"], key, cfg.get("models", []))
    return providers


# --- opencode backend ---
OPENCODE_URL = os.getenv(
    "OPENPRISM_OPENCODE_URL", f"http://127.0.0.1:{os.getenv('OPENPRISM_OPENCODE_PORT', '4096')}"
)
OPENCODE_PASSWORD = os.getenv("OPENCODE_SERVER_PASSWORD", "")
OPENCODE_AUTOSERVE = os.getenv("OPENPRISM_OPENCODE_AUTOSERVE", "1") not in ("0", "false", "False", "")

# --- Judge ---
JUDGE_BACKEND = os.getenv("OPENPRISM_JUDGE_BACKEND", "claude-code")  # claude-code | anthropic-api | opencode
JUDGE_MODEL = os.getenv("OPENPRISM_JUDGE_MODEL", "opus")  # claude-code: alias; opencode: provider/model
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Tuning ---
def _int_env(name: str, default: int) -> int:
    """Parse an int env var without letting a typo crash import (which would take
    down the whole CLI / MCP server with a bare ValueError)."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        import sys

        print(f"openprism: {name}={raw!r} is not an integer; using {default}", file=sys.stderr)
        return default


PANEL_TIMEOUT = _int_env("OPENPRISM_PANEL_TIMEOUT", 300)
MAX_TOKENS = _int_env("OPENPRISM_MAX_TOKENS", 8000)
# Hard cap on panel size — one MCP call must not fan out to hundreds of paid calls.
MAX_PANEL = _int_env("OPENPRISM_MAX_PANEL", 8)

# --- Diversity / degradation ---
# The lift comes from DIVERSE model FAMILIES, not raw count. If fewer than this
# many distinct families answer, the run is labelled "stop" (loudly degraded) —
# we never silently present a monoculture as a confident panel result.
MIN_FAMILIES = _int_env("OPENPRISM_MIN_FAMILIES", 2)
# Strict mode turns a "stop" into a hard refusal instead of a labelled answer.
STRICT = os.getenv("OPENPRISM_STRICT", "0") in ("1", "true", "True")

# Map a model ref -> its model FAMILY (the maker), not the serving provider — so
# `alibaba-coding-plan/glm-5` is the GLM family, and `requesty/anthropic/claude-*`
# and `anthropic/claude-*` collapse to one family (no fake diversity).
_FAMILY_KEYWORDS = [
    ("claude", "anthropic"), ("anthropic", "anthropic"),
    ("gpt", "openai"), ("codex", "openai"), ("o1", "openai"), ("o3", "openai"),
    ("o4", "openai"), ("openai", "openai"),
    ("gemini", "google"), ("gemma", "google"), ("google", "google"),
    ("qwen", "qwen"),
    ("glm", "glm"), ("zhipu", "glm"), ("z-ai", "glm"), ("zai", "glm"),
    ("kimi", "kimi"), ("moonshot", "kimi"),
    ("minimax", "minimax"),
    ("deepseek", "deepseek"),
    ("grok", "xai"), ("xai", "xai"),
    ("mistral", "mistral"), ("codestral", "mistral"), ("ministral", "mistral"),
    ("devstral", "mistral"), ("pixtral", "mistral"),
    ("llama", "meta"),
    ("nemotron", "nvidia"),
]


def model_family(ref: str) -> str:
    full = ref.lower()
    # Prefer the model id (last path segment) so a provider name can't hijack the
    # family — e.g. "deepseek-host/llama-3" is the llama family, not deepseek.
    model_id = full.rsplit("/", 1)[-1]
    for scope in (model_id, full):
        for kw, fam in _FAMILY_KEYWORDS:
            if kw in scope:
                return fam
    return full.split("/", 1)[0]  # fallback: serving provider id

# --- Panel tools (opencode backend only) ---
# opencode panelists have ALL tools on by default — including bash/edit/write,
# unsafe for parallel agents on your machine. So we restrict explicitly.
#   research -> web + read-only (webfetch/websearch/read/grep/glob/list); mutation denied  [default]
#   none     -> pure completions, no tools (cheapest, model knowledge only)
#   all      -> opencode defaults = every tool incl. bash/edit/write  (OPT-IN, dangerous)
PANEL_TOOLS = os.getenv("OPENPRISM_PANEL_TOOLS", "research").lower()

_MUTATING = ("write", "edit", "apply_patch", "bash", "task", "todowrite")
_READABLE = ("webfetch", "websearch", "read", "grep", "glob", "list")
_ALL_TOOL_NAMES = _READABLE + _MUTATING + ("todoread", "lsp", "skill")
_RESEARCH_TOOLS = {**{t: True for t in _READABLE}, **{t: False for t in _MUTATING}}
_NO_TOOLS = {t: False for t in _ALL_TOOL_NAMES}


_TOOL_LEVELS = ("research", "none", "all")


def panel_tools(level: str | None = None) -> dict | None:
    """Tool map for panelists. None = omit (opencode defaults / all tools)."""
    level = (level or PANEL_TOOLS).lower()
    if level not in _TOOL_LEVELS:
        raise PrismError(
            f"OPENPRISM_PANEL_TOOLS={level!r} is invalid — use one of {_TOOL_LEVELS}."
        )
    if level == "all":
        return None
    if level == "none":
        return dict(_NO_TOOLS)
    return dict(_RESEARCH_TOOLS)


# --- Panel presets (direct/Alibaba bare ids; for opencode use provider/model refs) ---
PANELS = {
    "research": ["qwen3.7-plus", "glm-5", "kimi-k2.5", "MiniMax-M2.5"],
    "research-lean": ["qwen3.7-plus", "glm-5", "kimi-k2.5"],
    "code": ["qwen3-coder-plus", "qwen3-coder-next", "glm-5"],
}
DEFAULT_PANEL = "research"

# Optional default-panel override. When set (and no per-call panel is passed),
# research/code use it instead of the backend's auto-picked diverse panel. A
# preset name, or a comma-separated list of model refs (opencode: provider/model):
#   OPENPRISM_PANEL=google/gemini-2.5-pro,openai/gpt-5.4,anthropic/claude-sonnet-4-6
PANEL_OVERRIDE = os.getenv("OPENPRISM_PANEL", "").strip()

KNOWN_MODELS = [
    "qwen3.7-plus", "qwen3.6-plus", "qwen3.5-plus",
    "qwen3-max-2026-01-23", "qwen3-coder-next", "qwen3-coder-plus",
    "glm-5", "glm-4.7", "kimi-k2.5", "MiniMax-M2.5",
]


def resolve_panel(spec: str | None) -> list[str]:
    """A preset name, or a comma-separated list of model refs. De-duplicated and
    capped at MAX_PANEL so a single call can't fan out unbounded."""
    if not spec:
        return PANELS[DEFAULT_PANEL]
    if spec in PANELS:
        return PANELS[spec]
    seen: set[str] = set()
    models = []
    for m in (x.strip() for x in spec.split(",")):
        if m and m not in seen:
            seen.add(m)
            models.append(m)
    if len(models) > MAX_PANEL:
        raise PrismError(
            f"Panel has {len(models)} models; cap is {MAX_PANEL} "
            f"(raise OPENPRISM_MAX_PANEL if you really mean it)."
        )
    return models
