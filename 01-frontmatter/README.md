# Module 01: Frontmatter

## The Concept

A note vault is a folder of text files, and most of the structure is *inside* the files.
The first structured thing is **frontmatter**: a block of YAML at the very top, fenced
by `---` lines.

```
---
status: draft          # still thinking
tags:
  - project
due: 2026-12-01
---
# Alpha Plan
```

An agent that can read this can answer "which notes are drafts?" without opening them
all. An agent that can *write* it has a new way to corrupt your notes. Both facts drive the
design of this module.

## Decision 1: write the parser, don't import pyyaml

`pyyaml` is a fine library. We still don't use it, for three reasons:

1. **Surprising types.** YAML 1.1 turns `no` into `False`, `2026-12-01` into a `date`
   object, `007` into an octal number. A notes tool wants dates as sortable strings and
   `no` as the word "no".
2. **Error messages.** When a note's frontmatter is broken, the agent needs
   `line 3: unterminated list`, not a stack trace from a library.
3. **It teaches the format.** A subset parser is ~80 lines.

The real mdvault-mcp parser is a bigger subset (nested maps, flow maps, block scalars).
This module's covers what you need to follow along: flat `key: value`, quoted strings,
numbers, booleans, null, inline lists and block lists. **Anything outside the subset
raises `FrontmatterError` with a line number.** It never guesses.

## Decision 2: finding the fences

```python
first_nl = text.find("\n")
if first_nl == -1 or text[:first_nl].rstrip() != "---":
    return None, 0
```

The first line must be `---` and nothing may come before it. An opening fence with no
closing fence is *not* frontmatter (a note that starts with a horizontal rule is common),
so `split_frontmatter` returns `(None, 0)` and the whole file is body.

It returns the **offset** where the body starts, not a copy of the body. Later modules
need to know exactly where in the file things are, and offsets are how you splice.

We also read files as *bytes* and decode ourselves. Python's text mode silently turns
`\r\n` into `\n`, and then you would write a different file than you read.

## Decision 3: comments

```
status: draft          # still thinking
```

`strip_comment` cuts at ` #`, but only outside quotes, so `title: "C# notes"` keeps its
`#`. A `#` only starts a comment at the start of the line or after whitespace, so
`url: http://x.org/#anchor` survives.

## Decision 4: never re-serialise

The most important line in the module is `set_scalar`:

```python
return text[: m.start(2)] + new_value + text[m.end(2) :]
```

To change `status`, parse-then-dump would lose the comment, the alignment spaces,
quoting style and line endings. Instead we find the exact characters of the old value
and replace only those. The `main.py` assertion checks the result is *byte-identical*
except for the value.

This is the rule the whole project follows: **find the span, splice the span.**

## Run It

```
python main.py
```

It parses every note in `../sample-vault`, checks the types and the broken note's error
line, and edits a value in an LF file and a CRLF file.

## What You Learned

- Frontmatter is fenced, first-line-only, and may be absent.
- A small parser with line-numbered errors beats a library for this job.
- Offsets and splices, not parse-and-dump, are how you edit text you don't own.

Next: the links between notes.
