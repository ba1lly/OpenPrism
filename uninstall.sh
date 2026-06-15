#!/usr/bin/env bash
# Remove OpenPrism's local install artifacts. Leaves your .env / providers.json.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

rm -rf "$ROOT/.venv" "$ROOT/build" "$ROOT"/*.egg-info
echo "Removed venv/build artifacts."
echo
echo "To finish, remove the 'openprism' MCP server from any host you configured:"
echo "  Claude Code : /plugin uninstall openprism   (or delete it from .mcp.json / ~/.claude.json)"
echo "  opencode    : delete the mcp.openprism block from ~/.config/opencode/opencode.json"
echo "  cursor      : ~/.cursor/mcp.json"
echo "  windsurf    : ~/.codeium/windsurf/mcp_config.json"
echo "  gemini      : ~/.gemini/settings.json"
echo "  codex       : ~/.codex/config.toml"
echo
echo "Your .env and providers.json were left untouched. Delete them manually if desired."
