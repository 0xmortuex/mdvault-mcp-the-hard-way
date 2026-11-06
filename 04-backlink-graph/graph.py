"""Module 04: resolve links to notes and build the backlink graph.

The one rule that makes the module interesting: if a link could mean two notes, we SAY SO.
We never pick one.
"""

from __future__ import annotations

import os
import posixpath
import sys
import unicodedata
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "03-index-and-ranking"))

from index import Index, Note  # noqa: E402
from links import Link  # noqa: E402


def key(s: str) -> str:
    """Comparison key: Unicode-normalised and case-folded, so [[şeker notu]] finds Şeker Notu.md."""
    return unicodedata.normalize("NFC", s).casefold()


def strip_md(path: str) -> str:
    return path[:-3] if path.lower().endswith(".md") else path


def list_attachments(root: str) -> set[str]:
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".md") and not name.startswith("."):
                found.add(os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/"))
    return found


@dataclass
class Resolved:
    src: str  # the note containing the link
    link: Link
    status: str  # "note" | "attachment" | "broken" | "ambiguous"
    target: str | None = None
    candidates: list[str] = field(default_factory=list)


class Graph:
    def __init__(self, notes: dict[str, Note], attachments: set[str]) -> None:
        self.notes = notes
        self.attachments = attachments
        # key(path without .md) for suffix matching, and key(stem) -> paths for name lookups
        self.path_key = {p: key(strip_md(p)) for p in notes}
        self.by_stem: dict[str, list[str]] = {}
        for p, k in self.path_key.items():
            self.by_stem.setdefault(k.rsplit("/", 1)[-1], []).append(p)
        self.by_name: dict[str, list[str]] = {}
        for a in attachments:
            self.by_name.setdefault(key(a.rsplit("/", 1)[-1]), []).append(a)
        self.everything = {key(p): p for p in [*notes, *attachments]}

        self.out: dict[str, list[Resolved]] = {}
        self.inc: dict[str, list[Resolved]] = {}  # backlinks: target note -> links pointing at it
        self.maybe: dict[str, list[Resolved]] = {}  # ambiguous links that COULD point at a note
        for src, note in sorted(notes.items()):
            resolved = [self.resolve(lk, src) for lk in note.links]
            self.out[src] = resolved
            for r in resolved:
                if r.status == "note" and r.target:
                    self.inc.setdefault(r.target, []).append(r)
                elif r.status == "ambiguous":
                    for c in r.candidates:
                        self.maybe.setdefault(c, []).append(r)

    # -- resolving ---------------------------------------------------------

    def candidates(self, name: str) -> list[str]:
        """Every note a wikilink target could mean. A bare name matches by file name anywhere;
        a path ('Alpha/Alpha Plan') must match the END of a note's path, on folder boundaries."""
        k = strip_md(key(name.replace("\\", "/")).strip("/"))
        stem = k.rsplit("/", 1)[-1]
        found = self.by_stem.get(stem, [])
        if "/" not in k:
            return sorted(found)
        exact = [p for p in found if self.path_key[p] == k]
        return sorted(exact or [p for p in found if self.path_key[p].endswith("/" + k)])

    def resolve(self, lk: Link, src: str) -> Resolved:
        if lk.kind == "wiki":
            if lk.target == "":
                return Resolved(src, lk, "note", src)  # [[#Heading]] points inside this note
            cands = self.candidates(lk.target)
            if not cands and not lk.target.lower().endswith(".md"):
                files = self.by_name.get(key(lk.target.rsplit("/", 1)[-1]), [])  # ![[diagram.png]]
                if len(files) == 1:
                    return Resolved(src, lk, "attachment", files[0])
        else:
            cands = self._md_candidates(lk.target, src)
            if len(cands) == 1 and cands[0] in self.attachments:
                return Resolved(src, lk, "attachment", cands[0])
        if len(cands) == 1:
            return Resolved(src, lk, "note", cands[0])
        if len(cands) > 1:
            return Resolved(src, lk, "ambiguous", None, cands)
        return Resolved(src, lk, "broken")

    def _md_candidates(self, dest: str, src: str) -> list[str]:
        base = posixpath.dirname(src)
        joined = dest.lstrip("/") if dest.startswith("/") else posixpath.join(base, dest)
        norm = posixpath.normpath(joined)
        if norm.startswith(".."):
            return []  # leaves the vault
        hit = self.everything.get(key(norm)) or self.everything.get(key(norm + ".md"))
        return [hit] if hit else []

    def note_for(self, ref: str) -> str:
        """Turn a name, path or [[wikilink]] typed by a user into exactly one note path."""
        name = ref.strip()
        if name.startswith("[[") and name.endswith("]]"):
            name = name[2:-2].split("|")[0]
        for ch in "#^":
            name = name.split(ch)[0]
        cands = self.candidates(name)
        if len(cands) == 1:
            return cands[0]
        if not cands:
            raise LookupError(f"no note matches {ref!r}")
        raise LookupError(f"{ref!r} is ambiguous; use the full path of one of: {', '.join(cands)}")

    # -- questions the tools will ask --------------------------------------

    def backlinks(self, note: str) -> list[Resolved]:
        return [r for r in self.inc.get(note, []) if r.src != note]

    def broken(self) -> list[Resolved]:
        return [r for rs in self.out.values() for r in rs if r.status == "broken"]

    def ambiguous(self) -> list[Resolved]:
        return [r for rs in self.out.values() for r in rs if r.status == "ambiguous"]

    def orphans(self) -> list[str]:
        """Notes nothing links to and that link to nothing. A note an ambiguous link might
        point at is not an orphan: someone is trying to reach it."""
        return sorted(
            p for p in self.notes
            if not self.backlinks(p) and p not in self.maybe
            and not any(r.status in ("note", "attachment") and r.target != p for r in self.out[p])
        )


def build(root: str, cache_path: str) -> Graph:
    idx = Index(root, cache_path)
    idx.refresh()
    return Graph(idx.notes, list_attachments(root))
