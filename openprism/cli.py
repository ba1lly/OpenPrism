"""Prism CLI.

  openprism "question"                       # research synthesis (default 4-house panel)
  openprism "task" --mode code               # best-of-N + repair (coder panel)
  openprism "q" --panel research-lean        # use a preset
  openprism "q" --panel qwen3.7-plus,glm-5   # ad-hoc panel
  openprism --bakeoff qwen3.7-plus qwen3-max-2026-01-23 "your test prompt"
  openprism --list                           # show presets + known models
"""
import argparse
import sys

from . import config
from .config import PrismError
from .pipeline import bakeoff, run

# Windows consoles default to cp1252 and choke on model output / glyphs.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def _print_result(result) -> None:
    print("\n" + "=" * 70)
    print(f"OPENPRISM | mode={result.mode} | judge={result.judge_backend}")
    print(result.status_line())
    print("Panel:")
    print(result.panel_summary())
    print("=" * 70 + "\n")
    print(result.final)
    print()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "doctor":
        from .doctor import run_doctor

        return run_doctor()
    if argv and argv[0] == "init":
        from .init_cmd import run_init

        ip = argparse.ArgumentParser(prog="openprism init",
                                     description="Generate MCP config for a host.")
        ip.add_argument("--host", help="claude-code | opencode | cursor | windsurf | gemini | codex")
        ip.add_argument("--backend", default="opencode", choices=["direct", "opencode"])
        ip.add_argument("--judge-backend", dest="judge_backend", default=None)
        ip.add_argument("--judge-model", dest="judge_model", default=None)
        ip.add_argument("--local", action="store_true",
                        help="launch from this checkout instead of uvx")
        ip.add_argument("--pypi", action="store_true",
                        help="emit the published-package form (after PyPI publish) instead of uvx-from-git")
        ip.add_argument("--ref", default=None,
                        help="pin the uvx-from-git launch to a tag/branch/sha (recommended)")
        ip.add_argument("--write", action="store_true", help="merge into the host's config file")
        ip.add_argument("--print", action="store_true", help="print the config block (default)")
        return run_init(ip.parse_args(argv[1:]))

    p = argparse.ArgumentParser(prog="openprism", description="Multi-model panel + judge.")
    p.add_argument("question", nargs="*", help="the question / task")
    p.add_argument("--mode", choices=["research", "code"], default="research")
    p.add_argument("--panel", help="preset name or comma-separated model ids")
    p.add_argument("--bakeoff", nargs=2, metavar=("MODEL_A", "MODEL_B"),
                   help="compare two models on the question; judge picks a winner")
    p.add_argument("--list", action="store_true", help="list presets and known models")
    args = p.parse_args(argv)

    if args.list:
        print("Panel presets:")
        for name, models in config.PANELS.items():
            print(f"  {name:<16} {', '.join(models)}")
        print("\nKnown models:")
        for m in config.KNOWN_MODELS:
            print(f"  {m}")
        return 0

    question = " ".join(args.question).strip()
    if not question:
        p.error("no question given")

    try:
        if args.bakeoff:
            a, b = args.bakeoff
            verdict, responses = bakeoff(question, a, b)
            print("\n" + "=" * 70)
            print(f"BAKE-OFF | {a}  vs  {b}")
            for r in responses:
                tag = f"{r.latency:.1f}s" if r.ok else f"FAILED: {r.error}"
                print(f"  {r.model:<22} {tag}")
            print("=" * 70 + "\n")
            print(verdict)
            print()
            return 0

        result = run(question, mode=args.mode, panel_spec=args.panel)
        _print_result(result)
        return 0
    except PrismError as e:
        print(f"openprism: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
