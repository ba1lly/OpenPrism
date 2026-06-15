"""Offline unit tests — no network, no opencode, no model calls.

Covers the pure logic: tool-restriction maps, ref splitting, panel resolution,
init config generation, and that the MCP server registers its tools.
"""
import asyncio
import json
import os

from openprism import config
from openprism.backends.base import split_ref


def test_panel_tools_research_denies_mutation():
    t = config.panel_tools("research")
    assert t["webfetch"] is True and t["websearch"] is True
    for danger in config._MUTATING:  # all of them, not a subset
        assert t[danger] is False, f"{danger} must be denied in research mode"


def test_panel_tools_rejects_unknown_level():
    import pytest

    with pytest.raises(config.PrismError):
        config.panel_tools("reserch")  # typo must error, not silently fall back


def test_resolve_panel_caps_size(monkeypatch):
    import pytest

    monkeypatch.setattr(config, "MAX_PANEL", 3)
    with pytest.raises(config.PrismError):
        config.resolve_panel("a/1,b/2,c/3,d/4")
    # dedup keeps it under the cap
    assert config.resolve_panel("a/1,a/1,b/2") == ["a/1", "b/2"]


def test_panel_tools_none_disables_everything():
    t = config.panel_tools("none")
    assert all(v is False for v in t.values())
    assert "webfetch" in t and "bash" in t


def test_panel_tools_all_is_omitted():
    assert config.panel_tools("all") is None  # None = opencode defaults (all tools)


def test_split_ref_first_slash_only():
    assert split_ref("google/gemini-2.5-flash") == ("google", "gemini-2.5-flash")
    assert split_ref("requesty/xai/grok-4") == ("requesty", "xai/grok-4")
    assert split_ref("qwen3.7-plus", "alibaba") == ("alibaba", "qwen3.7-plus")


def test_resolve_panel_presets_and_csv():
    assert config.resolve_panel("research") == config.PANELS["research"]
    assert config.resolve_panel("a/b, c/d") == ["a/b", "c/d"]
    assert config.resolve_panel(None) == config.PANELS[config.DEFAULT_PANEL]


def test_init_generates_valid_json_for_mcpservers_hosts():
    from openprism import init_cmd

    cmd = init_cmd._launch(local=False)
    assert cmd == ["uvx", "--from", "openprism", "openprism-mcp"]  # PyPI form by default
    block = init_cmd._block("cursor", cmd, {"OPENPRISM_BACKEND": "opencode"})
    data = json.loads(block)
    assert data["mcpServers"]["openprism"]["command"] == "uvx"


def test_init_opencode_block_is_valid_and_typed_local():
    from openprism import init_cmd

    block = init_cmd._block("opencode", ["uvx", "openprism-mcp"], {"OPENPRISM_BACKEND": "opencode"})
    data = json.loads(block)
    entry = data["mcp"]["openprism"]
    assert entry["type"] == "local" and entry["enabled"] is True


def test_init_codex_block_is_toml_like():
    from openprism import init_cmd

    block = init_cmd._block("codex", ["uvx", "openprism-mcp"], {"OPENPRISM_BACKEND": "opencode"})
    assert "[mcp_servers.openprism]" in block and "command = " in block


def test_mcp_server_registers_exactly_four_tools():
    from openprism import mcp_server

    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert names == {"research", "code", "bakeoff", "models"}


def test_model_family_is_maker_not_provider():
    f = config.model_family
    assert f("anthropic/claude-opus-4-7") == "anthropic"
    assert f("requesty/anthropic/claude-haiku") == "anthropic"  # same family, no fake diversity
    assert f("alibaba-coding-plan/glm-5") == "glm"              # GLM family, not "alibaba"
    assert f("alibaba-coding-plan/kimi-k2.5") == "kimi"
    assert f("google/gemini-2.5-flash") == "google"
    assert f("openai/gpt-5.2") == "openai"
    assert f("alibaba-coding-plan/MiniMax-M2.5") == "minimax"


def test_panel_status_full_degraded_stop():
    from openprism.panel import PanelResponse
    from openprism.pipeline import _panel_status

    def ok(model):
        return PanelResponse(model, "ans", True)
    def fail(model):
        return PanelResponse(model, None, False, error="x")

    # two distinct families, all requested ok -> full
    s, fams = _panel_status([ok("anthropic/claude"), ok("google/gemini")], 2)
    assert s == "full" and set(fams) == {"anthropic", "google"}

    # a panelist failed -> degraded (still >= MIN_FAMILIES)
    s, _ = _panel_status([ok("anthropic/claude"), ok("google/gemini"), fail("openai/gpt")], 3)
    assert s == "degraded"

    # only one family answered -> stop (monoculture)
    s, fams = _panel_status([ok("anthropic/claude"), ok("requesty/anthropic/claude-x")], 2)
    assert s == "stop" and fams == ["anthropic"]


# --- pipeline / judge / backend, exercised with fakes (no network) ---
from openprism.backends.base import Backend, ModelInfo  # noqa: E402


class _FakeBackend(Backend):
    name = "fake"

    def __init__(self, answers, fail=()):
        self.answers, self.fail, self.closed, self.tools_seen = answers, set(fail), False, []

    async def list_models(self):
        return [ModelInfo(r, r.split("/")[0], r) for r in self.answers]

    async def complete(self, ref, prompt, system, max_tokens, tools=None):
        self.tools_seen.append(tools)
        if ref in self.fail:
            raise RuntimeError("boom")
        return self.answers[ref], 1

    async def aclose(self):
        self.closed = True


