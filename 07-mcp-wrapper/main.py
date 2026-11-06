"""Module 07: a real MCP session.

Starts server.py as a subprocess (stdio, exactly how Claude Desktop would), on a COPY of
the sample vault, and talks to it with the official MCP client: list the tools, use them,
and check that errors arrive with their helpful text.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import tempfile

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

EXPECTED = {"vault_overview", "search_notes", "read_note", "backlinks", "create_note", "rename_note"}


async def session(vault: str) -> None:
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "server.py"), "--vault", vault])
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        assert init.server_info.name == "minivault"
        tools = (await s.list_tools()).tools
        assert {t.name for t in tools} == EXPECTED
        assert all(len(t.description or "") > 40 for t in tools)  # the description IS the agent's manual

        async def call(name: str, args: dict | None = None):
            res = await s.call_tool(name, args or {})
            return res.is_error, res.content[0].text

        err, text = await call("vault_overview")
        print(text)
        assert not err and "11 notes" in text and "Orphan.md" in text and "Bad Frontmatter.md" in text

        err, text = await call("search_notes", {"query": "seker cicek"})
        assert not err and text.splitlines()[0].endswith("Turkce/Şeker Notu.md  --  Şeker Notu"), text

        err, text = await call("backlinks", {"note": "[[Alpha Plan]]"})
        assert not err and "Home.md:10" in text and "Projects/Beta/Beta Plan.md:8" in text

        # Errors reach the agent WITH their advice, because they were raised as ToolError.
        err, text = await call("read_note", {"note": "Meeting Notes"})
        assert err and "ambiguous" in text and "Areas/Meeting Notes.md" in text, text
        err, text = await call("create_note", {"path": "../escape.md", "content": "x"})
        assert err and "'..'" in text, text
        err, text = await call("create_note", {"path": "Home.md", "content": "x"})
        assert err and "overwrite=true" in text, text
        err, text = await call("search_notes", {"query": "x", "limit": 0})
        assert err and "limit" in text, text

        # Create, then rename with a dry run first.
        err, text = await call("create_note", {"path": "Inbox/Idea", "content": "see [[Home]]"})
        assert not err and text == "Created Inbox/Idea.md"
        err, text = await call("rename_note", {"note": "Beta Plan", "new_name": "Beta Roadmap"})
        assert not err and text.startswith("DRY RUN") and "dry_run=false" in text
        assert os.path.exists(os.path.join(vault, "Projects", "Beta", "Beta Plan.md"))  # nothing happened yet
        err, text = await call("rename_note", {"note": "Beta Plan", "new_name": "Beta Roadmap", "dry_run": False})
        assert not err and text.startswith("Renamed.")
        assert os.path.exists(os.path.join(vault, "Projects", "Beta", "Beta Roadmap.md"))
        err, text = await call("backlinks", {"note": "Beta Roadmap"})
        assert not err and "Home.md:8" in text  # the index noticed the change made through another tool


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    src = ap.parse_args().vault
    with tempfile.TemporaryDirectory() as tmp:
        vault = os.path.join(tmp, "vault")
        shutil.copytree(src, vault)
        asyncio.run(session(vault))
    print("module 07 ok")


if __name__ == "__main__":
    main()
