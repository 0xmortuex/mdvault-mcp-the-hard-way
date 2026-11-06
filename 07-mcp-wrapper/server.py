"""Module 07: the MCP server. Six tools over everything built in Modules 01-06.

Run:  python server.py --vault PATH
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import os
import sys
import tempfile
from collections.abc import Callable
from typing import Any, TypeVar

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "06-rename-refactor"))

from rename import apply_plan, plan_rename, render  # noqa: E402  (importing rename puts modules 01-05 on sys.path)
from graph import Graph, list_attachments  # noqa: E402
from index import Index  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from safeio import VaultError, create_note as _create_note, read_note as _read  # noqa: E402

mcp = MCPServer(
    "minivault",
    instructions=(
        "Work with a folder of markdown notes. Start with vault_overview. Find notes with "
        "search_notes, read them with read_note, follow links with backlinks. rename_note is a "
        "dry run unless dry_run=false. A name shared by two notes is an error listing both paths."
    ),
)

_root = ""
_index: Index | None = None

F = TypeVar("F", bound=Callable[..., Any])


def tool(fn: F) -> F:
    """Register fn as a tool. MCPServer shows the agent ONLY a ToolError's message, so every
    failure we expect (a bad path, an ambiguous name) is re-raised as one. Anything else is a
    bug and stays hidden from the agent but visible in our log."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (VaultError, LookupError, OSError) as e:
            # KeyError/LookupError str() adds quotes around the message; use the raw text
            raise ToolError(str(e.args[0]) if isinstance(e, LookupError) and e.args else str(e)) from e

    mcp.tool()(wrapper)
    return fn


def graph() -> Graph:
    """Refresh the index (cheap: stat every file, re-parse the changed ones), then resolve links.
    Calling this at the start of every tool is what keeps the server honest about edits made
    outside it."""
    global _index
    if _index is None:
        _index = Index(_root, os.path.join(tempfile.gettempdir(), f"minivault-{hashlib.sha1(_root.encode()).hexdigest()[:10]}.json"))
    _index.refresh()
    return Graph(_index.notes, list_attachments(_root))


@tool
def vault_overview() -> str:
    """Count the notes, list the top tags, and report orphans, broken links and ambiguous links.
    Call this first."""
    g = graph()
    tags: dict[str, int] = {}
    for n in g.notes.values():
        for t in n.tags:
            tags[t] = tags.get(t, 0) + 1
    top = ", ".join(f"#{t} ({c})" for t, c in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[:10])
    bad = [(p, n.fm_error) for p, n in sorted(g.notes.items()) if n.fm_error]
    lines = [
        f"{len(g.notes)} notes, {len(g.attachments)} other files",
        f"Top tags: {top or 'none'}",
        f"Orphans: {', '.join(g.orphans()) or 'none'}",
        f"Broken links: {len(g.broken())}; ambiguous links: {len(g.ambiguous())}",
    ]
    lines += [f"Unparseable frontmatter: {p}: {e}" for p, e in bad]
    return "\n".join(lines)


@tool
def search_notes(query: str, limit: int = 10) -> str:
    """Ranked full-text search (BM25) over titles, bodies and tags. Ignores case and diacritics,
    so 'seker' finds 'Şeker'. Returns the best notes first."""
    if limit < 1:
        raise VaultError("limit must be at least 1")
    graph()
    assert _index is not None
    hits = _index.search(query, limit)
    if not hits:
        return f"No notes match {query!r}."
    return "\n".join(f"{score:6.2f}  {path}  --  {_index.notes[path].title}" for path, score in hits)


@tool
def read_note(note: str) -> str:
    """Read a note by path ('Projects/Alpha/Alpha Plan.md'), name ('Alpha Plan') or [[wikilink]].
    If two notes share the name you get an error listing both paths."""
    g = graph()
    path = g.note_for(note)
    text, _ = _read(os.path.join(_root, *path.split("/")))
    n = g.notes[path]
    return f"path: {path}\ntags: {', '.join(n.tags) or 'none'}\nfrontmatter: {n.fm}\n---\n{text.replace(chr(13) + chr(10), chr(10))}"


@tool
def backlinks(note: str) -> str:
    """List every note that links to `note`, with the line number of each link."""
    g = graph()
    path = g.note_for(note)
    rows = sorted({(r.src, r.link.line) for r in g.backlinks(path)})
    if not rows:
        return f"Nothing links to {path}."
    return f"{len(rows)} link lines to {path}:\n" + "\n".join(f"  {src}:{line}" for src, line in rows)


@tool
def create_note(path: str, content: str = "", overwrite: bool = False) -> str:
    """Create a note at a vault-relative path. Refuses to overwrite unless overwrite=true.
    Paths outside the vault, through symlinks, or into dot-folders are refused."""
    graph()
    return f"Created {_create_note(_root, path, content, overwrite)}"


@tool
def rename_note(note: str, new_name: str, dry_run: bool = True) -> str:
    """Rename or move a note and update every link to it. dry_run defaults to TRUE and lists every
    file and link that would change; call again with dry_run=false to apply."""
    g = graph()
    plan = plan_rename(_root, g, note, new_name)
    if dry_run:
        return render(plan, dry_run=True) + "\nCall again with dry_run=false to apply."
    apply_plan(_root, plan)
    return "Renamed.\n" + render(plan, dry_run=False)


def main() -> None:
    global _root
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    _root = os.path.realpath(ap.parse_args().vault)
    if not os.path.isdir(_root):
        ap.error(f"{_root} is not a directory")
    mcp.run()


if __name__ == "__main__":
    main()
