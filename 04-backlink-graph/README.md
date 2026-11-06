# Module 04: The Backlink Graph

## The Concept

Module 02 gave us links as text. A link is useful once we know **which note it points to**.
Resolve every link and you get a graph, and a graph answers the questions a knowledge
base exists for:

- Who links here? (backlinks)
- What does this link to? (outgoing links)
- What points nowhere? (broken links)
- What is isolated? (orphans)

## How Obsidian-style names resolve

A wikilink is a *name*, not a path. `[[Beta Plan]]` finds `Beta Plan.md` in any folder.
That is convenient and it has a catch: two notes can have the same name in different
folders.

```
Areas/Meeting Notes.md
Projects/Meeting Notes.md
```

What does `[[Meeting Notes]]` mean? Obsidian guesses (shortest path). We refuse to. An
agent that rewrites links based on a guess corrupts a vault in a way nobody sees until
months later. So `resolve` returns one of four statuses:

| status | meaning |
|--------|---------|
| `note` | exactly one match |
| `attachment` | exactly one non-markdown file (`![[diagram.png]]`) |
| `broken` | no match |
| `ambiguous` | several matches, and **we list all of them** |

Disambiguation is a user's job: `[[Projects/Meeting Notes]]` matches on the end of the
path, on folder boundaries (`Projects/Meeting Notes` but never `MyProjects/Meeting Notes`).

## Keys: case and Unicode

```python
def key(s): return unicodedata.normalize("NFC", s).casefold()
```

Every comparison goes through `key`. `casefold` makes `[[BETA plan]]` match `Beta Plan.md`.
NFC fixes the nastiest filename bug there is: macOS stores `Ş` as `S` + a combining mark
(NFD), your link was typed as a single character (NFC), and the two look identical and
compare unequal.

## Markdown links resolve differently

`[x](../Beta/Beta%20Plan.md)` is a **path relative to the file it is written in**. We join
it to the source's folder, normalise (`..`), and check the result against the files that
exist. A path that climbs out of the vault resolves to nothing, even if it names a real file
elsewhere on the disk. That is a security property, not just tidiness.

## Building the graph

```python
self.out[src]  = every link in a note, resolved
self.inc[tgt]  = the links that point at a note        (backlinks)
self.maybe[c]  = ambiguous links that COULD point at c
```

Everything is built once from the index, in one pass. Backlink queries are then dictionary
lookups. This is why `note_links` on a 5,000-note vault takes ~10 ms.

Two small decisions to notice:

- **A note linking to itself** (`[[Alpha Plan#Goal]]` inside Alpha Plan) is not a backlink.
- **An orphan** has no links in *or* out. A note an ambiguous link might point at is not an
  orphan: somebody is trying to reach it. Without that rule, one of the two "Meeting Notes"
  would be reported as lonely, which is false.

## Run It

```
python main.py
```

It resolves names (Turkish and path forms), proves ambiguity is reported, lists backlinks
with line numbers, and checks the broken, ambiguous and orphan sets against what is in the
sample vault.

## What You Learned

- Resolution has four outcomes, not two. "Ambiguous" is a first-class answer.
- Normalise and casefold every name before comparing.
- Build the graph once; make every question a lookup.

Next: writing to the vault without hurting it.
