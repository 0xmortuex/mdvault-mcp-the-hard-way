"""Tests for the mini server, over a real stdio connection. Run: pytest test_server.py"""

import os
import shutil
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(os.path.dirname(HERE), "sample-vault")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def vault(tmp_path):
    dest = tmp_path / "vault"
    shutil.copytree(SAMPLE, dest)
    return str(dest)


def connect(vault):
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "server.py"), "--vault", vault])
    return stdio_client(params)


@pytest.mark.anyio
async def test_dry_run_changes_nothing_and_apply_updates_links(vault):
    async with connect(vault) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        with open(os.path.join(vault, "Home.md"), "rb") as f:
            home_before = f.read()
        res = await s.call_tool("rename_note", {"note": "Beta Plan", "new_name": "Beta Roadmap"})
        assert not res.is_error and "DRY RUN" in res.content[0].text
        with open(os.path.join(vault, "Home.md"), "rb") as f:
            assert f.read() == home_before
        res = await s.call_tool("rename_note", {"note": "Beta Plan", "new_name": "Beta Roadmap", "dry_run": False})
        assert not res.is_error
        with open(os.path.join(vault, "Home.md"), "rb") as f:
            assert f.read() == home_before.replace(b"[[Beta Plan|the beta]]", b"[[Beta Roadmap|the beta]]")


@pytest.mark.anyio
async def test_errors_carry_their_advice(vault):
    async with connect(vault) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        res = await s.call_tool("read_note", {"note": "Meeting Notes"})
        assert res.is_error and "Areas/Meeting Notes.md" in res.content[0].text
        res = await s.call_tool("create_note", {"path": "../x.md"})
        assert res.is_error and "'..'" in res.content[0].text
        res = await s.call_tool("rename_note", {"note": "Orphan", "new_name": "Home"})
        assert res.is_error and "already exists" in res.content[0].text


@pytest.mark.anyio
async def test_sees_edits_made_outside_the_server(vault):
    async with connect(vault) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        res = await s.call_tool("search_notes", {"query": "zebras"})
        assert "No notes match" in res.content[0].text
        with open(os.path.join(vault, "Orphan.md"), "ab") as f:
            f.write(b"\nzebras everywhere\n")
        res = await s.call_tool("search_notes", {"query": "zebras"})
        assert "Orphan.md" in res.content[0].text
