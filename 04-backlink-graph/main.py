"""Module 04: the backlink graph.

Resolves every link in the sample vault, then checks backlinks, broken links, ambiguity
and orphans against what is known to be in the files.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import os
import tempfile

from graph import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    vault = ap.parse_args().vault

    with tempfile.TemporaryDirectory() as tmp:
        g = build(vault, os.path.join(tmp, "cache.json"))

    # 1. Names resolve by file name anywhere, case-insensitively, Turkish included.
    assert g.note_for("Beta Plan") == "Projects/Beta/Beta Plan.md"
    assert g.note_for("[[BETA plan|x]]") == "Projects/Beta/Beta Plan.md"
    assert g.note_for("şeker notu") == "Turkce/Şeker Notu.md"
    assert g.note_for("Alpha/Alpha Plan") == "Projects/Alpha/Alpha Plan.md"  # path suffix

    # 2. Two notes called "Meeting Notes": say so, never guess.
    try:
        g.note_for("Meeting Notes")
    except LookupError as e:
        print("ambiguous ->", e)
        assert "Areas/Meeting Notes.md" in str(e) and "Projects/Meeting Notes.md" in str(e)
    else:
        raise AssertionError("an ambiguous name must not resolve")
    assert g.note_for("Projects/Meeting Notes") == "Projects/Meeting Notes.md"  # a path settles it

    # 3. Backlinks, including markdown links and embeds, with the line each is on.
    back = g.backlinks("Projects/Alpha/Alpha Plan.md")
    where = sorted({(r.src, r.link.line) for r in back})
    print("backlinks to Alpha Plan:", where)
    assert ("Home.md", 10) in where  # ![[Alpha Plan]]
    assert ("Projects/Beta/Beta Plan.md", 8) in where  # [[Alpha Plan]] and a markdown link, same line
    assert sum(1 for r in back if r.src == "Projects/Beta/Beta Plan.md") == 2
    assert any(r.link.embed for r in back)

    # 4. Links inside code never reach the graph.
    targets = [r.link.target for r in g.out["Projects/Alpha/Alpha Plan.md"]]
    assert "Not A Link In Code" not in targets and "nothing.md" not in targets

    # 5. Broken, ambiguous, attachments.
    broken = sorted((r.src, r.link.target) for r in g.broken())
    print("broken:", broken)
    assert broken == [("Home.md", "Does Not Exist"), ("Home.md", "Projects/Alpha/Plan")], broken
    assert sorted((r.src, r.link.target) for r in g.ambiguous()) == [
        ("Home.md", "Meeting Notes"), ("Projects/Alpha/Alpha Plan.md", "Meeting Notes")
    ]
    assert any(r.status == "attachment" and r.target == "diagram.png" for r in g.out["Home.md"])
    # an ambiguous link might point at either twin, so neither is an orphan
    assert len(g.maybe["Areas/Meeting Notes.md"]) == 2

    # 6. Orphans: no links in or out.
    print("orphans:", g.orphans())
    assert g.orphans() == ["Bad Frontmatter.md", "Orphan.md"]

    # 7. The most linked-to note.
    ranked = sorted(g.notes, key=lambda p: -len({r.src for r in g.backlinks(p)}))
    assert ranked[0] == "Home.md"
    print("module 04 ok")


if __name__ == "__main__":
    main()
