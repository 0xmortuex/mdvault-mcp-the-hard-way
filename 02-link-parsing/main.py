"""Module 02: link parsing.

Checks the parser on a tricky fixture string, then counts the links in the sample vault,
then uses the recorded spans to rewrite one link by splicing.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import os

from links import mask_code, parse_links, parse_tags

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIXTURE = """\
Plain [[Note]], aliased [[Note|the alias]], heading [[Note#Intro]], block [[Note#^abc]],
path [[Folder/Note]], embed ![[diagram.png]], same-note [[#Local heading]].
Markdown [text](folder/Note.md), encoded [t](my%20note.md#sec), angle [t](<my note.md>),
image ![alt](pics/a.png), web [w](https://example.com/Note.md), mail [m](mailto:a@b.c).
```
[[In A Fence]] and [x](nothing.md)
```
Inline `[[in code]]` is ignored too. Tags: #idea #nested/tag #2024 text#notatag
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    vault = ap.parse_args().vault

    links = parse_links(FIXTURE)
    summary = [(lk.kind, lk.embed, lk.target, lk.fragment, lk.alias) for lk in links]
    for row in summary:
        print(row)
    assert summary == [
        ("wiki", False, "Note", "", ""),
        ("wiki", False, "Note", "", "the alias"),
        ("wiki", False, "Note", "#Intro", ""),
        ("wiki", False, "Note", "#^abc", ""),
        ("wiki", False, "Folder/Note", "", ""),
        ("wiki", True, "diagram.png", "", ""),
        ("wiki", False, "", "#Local heading", ""),
        ("md", False, "folder/Note.md", "", "text"),
        ("md", False, "my note.md", "#sec", "t"),      # %20 decoded
        ("md", False, "my note.md", "", "t"),          # <angle brackets> allowed spaces
        ("md", True, "pics/a.png", "", "alt"),
    ], summary
    # no web links, no mailto, nothing from the code fence or inline code
    assert parse_tags(FIXTURE) == ["idea", "nested/tag"]

    # The span of every target points at exactly the target text.
    for lk in links:
        raw = FIXTURE[lk.tstart : lk.tend]
        assert raw.replace("%20", " ") == lk.target, (raw, lk)

    # Masking keeps offsets: same length, same newlines.
    masked = mask_code(FIXTURE)
    assert len(masked) == len(FIXTURE) and masked.count("\n") == FIXTURE.count("\n")

    # Line numbers survive CRLF files.
    assert [lk.line for lk in parse_links("a\r\n[[x]]\r\n\r\n[[y]]")] == [2, 4]

    # Splice: rewrite [[Note|the alias]] -> [[Renamed|the alias]]. One span, nothing else moves.
    target = next(lk for lk in links if lk.alias == "the alias")
    rewritten = FIXTURE[: target.tstart] + "Renamed" + FIXTURE[target.tend :]
    assert rewritten == FIXTURE.replace("[[Note|the alias]]", "[[Renamed|the alias]]")

    # The real vault.
    total = 0
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.endswith(".md"):
                with open(os.path.join(dirpath, name), "rb") as f:
                    total += len(parse_links(f.read().decode("utf-8")))
    print("links in sample vault:", total)
    assert total == 22, total  # cross-checked against the full mdvault-mcp parser
    print("module 02 ok")


if __name__ == "__main__":
    main()
