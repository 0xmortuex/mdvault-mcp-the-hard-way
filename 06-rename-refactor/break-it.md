# Break It: The Rename Refactor

## Challenge 1: Edit Front to Back

In `apply_plan`, remove `sorted(..., key=lambda e: -e.start)` so edits apply in file order
(`Alpha Plan.md` has two edits). Run `main.py`.

**Hint:** The first edit changes the text length (`Beta Plan` to `Beta Roadmap` adds 4
characters), so the second edit's offsets now point 4 characters too early and the splice
lands in the wrong place. The oracle catches this immediately.

## Challenge 2: Skip the Moved Note's Own Links

Delete the `elif src == old and lk.kind == "md" ...` branch in `plan_rename`, then run the
"move to another folder" step. Which assertion fails, and what would the reader of the
moved note see?

**Hint:** The note's `[alpha](../Alpha/Alpha%20Plan.md)` link now points at a path that no
longer exists from `Archive/`. No other note changed, which is why this bug survives code
review: nothing in the *diff* looks wrong.

## Challenge 3: Guess the Twin

Make `plan_rename` rewrite ambiguous links to `old` too (treat them as pointing at it). Run
step 5. What happens to `Home.md`?

**Hint:** `[[Meeting Notes]]` in `Home.md` becomes a link to the renamed note. If its author
meant the *other* Meeting Notes, you have silently redirected a link, and there is no
error to find later.
