"""Orchestration: run the panel on a backend, then the judge. Plus a bake-off
helper for deciding which model earns a panel seat.
"""
import asyncio
from dataclasses import dataclass, field

from . import config, prompts
from .backends import Backend, get_backend
from .config import PrismError
from .judge import judge_async
from .panel import PanelResponse, run_panel


@dataclass
class PrismResult:
    question: str
    mode: str
    panel: list[PanelResponse]
    final: str
    judge_backend: str = field(default="")
    panel_backend: str = field(default="")
    status: str = field(default="full")        # full | degraded | stop
    families: list[str] = field(default_factory=list)

    @property
    def ok_panelists(self) -> list[PanelResponse]:
        return [r for r in self.panel if r.ok and r.text]

    def status_line(self) -> str:
        fam = ", ".join(self.families)
        if self.status == "full":
            return f"diversity: full ({len(self.families)} families: {fam})"
        if self.status == "degraded":
            return f"DIVERSITY DEGRADED ({len(self.families)} families: {fam}) — some panelists failed; treat with care"
        return f"DIVERSITY STOP — only {len(self.families)} family answered ({fam}); this is effectively a single-model answer, NOT a diverse panel"

    def panel_summary(self) -> str:
        lines = []
        for r in self.panel:
            if r.ok:
                fam = config.model_family(r.model)
                lines.append(f"  [ok]   {r.model:<28} {fam:<10} {r.latency:6.1f}s  {r.tokens or '?'} tok")
            else:
                lines.append(f"  [FAIL] {r.model:<28} {r.error}")
        return "\n".join(lines)


def _panel_status(responses: list[PanelResponse], n_requested: int) -> tuple[str, list[str]]:
    ok = [r for r in responses if r.ok and r.text]
    families = sorted({config.model_family(r.model) for r in ok})
    if len(families) < config.MIN_FAMILIES:
        return "stop", families
    if len(ok) < n_requested:
        return "degraded", families
    return "full", families


async def _resolve_models(backend: Backend, mode: str, panel_spec: str | None) -> list[str]:
    spec = panel_spec or config.PANEL_OVERRIDE or None
    if spec:
        return config.resolve_panel(spec)
    return await backend.default_panel(mode)


async def _run_async(question: str, mode: str, panel_spec: str | None, backend_name: str | None) -> PrismResult:
    if mode not in ("research", "code"):
        raise PrismError(f"Unknown mode {mode!r} (use 'research' or 'code').")
    backend = get_backend(backend_name)
    try:
        models = await _resolve_models(backend, mode, panel_spec)
        # research panelists get web + read-only tools (Fusion-style); code/bakeoff
        # candidates are pure completions. Only the opencode backend uses tools.
        tools = config.panel_tools() if mode == "research" else config.panel_tools("none")
        responses = await run_panel(backend, question, models, tools=tools)

        answers = [(r.model, r.text) for r in responses if r.ok and r.text]
        if not answers:
            raise PrismError(
                "Every panelist failed — nothing to judge:\n"
                + "\n".join(f"  {r.model}: {r.error}" for r in responses)
            )

        status, families = _panel_status(responses, len(models))
        if status == "stop" and config.STRICT:
            raise PrismError(
                f"Refusing (OPENPRISM_STRICT): only {len(families)} model family answered "
                f"({', '.join(families)}); need >= {config.MIN_FAMILIES} for a diverse panel."
            )

        if mode == "code":
            judge_prompt = prompts.code_selection(question, answers)
        else:
            judge_prompt = prompts.research_synthesis(question, answers)

        try:
            final = await judge_async(judge_prompt, backend)
        except PrismError:
            raise
        except Exception as e:  # noqa: BLE001 — don't throw away successful (paid) panel work
            answered = ", ".join(m for m, _ in answers)
            raise PrismError(
                f"Panel succeeded ({answered}) but the judge failed: {e}. "
                "Re-run, or switch OPENPRISM_JUDGE_BACKEND."
            ) from e
        return PrismResult(question, mode, responses, final, config.JUDGE_BACKEND,
                           backend.name, status=status, families=families)
    finally:
        await backend.aclose()


async def _bakeoff_async(question: str, model_a: str, model_b: str, backend_name: str | None) -> tuple[str, list[PanelResponse]]:
    if model_a == model_b:
        raise PrismError("Bake-off needs two different models.")
    backend = get_backend(backend_name)
    try:
        responses = await run_panel(backend, question, [model_a, model_b], tools=config.panel_tools("none"))
        by_model = {r.model: r for r in responses}
        ra, rb = by_model[model_a], by_model[model_b]
        if not (ra.ok and rb.ok):
            failed = [r.model for r in responses if not r.ok]
            raise PrismError(f"Bake-off needs both models to answer; failed: {failed}")
        verdict = await judge_async(prompts.bakeoff(question, (model_a, ra.text), (model_b, rb.text)), backend)
        return verdict, responses
    finally:
        await backend.aclose()


# --- sync entry points (CLI; and MCP server via asyncio.to_thread) ---
def run(question: str, mode: str = "research", panel_spec: str | None = None, backend_name: str | None = None) -> PrismResult:
    return asyncio.run(_run_async(question, mode, panel_spec, backend_name))


def bakeoff(question: str, model_a: str, model_b: str, backend_name: str | None = None) -> tuple[str, list[PanelResponse]]:
    return asyncio.run(_bakeoff_async(question, model_a, model_b, backend_name))
