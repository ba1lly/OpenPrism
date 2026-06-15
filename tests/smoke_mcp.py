"""Smoke test: drive the Prism MCP server over stdio like a real host would.

Runs the server as a subprocess, does the MCP handshake, lists tools, and calls
`list_models` (free — no model spend). Pass --live to also call `research` with a
one-model panel, exercising the full chain (panel API + judge).

    python tests/smoke_mcp.py
    python tests/smoke_mcp.py --live
"""
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main(live: bool) -> None:
    # Launch with THIS interpreter (the venv python running the test) and the full
    # environment, exactly as a host would — picks up OPENPRISM_BACKEND etc. from env.
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "openprism.mcp_server"], cwd=str(ROOT),
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print("TOOLS:", [t.name for t in tools])

            res = await session.call_tool("models", {})
            print("\nmodels ->\n" + res.content[0].text[:600])

            if live:
                print("\n--live: calling research...")
                res = await session.call_tool(
                    "research",
                    {"question": "In one sentence, what is a token bucket?"},
                )
                print(res.content[0].text)


if __name__ == "__main__":
    asyncio.run(main("--live" in sys.argv))
