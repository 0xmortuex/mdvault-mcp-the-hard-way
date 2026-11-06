# Break It: Index and Ranking

## Challenge 1: Fold the Query but Not the Documents

In `tokenize`, make `fold` return only `word.lower()` for documents (leave the query side
folded). Search for `seker`. Why does it find nothing, and why is the failure silent?

**Hint:** The index contains `şeker` and the query asks for `seker`. Nothing errors; the note
just never matches. Search bugs rarely crash. They return fewer results, and nobody
notices what is missing.

## Challenge 2: Drop the Length Normalisation

Set `B = 0` and search "kernel scheduler". Add a 5,000-word note that mentions "kernel"
twenty times. Where does it rank?

**Hint:** Without normalisation a long note collects term frequency by sheer size and rises
above a short note whose title *is* the topic.

## Challenge 3: Trust the mtime Alone

Change the cache check to compare only `mtime`. Then edit a file and restore its old
timestamp with `os.utime`. Does the index notice? What if you compare only `size`?

**Hint:** Neither signal alone is enough. Tools that rewrite a file (sync clients, git
checkouts) can preserve one of them. Using both is cheap; a content hash would be exact but
means reading every file on every call, which defeats the point of the cache.
