# Changelog

All notable changes to OpenPrism are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [0.1.0] — first release

### Added
- Two backends: `direct` (your OpenAI-compatible provider keys) and `opencode`
  (piggyback a running opencode server — every provider/model it has, nothing
  hardcoded).
- MCP server with tools `research`, `code`, `bakeoff`, `models`; works in Claude
  Code and opencode (and any MCP host).
- Fusion-style panelist tools on the opencode backend: research panelists get
  `webfetch`/`websearch` (read-only); all mutation tools denied by default,
  opt-in via `OPENPRISM_PANEL_TOOLS=all`. The judge always runs tool-less.
- `openprism init` — generates MCP config for claude-code / opencode / cursor /
  windsurf / gemini / codex (`--write` to apply, `--local` for a checkout,
  `--ref` to pin a version).
- `openprism doctor` — diagnoses setup (backend, server, judge, keys) without
  printing secrets.
- Cross-OS install: `install.sh` / `install.ps1`, `uninstall.sh` / `uninstall.ps1`,
  uvx-from-git launch, Claude Code marketplace manifest.
- Configurable judge: `claude-code` (default), `anthropic-api`, or `opencode`.
- Family-aware diversity: default panels pick one model per model *family*; runs are
  labelled `full` / `degraded` / `stop` and never silently present a monoculture
  (`OPENPRISM_MIN_FAMILIES`, `OPENPRISM_STRICT`). Panel size capped (`OPENPRISM_MAX_PANEL`).
- Prompt-injection hardening: untrusted question/panel text is fenced as data in
  judge prompts.
