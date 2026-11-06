# Module 05: Safe Writes

## The Concept

Everything so far only reads. The moment a tool can write, it can lose someone's notes.
An agent is not malicious, but it is *confidently wrong* often enough that every write
path has to assume the input is hostile: a path with `..`, a rename that collides, a
half-finished write when the laptop sleeps.

Four promises, each one small function.

## Promise 1: the path stays inside the vault

```python
parts = clean_rel(rel).split("/")
target = os.path.join(root, *parts)
if os.path.normcase(os.path.realpath(target)) != os.path.normcase(target):
    raise VaultError("... goes through a symbolic link or junction")
```

Two layers:

1. `clean_rel` is a **text** check: no absolute paths, no drive letters, no `..`, nothing
   starting with `.` (that rules out `.git` and `.obsidian` in one rule), no characters or
   names Windows rejects. A vault that works on your Mac should still sync to your Windows
   laptop.
2. `confine` is a **file system** check. Text checks cannot see a symlink: a folder
   `Linked/` inside your vault that points at `~/.ssh` passes every string test. `realpath`
   follows every link in the path; if the answer is not where we built it, a link is
   involved and we refuse.

We refuse *all* links on a write path, even ones that point back inside the vault. Allowing
"safe" links means reasoning about where they lead, and every such rule is a future bug.
Windows **junctions** are the same trick without the privilege requirement, and
`realpath` sees through them too. `main.py` builds one for real and attacks it.

## Promise 2: atomic writes

Writing a file in place has a window where it is half old, half new. Crash inside it and
the note is truncated. The fix:

```python
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))   # same folder
... write, flush, os.fsync ...
os.replace(tmp, path)                                    # atomic swap
```

- Same folder, because `os.replace` is only atomic within one file system.
- `fsync` before the swap, so the bytes are on disk before the name points at them.
- Any failure removes the temp file and re-raises. `main.py` makes `os.replace` fail and
  checks the original bytes and the absence of leftovers.

The temp file starts with `.` so the scanner ignores it even if it were ever left behind.

## Promise 3: preserve what you didn't change

Open a CRLF file in text mode, write it back, and every line ending flips to LF: a
one-word edit becomes a whole-file diff. So:

- read **bytes**, decode, keep the text with its `\r\n`;
- detect the file's dominant ending, and convert *the new text* to it;
- keep a UTF-8 BOM if there was one;
- an agent sending `"line1\nline2"` into a CRLF file must produce `line1\r\nline2`. That
  goes for `edit_note`'s `old_text` too, otherwise it would never match.

A file that is not valid UTF-8 raises an error. We don't "fix" it, since decoding with
`errors="replace"` and writing back would permanently destroy bytes.

## Promise 4: no surprises

- `create_note` refuses to overwrite unless `overwrite=true` is passed, and an overwrite
  keeps the old file's line endings.
- `edit_note` requires `old_text` to occur **exactly once**. Zero matches: not found. Two
  or more: the error says how many, and that more surrounding text will fix it. This turns
  "I changed the wrong paragraph" into an error the agent can read and recover from.
- `dry_run` computes the result and writes nothing.

## Errors are part of the tool

`VaultError` is the "expected failure" type. In Module 07 it becomes the only kind of
exception whose message reaches the agent; every message names the problem *and* the next
step ("Pass overwrite=true", "add surrounding text").

## Run It

```
python main.py
```

It attacks everything above on a copy of the sample vault and prints one line per attack
that was repelled.

## What You Learned

- Text checks and file system checks guard different things; you need both.
- Same-folder temp file + `fsync` + `os.replace` is the standard atomic write.
- Read bytes, splice text, keep the file's own line endings.
- Make ambiguity an error with a fix in the message.

Next: the hardest write: renaming a note and every link to it.
