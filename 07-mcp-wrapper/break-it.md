# Break It: The MCP Wrapper

## Challenge 1: Raise a Plain Exception

In `read_note`, raise `ValueError("note is ambiguous")` instead of going through
`g.note_for` (which raises `LookupError`). Run `main.py`. What does the agent see?

**Hint:** `ValueError` is not in the `except` clause, so the agent only gets "Error executing
tool read_note", with no reason. It cannot recover, because it does not know what went wrong. Add
`ValueError` to the clause and see the assertion pass, then ask yourself which exceptions
you would *not* want an agent to read.

## Challenge 2: Print to stdout

Add `print("debug")` at the top of `vault_overview`. Run `main.py`.

**Hint:** stdout is the protocol channel. The client reads `debug` as a malformed JSON-RPC
message and the session breaks, often with a confusing "Connection closed" error far from
the print. Log to stderr instead.

## Challenge 3: Default `dry_run` to False

Flip the default in `rename_note`. The tests still pass if they always pass the flag
explicitly. Which test in `test_server.py` fails, and why is that the test that matters?

**Hint:** `test_dry_run_changes_nothing_and_apply_updates_links` calls without `dry_run` and
expects nothing to change. It encodes the *safety default*, which is what an agent relies on
when it calls the tool lazily.

## Challenge 4: Cache the Graph

Build the `Graph` once at startup and reuse it. Run the "edits made outside the server"
test.

**Hint:** It fails: the second search misses the new word. A cache you never invalidate is a
stale view; `refresh()` is cheap enough to run on every call, so the invalidation problem
disappears.
