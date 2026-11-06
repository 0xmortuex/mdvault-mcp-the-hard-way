# Break It: Safe Writes

## Challenge 1: Drop the Symlink Check

Delete the `realpath` comparison from `confine`. Run `main.py`. Which attack succeeds and
what ends up in the `outside` folder?

**Hint:** The traversal tests still pass, since they are string checks. Only the junction
test fails, and the file lands outside the vault. Every text-only path check has this
blind spot.

## Challenge 2: Write In Place

Replace `atomic_write` with `open(path, "wb").write(data)` and make the write fail halfway
(for example by raising inside a generator that feeds the file). What does the file
contain afterwards?

**Hint:** `open(..., "wb")` truncates the file *first*. A crash after that leaves an empty
note, which is the worst possible outcome, because the old content is gone and the new
content never arrived.

## Challenge 3: Text Mode

Read with `open(path, encoding="utf-8")` and write with `open(path, "w", encoding="utf-8")`.
Run the CRLF assertions in step 4. What does `git diff` look like for a one-line append to
a 500-line CRLF note?

**Hint:** On Windows the write translates `\n` to `\r\n`, on Linux it does not; read
translates `\r\n` to `\n` everywhere. The same code gives different bytes on different
machines. Binary I/O with explicit conversion is the only version that behaves the same
everywhere.
