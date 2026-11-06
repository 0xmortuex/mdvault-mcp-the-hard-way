# Break It: Link Parsing

## Challenge 1: Delete the Code Instead of Masking It

Change `mask_code` to remove fenced code rather than replace it with spaces. Run
`main.py`. Which assertion fails first, and why?

**Hint:** The span check (`FIXTURE[tstart:tend]`) fails for every link after the first code
block. The spans were computed on shorter text. A rename built on those spans would corrupt
the file, and corrupt it *silently*, because the splice still succeeds.

## Challenge 2: A Link With a Bracket in the Text

Try `[a [b] c](note.md)` and `[[Note]](x.md)`. What does the parser return? Is that a bug
in the regex, or a reasonable limit?

**Hint:** Nested brackets in link text are legal Markdown that the simple regex does not
handle. Decide how much a regex should take on before you reach for a real parser, and
who pays when the parser is wrong. Here the cost of a missed link is a rename that leaves
one stale link; the real server's `broken_links` tool shows it afterwards.

## Challenge 3: The Pipe in a Table

Put `| [[Note\|alias]] |` in a note. Remove the backslash handling and look at the
target. What does the rename in Module 06 then write?

**Hint:** The target becomes `Note\`, which resolves to nothing, so the link looks broken
and a rename would never update it.
