# Remove OpenPrism's local install artifacts. Leaves your .env / providers.json.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

foreach ($d in @(".venv", "build")) {
    $p = Join-Path $Root $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
Get-ChildItem -Path $Root -Filter *.egg-info -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Write-Host "Removed venv/build artifacts."
Write-Host ""
Write-Host "To finish, remove the 'openprism' MCP server from any host you configured:"
Write-Host "  Claude Code : /plugin uninstall openprism (or delete from .mcp.json / ~/.claude.json)"
Write-Host "  opencode    : ~/.config/opencode/opencode.json (mcp.openprism)"
Write-Host "  cursor      : ~/.cursor/mcp.json"
Write-Host "  windsurf    : ~/.codeium/windsurf/mcp_config.json"
Write-Host "  gemini      : ~/.gemini/settings.json"
Write-Host "  codex       : ~/.codex/config.toml"
Write-Host ""
Write-Host "Your .env and providers.json were left untouched."
