# Module 03: Index and Ranking

## The Concept

An agent asking "what do I know about kernel schedulers?" should not read 5,000 files. It
needs a ranked list with the best match first. That takes two things: an **index** (parse
each note once, remember the result) and a **ranking function**.

## The Note record

`parse_note` turns one file into a `Note`: title, frontmatter, tags, links, and a term
frequency table (`tf`: how many times each word appears). Everything later (search,
backlinks, queries) works from these records and never re-reads the files.

Two details worth copying:

- **A note with broken frontmatter is still a note.** `fm_error` records the message and
  the body is still indexed. Dropping it would make it invisible, which is worse than
  imperfect.
- **The title is the first `# Heading`, else the file name.** Cheap and right for nearly
  every vault.

## Tokenising Turkish (and everything else)

```python
s = unicodedata.normalize("NFKD", word.casefold())
return "".join(c for c in s if not unicodedata.combining(c)).replace("ı", "i")
```

- `casefold()` is a stronger `lower()`. It turns `İ` into `i` plus a combining dot.
- NFKD splits `ş` into `s` + a cedilla mark; we drop the marks. Now `seker` finds `Şeker`.
- `ı` (dotless i) has no decomposition, so it is mapped by hand.

The same function runs on documents and queries, which is the only rule that matters: the
two sides have to agree on what a word is. It also means `cicek` finds `çiçek`, which is
what someone on an English keyboard types.

## BM25 in one paragraph

For each query word, a note scores:

```
idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg_length))
```

- **idf** is high for rare words (`paging`) and near zero for words in every note. This is
  why searching "the kernel" does not drown you in "the".
- **tf** (term frequency) rewards repetition, but the formula *saturates*: the 10th
  mention adds far less than the 2nd (`k1 = 1.2`).
- **length normalisation** (`b = 0.75`) stops long notes winning just by being long.

Scores for the words add up, so a note with both "kernel" and "scheduler" outranks one with
only "kernel". We boost the title by adding 3 to its words' tf, and tags by 2: a note
*named* "Kernel Scheduler" is a better answer than one that mentions it. `main.py` computes
one score by hand and compares it with the library's number to 1e-12.

The loop in `search` scans every note for every term, which is fine for a tutorial and for
a few hundred notes. The real server builds an **inverted index** (term to list of notes)
the first time you search after a change, which is what makes 5,000 notes take ~10 ms.

## The cache

Parsing is the expensive part, so a restarted server should not redo it. `refresh()`:

1. walks the folder, `stat`s each file (cheap);
2. if `(mtime, size)` matches the cache entry, loads the parsed record;
3. otherwise reads and parses the file;
4. drops notes whose files are gone.

`main.py` proves it: first run parses all 11 notes, a "restarted" index parses 0, and after
appending to one file exactly 1 is re-parsed.

Two choices to notice:

- The cache is **outside the vault** in the real server (your notes folder stays clean).
- A **corrupt cache raises an error**; it does not silently rebuild. Hiding it would mean
  an unexplained 30-second pause the next time.

Tools call `refresh()` first on every call, so edits made in Obsidian between two tool
calls are always seen. No file watcher needed.

## Run It

```
python main.py
```

## What You Learned

- Parse once into records; everything else reads records.
- Fold diacritics on both sides of a search.
- BM25 is a few lines and beats "count the matches".
- `(mtime, size)` is a good-enough change detector, and calling `refresh()` per request is
  simpler and safer than watching files.

Next: turning links into a graph.
