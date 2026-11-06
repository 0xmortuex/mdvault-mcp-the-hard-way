"""Module 03: scan the vault, parse each note once, cache the result, rank search with BM25.

The cache here is one JSON file keyed by (mtime, size). The real server uses SQLite so it
can update one row instead of rewriting the whole file; the idea is identical.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("01-frontmatter", "02-link-parsing"):
    sys.path.insert(0, os.path.join(HERE, "..", _d))

from frontmatter import FrontmatterError, parse_yaml, split_frontmatter  # noqa: E402
from links import Link, parse_links, parse_tags  # noqa: E402

WORD = re.compile(r"\w+")
H1 = re.compile(r"^#[ \t]+(.+?)\s*$", re.MULTILINE)


@lru_cache(maxsize=None)
def fold(word: str) -> str:
    """Search form of a word: lowercase and no diacritics, so 'seker' finds 'Şeker'.

    casefold() lowercases (and turns Turkish dotted İ into i + a combining dot);
    NFKD splits letters from their accents; we drop the accents. Dotless ı has no
    decomposition, so it is mapped by hand.
    """
    s = unicodedata.normalize("NFKD", word.casefold())
    return "".join(c for c in s if not unicodedata.combining(c)).replace("ı", "i")


def tokenize(text: str) -> list[str]:
    return [fold(w) for w in WORD.findall(text)]


@dataclass
class Note:
    path: str
    title: str = ""
    fm: dict[str, Any] = field(default_factory=dict)
    fm_error: str | None = None
    tags: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    tf: dict[str, int] = field(default_factory=dict)  # term frequencies
    length: int = 0


def parse_note(path: str, text: str) -> Note:
    note = Note(path)
    raw, body_start = split_frontmatter(text)
    if raw is not None:
        try:
            note.fm = parse_yaml(raw)
        except FrontmatterError as e:
            note.fm_error = str(e)  # keep the note: it is still searchable and linkable
    body = text[body_start:]
    h1 = H1.search(body)
    stem = path.rsplit("/", 1)[-1][:-3]
    note.title = h1.group(1) if h1 else stem
    fm_tags = note.fm.get("tags") or []
    if isinstance(fm_tags, str):
        fm_tags = [t for t in re.split(r"[,\s]+", fm_tags) if t]
    note.tags = sorted({str(t).lstrip("#").lower() for t in fm_tags} | set(parse_tags(body)))
    note.links = parse_links(text)
    tf: Counter[str] = Counter(tokenize(body))
    for t in tokenize(note.title):
        tf[t] += 3  # a title hit is worth more than a body hit
    for t in note.tags:
        for part in tokenize(t):
            tf[part] += 2
    note.tf = dict(tf)
    note.length = sum(tf.values())
    return note


def scan(root: str) -> dict[str, tuple[int, int]]:
    """{relative path: (mtime_ns, size)} for every .md file; dot-folders are skipped."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.endswith(".md") and not name.startswith("."):
                full = os.path.join(dirpath, name)
                st = os.stat(full)
                found[os.path.relpath(full, root).replace("\\", "/")] = (st.st_mtime_ns, st.st_size)
    return found


@dataclass
class Stats:
    parsed: int = 0
    from_cache: int = 0
    removed: int = 0


class Index:
    K1, B = 1.2, 0.75  # the standard BM25 constants

    def __init__(self, root: str, cache_path: str) -> None:
        self.root = root
        self.cache_path = cache_path
        self.notes: dict[str, Note] = {}
        self.stats = Stats()

    def _load_cache(self) -> dict[str, Any]:
        if not os.path.exists(self.cache_path):
            return {}
        with open(self.cache_path, encoding="utf-8") as f:
            return json.load(f)  # a corrupt cache raises: we do not silently rebuild

    def refresh(self) -> Stats:
        """Bring the index up to date. Only files whose (mtime, size) changed are re-parsed."""
        files = scan(self.root)
        cache = self._load_cache()
        stats = Stats()
        new_cache: dict[str, Any] = {}
        for rel, (mtime, size) in files.items():
            hit = cache.get(rel)
            if hit and hit["m"] == mtime and hit["s"] == size:
                n = hit["n"]
                note = Note(rel, n["title"], n["fm"], n["fm_error"], n["tags"], [Link(*x) for x in n["links"]], n["tf"], n["length"])
                stats.from_cache += 1
            else:
                with open(os.path.join(self.root, *rel.split("/")), "rb") as f:
                    note = parse_note(rel, f.read().decode("utf-8"))
                stats.parsed += 1
            self.notes[rel] = note
            new_cache[rel] = {
                "m": mtime, "s": size,
                "n": {"title": note.title, "fm": note.fm, "fm_error": note.fm_error, "tags": note.tags,
                      "links": [list(vars(lk).values()) for lk in note.links], "tf": note.tf, "length": note.length},
            }
        stats.removed = len([p for p in self.notes if p not in files])
        self.notes = {p: n for p, n in self.notes.items() if p in files}
        if stats.parsed or stats.removed or not os.path.exists(self.cache_path):
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(new_cache, f, ensure_ascii=False)
        self.stats = stats
        return stats

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """BM25: sum over query terms of idf * saturated, length-normalised term frequency."""
        terms = list(dict.fromkeys(tokenize(query)))
        n_docs = len(self.notes)
        avg_len = sum(n.length for n in self.notes.values()) / max(n_docs, 1)
        scores: dict[str, float] = {}
        for term in terms:
            containing = [n for n in self.notes.values() if term in n.tf]
            if not containing:
                continue
            df = len(containing)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for n in containing:
                tf = n.tf[term]
                norm = tf + self.K1 * (1 - self.B + self.B * n.length / avg_len)
                scores[n.path] = scores.get(n.path, 0.0) + idf * tf * (self.K1 + 1) / norm
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
