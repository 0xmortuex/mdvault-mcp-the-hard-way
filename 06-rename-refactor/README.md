# Module 06: The Rename Refactor

## The Concept

Renaming a note is the operation that justifies a vault tool. Every other tool is a read.
Rename touches *every file that links to the note* and, done wrong, silently breaks
links across the whole vault. This module is where Modules 02 (spans), 04 (resolution) and
05 (safe writes) pay off.

The shape is the same as a refactoring tool in an IDE: **plan, review, apply.**

```
plan_rename()  -> a Plan: every edit, in every file. Writes nothing.
render(plan)   -> text for a human (or an agent) to review.
apply_plan()   -> re-check, write the files, move the note.
```

`dry_run` is not a flag that skips the write at the end. The plan *is* the dry run, so
the preview and the real thing cannot disagree.

## Step 1: who is affected?

```python
sources = {r.src for r in g.inc.get(old, [])} | {old}
```

Exactly the notes with a backlink (Module 04), plus the note itself, because moving it
changes what its own relative markdown links mean. Nothing else is read.

## Step 2: re-parse the live text

For each source we read the file *now* and parse its links again, instead of trusting
offsets saved in the index. The index is a cache; the spans we splice must come from the
bytes we are about to write.

## Step 3: rewrite in the author's style

A link target is rewritten, never the whole link, so the heading, block id, alias and brackets
survive for free:

| before | after renaming `Beta Plan` to `Beta Roadmap` |
|--------|------|
| `[[Beta Plan\|the beta]]` | `[[Beta Roadmap\|the beta]]` |
| `[[Beta Plan#^b1\|beta block]]` | `[[Beta Roadmap#^b1\|beta block]]` |
| `[b](../Beta/Beta%20Plan.md#top)` | `[b](../Beta/Beta%20Roadmap.md#top)` |

Rules:

- **A bare wikilink stays bare** if the new name is still unique; a path-qualified one gets the
  new path.
- **A markdown link is a path relative to its own file**, so after a *move* it must be
  recomputed with `posixpath.relpath` from the file's new location. The moved note's own
  relative links need recomputing too: `../Alpha/Alpha Plan.md` is wrong once the note
  lives in `Archive/`.
- Percent-encoding and a leading `/` are preserved; spaces become `%20`.
- A move that keeps the name does not touch bare wikilinks at all (`main.py` asserts
  `Home.md` is byte-identical).

## Step 4: what we refuse

- **The new path exists.** Rename never overwrites.
- **Another note already has the new name.** It would make every plain `[[Name]]`
  ambiguous. The real server is smarter (it allows it if nothing links to the twin by bare
  name, and writes path links); the mini one just refuses.
- **Ambiguous links** that *might* mean this note are listed as `NOT updated`. We cannot know
  which twin was meant, and a wrong guess is worse than a link a human fixes in ten seconds.

## Step 5: apply carefully

```python
for e in sorted(edits, key=lambda e: -e.start):   # back to front
    text = text[: e.start] + e.new + text[e.end :]
```

Editing back to front means earlier offsets stay valid as later text changes length.

Before writing anything, `apply_plan` re-reads every file and compares it with the snapshot
the plan was made from. If someone (Obsidian sync, you) edited a file in between, it aborts
with nothing written. Only then do files get written (atomically, via Module 05), and
the note moved last.

What this version does *not* do, and the real server does: stage every temp file before
moving the first one, so a full disk is discovered before any file changes.

## The oracle: re-parse and compare

How do you know the rename is right? Not by reading the code. `main.py` records, for
**every link in the vault**, what it resolves to; renames; builds a brand-new index; and
compares:

```python
assert a_status == status
assert a_target == rename(target)
```

Every link must resolve to the same note (under its new name), and no link may become newly
broken or ambiguous. Any bug in the edits, the spans or the relative-path math shows up as a
failed comparison. The real server's tests run this oracle after 25 random renames of a
generated vault, plus a 5,000-note one.

## Run It

```
python main.py
```

## What You Learned

- Refactors are plan, review, apply; the dry run is the plan.
- Splice target spans; derive them from live text; edit back to front.
- Resolve ambiguity by reporting it.
- Verify a refactor with an oracle that re-derives the answer independently.

Next: wrapping it in an MCP server and testing it over a real connection.
