# Contributing to OpenPrism

Thanks for your interest! OpenPrism is a small Python MCP server (a multi-model
panel + judge) that plugs into Claude Code, opencode, and other MCP hosts.

## Dev setup

```bash
git clone https://github.com/ba1lly/OpenPrism && cd OpenPrism
./install.sh          # or ./install.ps1 on Windows — creates .venv, installs editable
./.venv/bin/pip install pytest
```

Point a host at your checkout instead of the published package:
```bash
./.venv/bin/python -m openprism init --host claude-code --local --write
```

## Tests

```bash
pytest -q          # offline unit tests (no network / no model calls)
```
Live checks against a real opencode server live in `tests/smoke_mcp.py` (manual).
Please keep `pytest` green and offline — don't add tests that need API keys or a
running opencode to the default suite.

## Architecture (where things live)

- `openprism/backends/` — `direct` (your provider keys) and `opencode` (piggyback).
  New providers/hosts almost always belong here.
- `openprism/pipeline.py` — panel → judge orchestration.
- `openprism/mcp_server.py` — the MCP tools (`research`/`code`/`bakeoff`/`models`).
- `openprism/init_cmd.py` / `doctor.py` — the `openprism init` / `doctor` commands.

## Conventions

- Keep the two backends behind the `Backend` interface; don't special-case a host
  in the pipeline.
- Never log provider keys. The opencode backend must never read or surface the
  `key` field from `/config/providers`.
- Bump `__version__` in `openprism/__init__.py` and the two `.claude-plugin/*.json`
  manifests together (see CHANGELOG).

## PRs

Small, focused PRs with a green `pytest` run. Describe the behavior change and how
you verified it.
