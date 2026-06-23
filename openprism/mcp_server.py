"""Prism MCP server (stdio) — the shared core for the Claude Code plugin and the
opencode integration. Exposes the panel+judge pipeline as MCP tools so any
MCP-speaking host gets `research` / `code` / `bakeoff` alongside its built-ins.

Tool names are deliberately short ("research", "code", "bakeoff"); hosts namespace
them by server name, so they surface as `mcp__openprism__research` (Claude Code) and
`openprism_research` (opencode).

Run directly:  python -m openprism.mcp_server   (or the `openprism-mcp` console script)
"""
import asyncio

from mcp.server.fastmcp import FastMCP

from .backends import get_backend
from .pipeline import PrismResult, bakeoff as _bakeoff, run as _run

mcp = FastMCP("openprism")


def _render(result: PrismResult) -> str:
    banner = ""
    if result.status != "full":
        banner = f"!! {result.status_line()}\n\n"
    return (
        f"[openprism {result.mode} | judge={result.judge_backend} | {result.status_line()}]\n"
        f"{result.panel_summary()}\n\n"
        f"{banner}{result.final}"
    )


@mcp.tool()
async def research(question: str, panel: str = "") -> str:
    """Run a diverse multi-model panel and return a judge-synthesized answer.

    Use for HARD, open-ended problems where being right matters more than speed:
    deep research, architecture/design trade-offs, ambiguous judgement calls,
    "tear this plan apart". Not worth it for quick lookups or routine work
    (it costs ~slowest-model + judge latency).

    Args:
        question: the problem to answer.
        panel: a preset name (research | research-lean | code) or a
               comma-separated list of model refs (provider/model). Empty = the
               OPENPRISM_PANEL default if set, else the backend's default panel
               (Alibaba 4-house for direct; a diverse
               auto-pick across connected providers for opencode).
    """
    result = await asyncio.to_thread(_run, question, "research", panel or None)
    return _render(result)


@mcp.tool()
async def code(task: str, panel: str = "") -> str:
    """Run a multi-model coding panel; the judge does best-of-N selection +
    repair into one runnable solution (code is verifiable, so it picks/fixes a
    winner rather than blending). Returns the solution plus a "Verify by:" line.

    Args:
        task: the coding task.
        panel: comma-separated model refs, or empty for the OPENPRISM_PANEL
               default if set, else the backend's default coder panel.
    """
    result = await asyncio.to_thread(_run, task, "code", panel or None)
    return _render(result)


@mcp.tool()
async def bakeoff(question: str, model_a: str, model_b: str) -> str:
    """Compare two models on the same prompt; the judge blind-picks the winner.
    Use to decide which model earns a panel seat (e.g. qwen3.7-plus vs
    qwen3-max-2026-01-23).

    Args:
        question: the test prompt to run on both models.
        model_a: first model id.
        model_b: second model id.
    """
    verdict, responses = await asyncio.to_thread(_bakeoff, question, model_a, model_b)
    lines = [f"[openprism bakeoff | {model_a} vs {model_b}]"]
    for r in responses:
        lines.append(f"  {r.model:<22} {r.latency:.1f}s" if r.ok else f"  {r.model}: {r.error}")
    return "\n".join(lines) + "\n\n" + verdict


@mcp.tool()
async def models() -> str:
    """List the models available to the current backend as `provider/model` refs.

    For the opencode backend this is the live catalogue of everything you've
    configured/authed in opencode (connected providers first). Use any of these
    refs in the `panel` argument of research/code or as a/b in bakeoff.
    """
    def _list():
        async def go():
            backend = get_backend()
            try:
                return await backend.list_models(), backend.name
            finally:
                await backend.aclose()

        return asyncio.run(go())

    infos, backend_name = await asyncio.to_thread(_list)
    connected = [m for m in infos if m.connected]
    other = [m for m in infos if not m.connected]
    lines = [f"[backend={backend_name}] {len(infos)} models"]
    if connected:
        lines.append("\nConnected:")
        lines += [f"  {m.ref}" + (f"  ({m.name})" if m.name else "") for m in connected]
    if other:
        lines.append(f"\nConfigured but not connected ({len(other)}):")
        lines += [f"  {m.ref}" for m in other[:60]]
    return "\n".join(lines)


def main() -> None:
    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
