"""Module 06: rename a note and fix every link to it.

plan_rename()  works out every edit and writes nothing (this IS the dry run)
render()       shows the plan to a human or an agent
apply_plan()   re-checks the files are unchanged, writes them, then moves the note
"""

from __future__ import annotations

import os
import posixpath
import sys
from dataclasses import dataclass, field
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "05-safe-writes"))
sys.path.insert(0, os.path.join(HERE, "..", "04-backlink-graph"))

from graph import Graph, Resolved, key, strip_md  # noqa: E402
from links import Link, parse_links  # noqa: E402
from safeio import VaultError, clean_rel, confine, read_note, write_note  # noqa: E402


@dataclass
class Edit:
    start: int  # span of the link TARGET in the source file's text
    end: int
    new: str
    line: int
    before: str  # the whole line, for display
    after: str


@dataclass
class Plan:
    old: str
    new: str
    files: dict[str, list[Edit]] = field(default_factory=dict)
    skipped: list[Resolved] = field(default_factory=list)  # ambiguous links we refuse to touch
    snapshot: dict[str, str] = field(default_factory=dict)  # file text at planning time


def new_wiki_target(lk: Link, new_rel: str, stem_is_unique: bool) -> str:
    """Keep the author's style: a bare name stays a bare name unless that would now be ambiguous."""
    stem = posixpath.basename(strip_md(new_rel))
    target = stem if "/" not in lk.target and stem_is_unique else strip_md(new_rel)
    return target + ".md" if lk.target.lower().endswith(".md") else target


def new_md_target(lk: Link, new_rel: str, src_after_move: str) -> str:
    """A markdown link is a path relative to the file it is written in, so it must be
    recomputed from where that file will be AFTER the move."""
    if lk.target.startswith("/"):
        dest = "/" + new_rel
    else:
        dest = posixpath.relpath(new_rel, posixpath.dirname(src_after_move) or ".")
    if not lk.target.lower().endswith(".md"):
        dest = strip_md(dest)
    return quote(dest, safe="/.-_~")  # "my note.md" -> "my%20note.md"


def plan_rename(root: str, g: Graph, ref: str, new_name: str) -> Plan:
    old = g.note_for(ref)
    nn = new_name.replace("\\", "/")
    new_rel = clean_rel(nn if "/" in nn else posixpath.join(posixpath.dirname(old), nn))
    new_rel = new_rel if new_rel.lower().endswith(".md") else new_rel + ".md"
    confine(root, new_rel)
    if new_rel == old:
        raise VaultError(f"{old} already has that name")
    if key(new_rel) in g.everything and key(new_rel) != key(old):
        raise VaultError(f"{new_rel} already exists; rename never overwrites")
    twins = [p for p in g.by_stem.get(key(posixpath.basename(strip_md(new_rel))), []) if p != old]
    if twins:  # the real server is cleverer here; the mini one is simply careful
        raise VaultError(f"another note is already called {posixpath.basename(strip_md(new_rel))!r} ({twins[0]}); pick a different name")

    plan = Plan(old, new_rel)
    sources = {r.src for r in g.inc.get(old, [])} | {old}  # the note itself, for its own relative links
    for src in sorted(sources):
        text, _ = read_note(os.path.join(root, *src.split("/")))
        plan.snapshot[src] = text
        src_after = new_rel if src == old else src
        edits: list[Edit] = []
        for lk in parse_links(text):  # re-parse the LIVE text: offsets must match what is on disk
            r = g.resolve(lk, src)
            if r.status not in ("note", "attachment"):
                continue
            new_target = None
            if r.target == old and lk.target != "":
                new_target = new_wiki_target(lk, new_rel, True) if lk.kind == "wiki" else new_md_target(lk, new_rel, src_after)
            elif src == old and lk.kind == "md" and posixpath.dirname(new_rel) != posixpath.dirname(old):
                new_target = new_md_target(lk, r.target or "", src_after)  # the moved note's own relative links
            if new_target is None or new_target == text[lk.tstart : lk.tend]:
                continue
            ls = text.rfind("\n", 0, lk.tstart) + 1
            le = text.find("\n", lk.tstart)
            le = len(text) if le == -1 else le
            edits.append(Edit(lk.tstart, lk.tend, new_target, lk.line, text[ls:le].strip(),
                              (text[ls : lk.tstart] + new_target + text[lk.tend : le]).strip()))
        if edits:
            plan.files[src] = edits
    plan.skipped = sorted(g.maybe.get(old, []), key=lambda r: (r.src, r.link.line))
    return plan


def render(plan: Plan, dry_run: bool) -> str:
    n = sum(len(e) for e in plan.files.values())
    lines = [f"{'DRY RUN, nothing written. ' if dry_run else ''}{plan.old} -> {plan.new}",
             f"{n} link(s) in {len(plan.files)} file(s):"]
    for src, edits in plan.files.items():
        lines.append(f"  {src}")
        for e in edits:
            lines += [f"      L{e.line}: {e.before}", f"       -> {e.after}"]
    for r in plan.skipped:
        lines.append(f"NOT updated (ambiguous): {r.src}:{r.link.line} -> could be {', '.join(r.candidates)}")
    return "\n".join(lines)


def apply_plan(root: str, plan: Plan) -> None:
    new_texts: dict[str, tuple[str, bool]] = {}
    for src, edits in plan.files.items():
        text, bom = read_note(os.path.join(root, *src.split("/")))
        if text != plan.snapshot[src]:
            raise VaultError(f"{src} changed while the rename was being planned; nothing was written. Try again.")
        for e in sorted(edits, key=lambda e: -e.start):  # back to front, so earlier offsets stay valid
            text = text[: e.start] + e.new + text[e.end :]
        new_texts[src] = (text, bom)
    for src, (text, bom) in new_texts.items():
        write_note(os.path.join(root, *src.split("/")), text, bom)
    new_abs = confine(root, plan.new)
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    os.rename(os.path.join(root, *plan.old.split("/")), new_abs)


