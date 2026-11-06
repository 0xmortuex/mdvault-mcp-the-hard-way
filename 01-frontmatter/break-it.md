# Break It: Frontmatter

## Challenge 1: The Colon in the Title

Add `title: Notes: part 2` to a note's frontmatter and run `main.py`. What does the parser
return for `title`? Is that what YAML itself would do?

**Hint:** The regex splits on the first `:` followed by a space, so the value is
`Notes: part 2`. Real YAML rejects an unquoted `: ` inside a plain scalar. Decide whether
your tool should be as strict as YAML (and refuse notes Obsidian is happy with) or more
forgiving. The real server follows YAML and reports the line.

## Challenge 2: Round-Trip It

Replace `set_scalar` with `parse_yaml` followed by a hand-written `dump`. Run the byte
comparison in `main.py`. List everything that changed.

**Hint:** Comments, the run of spaces before `# still thinking`, list indentation, and any
quoting all change. Each is harmless alone; together they make every edit a noisy diff in
the user's git history.

## Challenge 3: The Horizontal Rule

Make a note whose first line is `---`, then ordinary text, then another `---` further
down as a divider. What does `split_frontmatter` return, and why is that a bug in the
note, not the parser?

**Hint:** It is YAML as far as any frontmatter reader can tell. `parse_yaml` will fail with
a line number, which is the right outcome: the note shows up in the "unparseable" list
instead of being silently mis-indexed.
