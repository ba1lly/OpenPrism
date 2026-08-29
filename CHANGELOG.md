# Changelog

All notable changes to OpenPrism are recorded here. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/), and versions follow semver.

## [0.3.0]

### Changed
- Migrated the MCP server to the mcp v2 SDK: `FastMCP` → `MCPServer`
  (`mcp.server.mcpserver`), dependency now `mcp>=2,<3` (v1 is no longer
  supported). The tool surface, stdio transport, and client-side smoke-test
  API are unchanged in v2. The server now reports its own package version as
  `serverInfo.version` (v2 defaults to empty instead of the SDK version).
- Widened `openai` to `>=2.43.0,<4` (openai 3.x verified against the suite).

## [0.2.0]

### Added
- `OPENPRISM_PANEL`: pin a default panel without passing `--panel` (CLI) or the MCP
  `panel` argument on every call. A preset name, or a comma-separated list of model
  refs (opencode: `provider/model`), e.g.
  `OPENPRISM_PANEL=google/gemini-2.5-pro,openai/gpt-5.4,anthropic/claude-sonnet-4-6`.
  A per-call panel still takes precedence; with neither set, the backend's
  family-diverse auto-panel is used as before.

### Changed
- Raised dependency floors: `openai>=2.43.0`, `anthropic>=0.111.0`, `mcp>=1.28.0`,
  `python-dotenv>=1.2.2` (upper bounds unchanged); the build now requires
  `setuptools>=82.0.1`. CI bumped `actions/checkout` to v7 (setup-python already v6).

## [0.1.0]

First release.

### Added
- Two backends: `direct` (your OpenAI-compatible provider keys) and `opencode`
  (piggyback a running opencode server: every provider/model it has, nothing
  hardcoded).
- MCP server with tools `research`, `code`, `bakeoff`, and `models`; works in Claude
  Code and opencode (and any MCP host).
- Fusion-style panelist tools on the opencode backend: research panelists get
  `webfetch` and `websearch` (read-only), all mutation tools denied by default,
  opt-in via `OPENPRISM_PANEL_TOOLS=all`. The judge always runs without tools.
- `openprism init`: generates MCP config for claude-code, opencode, cursor, windsurf,
  gemini, and codex (`--write` to apply, `--local` for a checkout, `--ref` to pin a
  version).
- `openprism doctor`: diagnoses setup (backend, server, judge, keys) without printing
  secrets.
- Cross-OS install scripts (`install.sh`, `install.ps1`), uninstall scripts, the uvx
  launch, and a Claude Code marketplace manifest.
- Configurable judge: `claude-code` (default), `anthropic-api`, or `opencode`.
- Family-aware diversity: default panels pick one model per model family, and every
  run is graded `full`, `degraded`, or `stop` so a monoculture is never presented as a
  confident result (`OPENPRISM_MIN_FAMILIES`, `OPENPRISM_STRICT`). Panel size is capped
  (`OPENPRISM_MAX_PANEL`).
- Prompt-injection hardening: untrusted question and panel text is fenced as data in
  the judge prompts.
