# mdvault-mcp: The Hard Way

Build an MCP server that lets an AI agent work with a folder of markdown notes: search it,
follow its links, and safely rename a note while every link to it is rewritten. You start with
a text file and end with an agent refactoring a vault. No Obsidian, no framework doing the
hard parts for you. Every line explained.

At the end you will have built a small version of [mdvault-mcp](https://github.com/0xmortuex/mdvault-mcp)
yourself, and you will understand the two things most MCP tutorials skip: **how to edit
files you don't own without damaging them**, and **how to design tools and errors for an agent**.

## Why This Exists

Most MCP tutorials stop at a weather API. The hard parts of a useful server are elsewhere:

- parsing a messy human format (YAML frontmatter, two link syntaxes, Turkish file names)
  without losing information;
- ranking search results so the right note comes first;
- making writes **safe**: confined to one folder, atomic, never a surprise overwrite, line
  endings preserved;
- refactoring across many files and **proving** you didn't break anything;
- failing in ways that tell the agent what to do next.

A folder of notes exercises all of it, and it is something people actually own and care about.

## Who This Is For

- Developers who built a "hello world" MCP server and want a real one.
- Anyone who keeps notes in Obsidian, Logseq or plain Markdown and wants an agent in the loop.
- Anyone curious how a safe multi-file rename works.

**Prerequisites:** Python and regular expressions. Nothing else; `pip install -r requirements.txt`.

## Modules

| # | Module | What You'll Build |
|---|--------|-------------------|
| 01 | [Frontmatter](01-frontmatter/) | Split YAML off a note, parse the useful subset with line-numbered errors, edit a value without touching another byte |
| 02 | [Link Parsing](02-link-parsing/) | `[[wikilinks]]` with aliases, headings, blocks and embeds, markdown links, tags, and the exact span of every target |
| 03 | [Index and Ranking](03-index-and-ranking/) | Parse once, cache by mtime, diacritic-folding tokenizer, BM25 checked against a hand calculation |
| 04 | [The Backlink Graph](04-backlink-graph/) | Resolve links to notes, report ambiguity instead of guessing, backlinks, broken links, orphans |
| 05 | [Safe Writes](05-safe-writes/) | Path confinement incl. symlinks and junctions, atomic writes, CRLF/BOM preservation, exact-once edits |
| 06 | [The Rename Refactor](06-rename-refactor/) | Plan, dry-run, apply; rewrite every link form; verify by re-parsing the whole vault |
| 07 | [The MCP Wrapper and Tests](07-mcp-wrapper/) | Six tools over stdio, errors as instructions, tests over a real MCP connection |

Each module contains:

- **`README.md`**: the concepts and the design decisions, and why;
- **a code file** (`frontmatter.py`, `links.py`, `index.py`, `graph.py`, `safeio.py`, `rename.py`, `server.py`) that later modules import;
- **`main.py`**: runs the module against a real vault and checks the results with `assert`;
- **`break-it.md`**: challenges that break your own code, with hints.

## How To Use This Course

**Option A: Build along.** Read each README, type the code file yourself, run `main.py`
to see whether you got it right, then do the break-it challenges.

**Option B: Reference.** Modules build on each other by importing the previous code files
(each `main.py` sets up its own path), so jump to the module you need and read its file.

**Option C: Use the finished tool.** `uvx mdvault-mcp --vault ~/Notes` is what Module 07
grows into.

## Run It

Everything runs against [`sample-vault/`](sample-vault/): eleven small notes with every case the
course cares about: two notes with the same name, a CRLF note, a Turkish file name, a
note with broken frontmatter, an image embed, links inside code blocks, and a hidden
`.obsidian` folder. Modules that write do so on a temporary copy.

```
pip install -r requirements.txt
python 03-index-and-ranking/main.py
```

## Every Module Is Verified

```
python verify.py
```

runs each `main.py` (and Module 07's pytest file, over a real stdio MCP connection) and
fails if any assertion fails. CI runs it on Linux, macOS and Windows on every push and
weekly, so the code in this course can't silently stop working.

## Architecture Overview

```
 AI agent (Claude Code, Claude Desktop, ...)
        |  MCP over stdio: JSON-RPC tool calls                  <- Module 07
        v
 +--------------------------------------------------------+
 | MCP server: tools, error design                        |   <- Module 07
 |   +-- rename:  plan / dry run / apply / verify         |   <- Module 06
 |   +-- safeio:  confine, atomic write, EOL, edits       |   <- Module 05
 |   +-- graph:   resolve links, backlinks, ambiguity     |   <- Module 04
 |   +-- index:   parse once, cache, BM25                 |   <- Module 03
 |   +-- links:   [[wiki]] and [md](links), spans, tags   |   <- Module 02
 |   +-- frontmatter: split, parse, splice                |   <- Module 01
 +--------------------------------------------------------+
        |
        v
   a folder of .md files
```

## License

MIT

> **Windows note:** the modules print Turkish note names. If a module crashes with a UnicodeEncodeError when you run it by hand, set PYTHONIOENCODING=utf-8 (or use python -X utf8 main.py). erify.py does this for you.

