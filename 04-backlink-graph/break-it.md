# Break It: The Backlink Graph

## Challenge 1: Make Resolution Pick One

In `resolve`, change the `len(cands) > 1` branch to return `cands[0]` as a `note`. Run
`main.py`. Which assertions fail? Which ones do *not*, and what does that tell you about
how long this bug would live in a real vault?

**Hint:** Only the ambiguity checks fail. Backlinks, orphans and broken links all still
look plausible, because they are wrong in a quiet way: some links are attributed to the
wrong twin.

## Challenge 2: Compare Without `key`

Compare `lk.target` to the file stem directly (no `casefold`, no NFC). Which sample links
stop resolving? Create a file whose name is spelled in NFD (decomposed) and see what
happens on your OS.

**Hint:** `[[şeker notu]]` and `[[BETA plan]]` break immediately. The NFD case depends on
the file system: macOS stores decomposed names, Linux and Windows keep what you gave them,
so the same vault can behave differently on two machines.

## Challenge 3: A Link That Climbs Out

Add `[escape](../../../etc/passwd)` to a note. Remove the `norm.startswith("..")` guard.
Does the link resolve? Why does it matter that the answer is "never"?

**Hint:** It will not resolve here, because `everything` only holds files inside the
vault. The guard is defence in depth: the graph should not even ask the question for a
path outside the root. In Module 05 the same idea is enforced on every write.
