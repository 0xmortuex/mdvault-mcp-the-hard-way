"""Module 01: frontmatter.

Parses the frontmatter of every note in the sample vault, shows what happens with a
broken one, and edits a value in place without disturbing a single other byte.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import os

from frontmatter import FrontmatterError, parse_yaml, set_scalar, split_frontmatter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_bytes_as_text(path: str) -> str:
    # newline="" semantics: open in binary and decode ourselves so "\r\n" stays "\r\n".
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    vault = ap.parse_args().vault

    # 1. Split and parse every note.
    parsed: dict[str, dict] = {}
    broken: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]  # skip .obsidian, .git
        for name in filenames:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), vault).replace("\\", "/")
            text = read_bytes_as_text(os.path.join(dirpath, name))
            raw, body_start = split_frontmatter(text)
            if raw is None:
                parsed[rel] = {}
                continue
            try:
                parsed[rel] = parse_yaml(raw)
            except FrontmatterError as e:
                broken[rel] = str(e)

    for rel, fm in sorted(parsed.items()):
        if fm:
            print(f"{rel}: {fm}")
    print("unparseable:", broken)

    # 2. What a good parser must get right.
    alpha = parsed["Projects/Alpha/Alpha Plan.md"]
    assert alpha["status"] == "draft"  # the trailing "# still thinking" comment is gone
    assert alpha["tags"] == ["project", "project/alpha"]  # block list
    assert alpha["due"] == "2026-12-01"  # a date stays a string
    assert parsed["Home.md"]["tags"] == ["index", "project"]  # inline list
    assert parsed["Projects/Beta/Beta Plan.md"]["tags"] == "project"  # a bare string, not a list
    assert parsed["Orphan.md"] == {}  # no frontmatter at all

    # 3. A broken note is reported with its line number, not guessed at.
    assert list(broken) == ["Bad Frontmatter.md"], broken
    assert broken["Bad Frontmatter.md"].startswith("line 3:"), broken  # file line, counting the --- fence

    # 4. Editing without re-serialising: only the value's bytes change.
    path = os.path.join(vault, "Projects", "Alpha", "Alpha Plan.md")
    text = read_bytes_as_text(path)
    edited = set_scalar(text, "status", "published")
    assert edited == text.replace("status: draft          # still thinking", "status: published          # still thinking")
    assert "# a comment line that must survive" in edited

    # The same on a CRLF file: the line endings are untouched because we never touched them.
    crlf = read_bytes_as_text(os.path.join(vault, "Projects", "Beta", "Beta Plan.md"))
    assert "\r\n" in crlf
    edited_crlf = set_scalar(crlf, "status", "archived")
    assert edited_crlf == crlf.replace("status: published", "status: archived")
    assert edited_crlf.count("\n") == edited_crlf.count("\r\n")

    # 5. Opening fence without a closing fence is NOT frontmatter.
    assert split_frontmatter("---\nno closing fence\n") == (None, 0)
    print("module 01 ok")


if __name__ == "__main__":
    main()
