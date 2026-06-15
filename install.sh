#!/usr/bin/env bash
# Prism installer (Linux / macOS / WSL). Creates a venv, installs Prism, and
# prints ready-to-paste host config for Claude Code and opencode.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"

echo "Prism: creating venv at $VENV"
"$PYTHON" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -e "$ROOT"

PY="$VENV/bin/python"
echo
echo "Installed. Entry point: $PY -m openprism.mcp_server"
echo
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  chmod 600 "$ROOT/.env" 2>/dev/null || true   # it will hold a secret
  echo "Created .env from .env.example — edit it to add a provider key (direct backend)."
  echo
fi

cat <<EOF
================= Claude Code =================
Local dev:  claude --plugin-dir "$ROOT"
(uses the .mcp.json in the repo; direct backend / your .env providers)

================= opencode ====================
Add to ~/.config/opencode/opencode.json (configs merge):

{
  "\$schema": "https://opencode.ai/config.json",
  "mcp": {
    "openprism": {
      "type": "local",
      "command": ["$PY", "-m", "openprism.mcp_server"],
      "enabled": true,
      "environment": { "OPENPRISM_BACKEND": "opencode" }
    }
  }
}

Copy the command files:
  cp "$ROOT"/integrations/opencode/commands/*.md ~/.config/opencode/commands/

NOTE: the judge defaults to claude-code (needs the \`claude\` CLI). For an
opencode-only setup, add to the environment block above:
  "OPENPRISM_JUDGE_BACKEND": "opencode", "OPENPRISM_JUDGE_MODEL": "<a connected provider/model>"
===============================================
EOF
