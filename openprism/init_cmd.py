"""`openprism init` — generate MCP config for whichever host(s) you use.

The "usable all over the place" entry point. Prints a ready-to-paste config block
(and the file it goes in) for any MCP-capable host, or writes it for you with
`--write`. Defaults to the `uvx openprism-mcp` launch so there's no clone or venv.

  openprism init                         # interactive
  openprism init --host opencode         # print opencode config
  openprism init --host cursor --backend opencode --print
  openprism init --host opencode --write # merge into the real config file
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HOSTS = ("claude-code", "opencode", "cursor", "windsurf", "gemini", "codex")

# Where each host keeps its MCP config, and which schema it uses.
_JSON_MCPSERVERS = "mcpServers"  # claude-code/.mcp.json, cursor, windsurf, gemini
HOST_FILES = {
    "claude-code": ("./.mcp.json", _JSON_MCPSERVERS),
    "cursor": ("~/.cursor/mcp.json", _JSON_MCPSERVERS),
    "windsurf": ("~/.codeium/windsurf/mcp_config.json", _JSON_MCPSERVERS),
    "gemini": ("~/.gemini/settings.json", _JSON_MCPSERVERS),
    "opencode": ("~/.config/opencode/opencode.json", "opencode"),
    "codex": ("~/.codex/config.toml", "codex-toml"),
}


GIT_URL = "git+https://github.com/ba1lly/OpenPrism"


def _launch(local: bool, pypi: bool = False, ref: str | None = None) -> list[str]:
    """The command that starts the MCP server.

    Default is uvx-from-git. Pass `ref` (a tag/branch/sha) to PIN the version —
    recommended, so a host launch doesn't silently pull whatever is on the default
    branch. `pypi=True` emits the published-package form.
    """
    if local:
        exe = shutil.which("openprism-mcp")
        if exe:
            return [exe]
        return [sys.executable, "-m", "openprism.mcp_server"]
    if pypi:
        # `uvx <pkg>` runs the same-named script; our package is `openprism` and the
        # MCP script is `openprism-mcp`, so we must name the package via --from.
        return ["uvx", "--from", "openprism", "openprism-mcp"]
    url = f"{GIT_URL}@{ref}" if ref else GIT_URL
    return ["uvx", "--from", url, "openprism-mcp"]


def _env(backend: str, judge_backend: str | None, judge_model: str | None) -> dict:
    env = {"OPENPRISM_BACKEND": backend}
    if judge_backend:
        env["OPENPRISM_JUDGE_BACKEND"] = judge_backend
    if judge_model:
        env["OPENPRISM_JUDGE_MODEL"] = judge_model
    return env


def _block(host: str, cmd: list[str], env: dict) -> str:
    schema = HOST_FILES[host][1]
    if schema == "opencode":
        obj = {"mcp": {"openprism": {
            "type": "local", "command": cmd, "enabled": True, "environment": env,
        }}}
        return json.dumps(obj, indent=2)
    if schema == "codex-toml":
        lines = ["[mcp_servers.openprism]",
                 f"command = {json.dumps(cmd[0])}",
                 f"args = {json.dumps(cmd[1:])}"]
        if env:
            kv = ", ".join(f"{k} = {json.dumps(v)}" for k, v in env.items())
            lines.append(f"env = {{ {kv} }}")
        return "\n".join(lines)
    # standard mcpServers JSON
    obj = {"mcpServers": {"openprism": {
        "command": cmd[0], "args": cmd[1:], "env": env,
    }}}
    return json.dumps(obj, indent=2)


def _write_json(path: Path, host: str, cmd: list[str], env: dict) -> bool:
    """Merge the openprism entry into a host's JSON config. Returns True if an
    existing openprism entry was overwritten. Backs up to a timestamped .bak and
    writes atomically (temp file + replace)."""
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists() and path.stat().st_size:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"openprism init: {path} is not valid JSON ({e}); fix or move it first.")
        if not isinstance(data, dict):
            raise SystemExit(f"openprism init: {path} is not a JSON object; refusing to overwrite.")
        bak = path.with_suffix(path.suffix + f".{int(time.time())}.bak")
        shutil.copy(path, bak)
    key = "mcp" if host == "opencode" else "mcpServers"
    existing = key in data and "openprism" in data.get(key, {})
    entry = ({"type": "local", "command": cmd, "enabled": True, "environment": env}
             if host == "opencode"
             else {"command": cmd[0], "args": cmd[1:], "env": env})
    data.setdefault(key, {})["openprism"] = entry
    if host == "opencode":
        data.setdefault("$schema", "https://opencode.ai/config.json")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return existing


def run_init(args) -> int:
    host = args.host
    if not host:
        print("Pick a host:", ", ".join(HOSTS))
        try:
            host = input("host> ").strip()
        except EOFError:
            host = ""
    if host not in HOST_FILES:
        print(f"openprism init: unknown host {host!r}. Choose from: {', '.join(HOSTS)}",
              file=sys.stderr)
        return 1

    cmd = _launch(local=args.local, pypi=getattr(args, "pypi", False),
                  ref=getattr(args, "ref", None))
    env = _env(args.backend, args.judge_backend, args.judge_model)
    rel_path, schema = HOST_FILES[host]
    path = Path(os.path.expanduser(rel_path)) if rel_path.startswith("~") else Path(rel_path)

    if args.write:
        if schema == "codex-toml":
            print("--write isn't supported for Codex (TOML, manual merge). Paste this into "
                  f"{rel_path}:\n", file=sys.stderr)
            print(_block(host, cmd, env))
            return 2  # nothing was written
        overwrote = _write_json(path, host, cmd, env)
        note = " (replaced an existing openprism entry)" if overwrote else ""
        print(f"Wrote openprism MCP server to {path}{note}. Backup saved alongside if it existed.")
        if host == "claude-code":
            print("Tip: or just run `claude --plugin-dir <repo>` to use the bundled plugin.")
        return 0

    print(f"# {host}: add to {rel_path}\n")
    print(_block(host, cmd, env))
    print(f"\n# launch: {' '.join(cmd)}   (use --local to launch from this checkout instead of uvx)")
    return 0
