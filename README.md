# OpenPrism

> Many diverse model voices, split and recombined into one judged answer.

![CI](https://github.com/ba1lly/OpenPrism/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)

OpenPrism sends your prompt to a **panel** of different models in parallel, then a
**judge** model reconciles their answers — an explicit consensus / contradiction /
gaps / blind-spots pass, then a single response better than any individual model
produced. It's the [OpenRouter "Fusion"](https://openrouter.ai/blog) pattern as a
small, self-hostable tool.

**Works with:** Claude Code · opencode · Cursor · Windsurf · Gemini CLI · Codex —
anything that speaks MCP. It runs on models you already have: **any model
configured in [opencode](https://opencode.ai)** (75+ providers, recommended — zero
extra keys), or your own OpenAI-compatible provider keys.

---

## Why it works

- **Diversity beats raw strength.** Independent models from different houses catch
  different things; a judge that reconciles them outperforms any single model on
  open-ended problems.
- **Parallel panel.** Wall-clock ≈ the slowest panelist, not the sum — so a 4th
  model is nearly free in latency.
- **Use it deliberately.** A call costs ~slowest-model + judge. Point it at *hard*
  questions (research, architecture, ambiguous trade-offs), not routine work.
- **Diversity is measured in model *families*, and never silently faked.** OpenPrism
  picks default panels by family (Anthropic / OpenAI / Google / Qwen / GLM / Kimi /
  MiniMax / …), so two models from the same maker don't count as two voices. Each
  run is graded: **`full`** (all panelists answered, ≥ `OPENPRISM_MIN_FAMILIES`
  distinct families), **`degraded`** (a panelist failed but the family floor still
  holds), or **`stop`** (fewer than the floor answered — effectively a single-family
  monoculture). The grade always prints; it's never silently passed off as
  confident, and `OPENPRISM_STRICT=1` refuses a `stop` outright.

## How it works

```
            ┌──────────── panel (parallel) ────────────┐
prompt ───▶ │  model A    model B    model C    model D │ ──▶  judge ──▶ answer
            └───────────────────────────────────────────┘   (reconcile +
                  (different providers / houses)               synthesize)
```

Two **backends** decide where panel calls go (set with `OPENPRISM_BACKEND`):

| Backend | Models from | Use |
|---|---|---|
| `opencode` **(default, recommended)** | **every provider/model authed in opencode** — discovered live, nothing hardcoded, no keys in OpenPrism | easiest; just `opencode auth login` your providers |
| `direct` | your own OpenAI-compatible provider keys (`.env` / `providers.json`) | when you don't run opencode |

Two **modes**:

- **research** (default) — Fusion-style synthesis. This is where the lift is proven.
- **code** — code is verifiable, so blending prose is wrong: each model gives a
  candidate, the judge does **best-of-N selection + repair** and emits a *Verify by:*
  command. (v1 doesn't auto-run tests yet.)

## Install

Pick whichever fits — all cross-platform (Linux / macOS / Windows / WSL).

**A. Claude Code marketplace** (easiest):
```
/plugin marketplace add ba1lly/OpenPrism
/plugin install openprism@openprism
```

**B. Any MCP host via `uvx`** (needs [`uv`](https://docs.astral.sh/uv/); no clone, no venv).
Generate the config for your host with the built-in wizard:
```bash
uvx --from git+https://github.com/ba1lly/OpenPrism openprism init --host opencode
#   ...or --host cursor | windsurf | gemini | codex | claude-code
```
It prints (or `--write`s) the exact MCP config block, with the server launching
via `uvx --from git+…` — works straight from GitHub, nothing to maintain. (After a
PyPI release this shortens to `uvx openprism …`; pass `--pypi` to emit that form.)

**C. From source** (for development):
```bash
git clone https://github.com/ba1lly/OpenPrism && cd OpenPrism
./install.sh          # Linux / macOS / WSL   (Windows: ./install.ps1)
```
The installer creates a venv, installs OpenPrism, seeds `.env`, and prints host
config. Use `openprism init --host <h> --local` to point a host at this checkout.

Then add a provider key to `.env` (`direct` backend) **or** set
`OPENPRISM_BACKEND=opencode` to use opencode's providers with no keys here.

### Judge options

| `OPENPRISM_JUDGE_BACKEND` | `OPENPRISM_JUDGE_MODEL` | Notes |
|---|---|---|
| `claude-code` (default) | alias, e.g. `opus` | `claude -p` headless via a Claude Max plan |
| `anthropic-api` | `opus` or a model id | metered Anthropic API key |
| `opencode` | `provider/model` ref | routes the judge through opencode too |

## Usage (CLI)

```bash
openprism "Best architecture for X, and the trade-offs?"          # research
openprism "Implement a token-bucket rate limiter" --mode code
openprism "..." --panel "google/gemini-2.5-flash,anthropic/claude-haiku-4-5"
openprism --bakeoff modelA modelB "a hard prompt"                 # which model wins?
openprism --list                                                  # presets + known models
openprism doctor                                                  # check your setup
```

With `OPENPRISM_BACKEND=opencode`, panels are `provider/model` refs; with no
`--panel`, OpenPrism auto-picks a diverse default across your connected providers.

## Use as a plugin

OpenPrism is one MCP server with four tools — `research`, `code`, `bakeoff`,
`models` — so every host calls the same core. `openprism init --host <host>`
generates the right config for each:

| Host | Config file | Tools surface as |
|---|---|---|
| Claude Code | marketplace, or `.mcp.json` | `mcp__openprism__research`, …; commands `/openprism*` |
| opencode | `~/.config/opencode/opencode.json` | `openprism_research`, …; commands `/openprism*` |
| Cursor | `~/.cursor/mcp.json` | `openprism` MCP tools |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `openprism` MCP tools |
| Gemini CLI | `~/.gemini/settings.json` | `openprism` MCP tools |
| Codex | `~/.codex/config.toml` | `openprism` MCP tools |

```bash
openprism init --host cursor            # print the block
openprism init --host opencode --write  # merge it into the config file (makes a .bak)
```

For opencode, also copy the command files for slash commands:
```bash
cp integrations/opencode/commands/*.md ~/.config/opencode/commands/
```
Use `/openprism-models` (or the `models` tool) to see which `provider/model` refs
are connected.

### Panelist tools (opencode backend)

Like Fusion, panelists can use **live web** tools. On the opencode backend the
panel runs with `OPENPRISM_PANEL_TOOLS`:

| Value | Panelists get |
|---|---|
| `research` (default, research mode) | `webfetch` + `websearch` + read-only; **all mutation tools denied** (`write`/`edit`/`apply_patch`/`bash`/`task`/`todowrite`) |
| `none` | pure completions (model knowledge only) — used for `code`/`bakeoff` |
| `all` | every opencode tool incl. `bash`/`edit`/`write` — **opt-in, runs on your machine** |

The `direct` backend is plain completions and ignores tools.

## Adding models & providers

**opencode backend (recommended) — you don't add anything to OpenPrism.** Add the
provider *in opencode* and it appears automatically:
```bash
opencode auth login          # pick a provider, paste its key / OAuth
```
Then in any host run `/openprism-models` (or the `models` tool) to see every
`provider/model` ref now available, and use them:
```bash
openprism "…" --panel "anthropic/claude-opus-4-7,google/gemini-3-pro,openai/gpt-5.2"
```
No `--panel`? OpenPrism auto-picks a diverse default across your connected providers.

**direct backend — add providers to OpenPrism.** The default provider is set in
`.env` (`ALIBABA_API_KEY` + `ALIBABA_BASE_URL`). Add more OpenAI-compatible
providers in `providers.json` (copy [`providers.json.example`](providers.json.example)):
```json
{ "openrouter": { "base_url": "https://openrouter.ai/api/v1",
                  "api_key": "env:OPENROUTER_API_KEY",
                  "models": ["anthropic/claude-opus-4", "google/gemini-2.5-pro"] } }
```
Reference them as `provider/model` in `--panel`.

**Judge model** is independent of the panel — set `OPENPRISM_JUDGE_BACKEND` +
`OPENPRISM_JUDGE_MODEL` (see the [judge table](#judge-options)).

## Health check & uninstall

```bash
openprism doctor      # checks backend, opencode server, judge, keys — prints no secrets
./uninstall.sh        # or ./uninstall.ps1 — removes venv/build; leaves your .env
```

## Configuration

All via env vars (`.env` in the repo root — see [`.env.example`](.env.example)):
`OPENPRISM_BACKEND`, `OPENPRISM_JUDGE_BACKEND`, `OPENPRISM_JUDGE_MODEL`,
`ANTHROPIC_API_KEY` (for the `anthropic-api` judge), `OPENPRISM_DEFAULT_PROVIDER`
(which `direct` provider a bare model id uses), `OPENPRISM_PANEL_TOOLS`
(research/none/all), `OPENPRISM_MIN_FAMILIES` (diversity floor, default 2),
`OPENPRISM_STRICT` (refuse below the floor), `OPENPRISM_MAX_PANEL` (size cap),
`OPENPRISM_PANEL_TIMEOUT`, `OPENPRISM_MAX_TOKENS`, and the opencode-backend
`OPENPRISM_OPENCODE_*` settings. Extra `direct`-backend providers go in
`providers.json` (see [`providers.json.example`](providers.json.example)).

## Security notes

- OpenPrism never logs provider keys. The opencode backend queries only the
  keyless `/provider` endpoint (never `/config/providers`, which would return keys),
  and the judge always runs tool-less. Still, bind the opencode server to localhost
  and set `OPENCODE_SERVER_PASSWORD` if you expose it. See [SECURITY.md](SECURITY.md).
- Keep `.env` and `providers.json` out of git (already in `.gitignore`).

## Roadmap

- Publish to PyPI so the launch shortens from `uvx --from git+… openprism-mcp` to
  `uvx --from openprism openprism-mcp` (and the CLI to `uvx openprism …`).
- `code` mode: optional sandboxed test execution (`--verify "<cmd>"`).
- Panelist tools on the `direct` backend (a tool-call loop, so non-opencode panels
  can browse too).
- Smarter default-panel selection (capability-aware, not just provider-diverse).

## License

MIT
