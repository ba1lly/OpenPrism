# Prism installer (Windows PowerShell). Creates a venv, installs Prism, and
# prints ready-to-paste host config for Claude Code and opencode.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$Venv = Join-Path $Root ".venv"

Write-Host "Prism: creating venv at $Venv"
& $Python -m venv $Venv
$Py = Join-Path $Venv "Scripts\python.exe"
& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q -e $Root

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Created .env from .env.example — edit it to add a provider key (direct backend)."
}

# JSON-escape backslashes in the Windows path. Use literal String.Replace — the
# regex `-replace '\\','\\'` is a no-op (regex replacement `\\` collapses to one `\`).
$pyJson = $Py.Replace('\', '\\')
Write-Host ""
Write-Host "================= Claude Code ================="
Write-Host "Local dev:  claude --plugin-dir `"$Root`""
Write-Host ""
Write-Host "================= opencode ===================="
Write-Host "Add to your opencode.json (mcp.openprism):"
Write-Host @"
{
  "`$schema": "https://opencode.ai/config.json",
  "mcp": {
    "openprism": {
      "type": "local",
      "command": ["$pyJson", "-m", "openprism.mcp_server"],
      "enabled": true,
      "environment": { "OPENPRISM_BACKEND": "opencode" }
    }
  }
}
"@
Write-Host ""
Write-Host "NOTE: the judge defaults to claude-code (needs the 'claude' CLI). For an"
Write-Host "opencode-only setup, add to the environment block above:"
Write-Host '  "OPENPRISM_JUDGE_BACKEND": "opencode", "OPENPRISM_JUDGE_MODEL": "<a connected provider/model>"'