def test_run_async_full_and_closes(monkeypatch):
    import openprism.pipeline as pipeline

    fb = _FakeBackend({"anthropic/claude": "A", "google/gemini": "B"})
    monkeypatch.setattr(pipeline, "get_backend", lambda name=None: fb)

    async def fake_judge(prompt, backend=None):
        return "JUDGED"

    monkeypatch.setattr(pipeline, "judge_async", fake_judge)
    res = asyncio.run(pipeline._run_async("q", "research", "anthropic/claude,google/gemini", None))
    assert res.status == "full" and res.final == "JUDGED"
    assert set(res.families) == {"anthropic", "google"}
    assert fb.closed is True


def test_run_async_degraded_on_partial_failure(monkeypatch):
    import openprism.pipeline as pipeline

    fb = _FakeBackend({"anthropic/claude": "A", "google/gemini": "B", "openai/gpt": "C"},
                      fail={"openai/gpt"})
    monkeypatch.setattr(pipeline, "get_backend", lambda name=None: fb)

    async def fake_judge(prompt, backend=None):
        return "J"

    monkeypatch.setattr(pipeline, "judge_async", fake_judge)
    res = asyncio.run(pipeline._run_async("q", "research",
                                          "anthropic/claude,google/gemini,openai/gpt", None))
    assert res.status == "degraded"


def test_run_async_all_failed_raises(monkeypatch):
    import pytest
    import openprism.pipeline as pipeline

    fb = _FakeBackend({"a/x": "", "b/y": ""})  # empty answers count as failures
    monkeypatch.setattr(pipeline, "get_backend", lambda name=None: fb)
    with pytest.raises(config.PrismError):
        asyncio.run(pipeline._run_async("q", "research", "a/x,b/y", None))


def test_judge_opencode_is_toolless_and_closes_created_backend(monkeypatch):
    import openprism.judge as judge_mod

    rec = {}

    class _JudgeBackend(Backend):
        name = "opencode"

        async def list_models(self):
            return []

        async def complete(self, ref, prompt, system, max_tokens, tools=None):
            rec["tools"], rec["ref"] = tools, ref
            return "VERDICT", 1

        async def aclose(self):
            rec["closed"] = True

    monkeypatch.setattr(judge_mod.config, "JUDGE_BACKEND", "opencode")
    monkeypatch.setattr(judge_mod.config, "JUDGE_MODEL", "anthropic/claude-x")
    monkeypatch.setattr(judge_mod, "get_backend", lambda name=None: _JudgeBackend())

    out = asyncio.run(judge_mod.judge_async("prompt", None))  # creates its own backend
    assert out == "VERDICT"
    assert rec["closed"] is True                      # didn't leak it (adj_5)
    assert all(v is False for v in rec["tools"].values())  # ran tool-less (adj_1)


def test_direct_backend_raises_on_no_choices(monkeypatch):
    import pytest
    from openprism.backends import direct

    class _Completions:
        async def create(self, **kw):
            class _R:
                choices = []
            return _R()

    class _FakeOpenAI:
        def __init__(self, **kw):
            self.chat = type("C", (), {"completions": _Completions()})()

        async def close(self):
            pass

    monkeypatch.setattr(direct, "AsyncOpenAI", _FakeOpenAI)
    monkeypatch.setattr(config, "ALIBABA_API_KEY", "test-key")
    b = direct.DirectBackend()
    with pytest.raises(RuntimeError):
        asyncio.run(b.complete("alibaba/x", "p", None, 10))


def test_doctor_never_prints_a_key(monkeypatch, capsys):
    from openprism import doctor

    monkeypatch.setattr(config, "BACKEND", "direct")
    monkeypatch.setattr(config, "ALIBABA_API_KEY", "sk-SECRET-DO-NOT-PRINT")
    monkeypatch.setattr(config, "JUDGE_BACKEND", "claude-code")
    doctor.run_doctor()
    assert "sk-SECRET-DO-NOT-PRINT" not in capsys.readouterr().out


def test_opencode_backend_builds_basic_auth(monkeypatch):
    from openprism.backends import opencode as oc

    monkeypatch.setattr(oc.OpencodeBackend, "_ensure_server", lambda self: None)
    monkeypatch.setattr(config, "OPENCODE_PASSWORD", "pw")
    assert oc.OpencodeBackend()._auth == ("opencode", "pw")
    monkeypatch.setattr(config, "OPENCODE_PASSWORD", "")
    assert oc.OpencodeBackend()._auth is None


def test_claude_judge_argv_is_list_and_restricts_tools(monkeypatch):
    import openprism.judge as judge_mod

    captured = {}

    class _Proc:
        returncode, stdout, stderr = 0, "VERDICT", ""

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(judge_mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(judge_mod.config, "JUDGE_MODEL", "opus")
    out = judge_mod._judge_claude_code("prompt")
    assert out == "VERDICT"
    assert isinstance(captured["cmd"], list)
    assert "--disallowedTools" in captured["cmd"]


def test_judge_unknown_backend_raises(monkeypatch):
    import pytest
    import openprism.judge as judge_mod

    monkeypatch.setattr(judge_mod.config, "JUDGE_BACKEND", "typo-backend")
    with pytest.raises(config.PrismError):
        asyncio.run(judge_mod.judge_async("p", None))


import pytest  # noqa: E402


@pytest.mark.skipif(os.getenv("OPENPRISM_LIVE") != "1",
                    reason="live: needs a running opencode server + model spend (set OPENPRISM_LIVE=1)")
def test_live_mcp_handshake():
    import importlib.util
    import pathlib

    p = pathlib.Path(__file__).parent / "smoke_mcp.py"
    spec = importlib.util.spec_from_file_location("smoke_mcp", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    asyncio.run(mod.main(False))
