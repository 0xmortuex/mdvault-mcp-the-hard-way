"""Module 02: find [[wikilinks]], [markdown](links.md) and #tags in note text.

Every link records the exact span of its TARGET, so a later module can rename a note by
splicing a new target into the file without disturbing any other byte.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from urllib.parse import unquote


@dataclass(frozen=True)
class Link:
    kind: str  # "wiki" or "md"
    embed: bool  # ![[x]] or ![alt](x)
    target: str  # decoded: "Folder/Note" (wiki) or "../a b.md" (md)
    fragment: str  # "#Heading" or "^block" or ""
    alias: str  # |alias (wiki) or link text (md)
    tstart: int  # span of the target in the file text: text[tstart:tend] == the raw target
    tend: int
    line: int  # 1-based


WIKI = re.compile(r"(!?)\[\[([^\[\]\n]*)\]\]")
MD = re.compile(r"(!?)\[([^\]\n]*)\]\((<[^>\n]*>|[^)\s]*)\)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
TAG = re.compile(r"(?<![\w/#&\[(])#(\w[\w/\-]*)")
FENCE = re.compile(r"^[ \t]{0,3}(```|~~~)")


def mask_code(text: str) -> str:
    """Blank out code fences and `inline code` (same length, newlines kept).

    Links inside code are examples, not links. Masking instead of removing keeps every
    character at its original offset, so spans found in the masked text are valid in the
    real text.
    """
    out: list[str] = []
    in_fence = ""
    for line in text.split("\n"):
        m = FENCE.match(line)
        if in_fence:
            if m and m.group(1) == in_fence:
                in_fence = ""
            out.append(" " * len(line))
        elif m:
            in_fence = m.group(1)
            out.append(" " * len(line))
        else:
            out.append(re.sub(r"`[^`\n]*`", lambda mm: " " * len(mm.group()), line))
    return "\n".join(out)


def parse_links(text: str) -> list[Link]:
    masked = mask_code(text)
    starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]
    links: list[Link] = []

    for m in WIKI.finditer(masked):
        inner, base = m.group(2), m.start(2)
        head, _, alias = inner.partition("|")
        if head.endswith("\\"):  # [[Note\|alias]] inside a table: the backslash escapes the pipe
            head = head[:-1]
        cut = next((i for i, ch in enumerate(head) if ch in "#^"), len(head))
        name = head[:cut]
        lead = len(name) - len(name.lstrip())
        links.append(
            Link("wiki", m.group(1) == "!", name.strip(), head[cut:].strip(), alias.strip(),
                 base + lead, base + lead + len(name.strip()), bisect.bisect_right(starts, m.start()))
        )

    wiki_spans = [(lk.tstart, lk.tend) for lk in links]
    for m in MD.finditer(masked):
        if any(a <= m.start(3) <= b for a, b in wiki_spans):
            continue
        dest, dstart = m.group(3), m.start(3)
        if dest.startswith("<"):
            dest, dstart = dest[1:-1], dstart + 1
        if not dest or dest.startswith("#") or SCHEME.match(dest):
            continue  # same-note anchor, or http:, mailto:, ...
        path, hash_, frag = dest.partition("#")
        if not path:
            continue
        links.append(
            Link("md", m.group(1) == "!", unquote(path), hash_ + frag, m.group(2),
                 dstart, dstart + len(path), bisect.bisect_right(starts, m.start()))
        )
    links.sort(key=lambda lk: lk.tstart)
    return links


def parse_tags(body: str) -> list[str]:
    """#tag and #nested/tag in the text, lowercased. '#2024' is not a tag; code is ignored."""
    tags = []
    for m in TAG.finditer(mask_code(body)):
        t = m.group(1).rstrip("/-")
        if t and not t.isdigit():
            tags.append(t.lower())
    return tags
