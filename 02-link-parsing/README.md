# Module 02: Link Parsing

## The Concept

Links are what turn a folder of files into a knowledge base. There are two syntaxes in
the wild and a vault usually mixes them:

```
[[Note]]                 wikilink: by name, not path
[[Note#Heading]]         ...to a heading
[[Note#^blockid]]        ...to a block
[[Note|shown text]]      ...with an alias
![[Note]]  ![[img.png]]  embed
[text](folder/Note.md)   markdown link: a relative path, maybe %20-encoded or <angled>
```

A parser has to answer two different questions, and this module answers both:

1. **What does the link say?** (target, heading, alias, embed or not)
2. **Where exactly is it in the file?** (the character span of the *target*)

Question 2 is what makes a safe rename possible in Module 06. If we know that characters
412 to 421 are the target `Beta Plan`, we can replace exactly those and nothing else.

## Regex vs a real Markdown parser

A full CommonMark parser does not know wikilinks, and Obsidian's own rules are looser than
CommonMark's. Two regexes plus one preprocessing step cover what real vaults contain:

```python
WIKI = re.compile(r"(!?)\[\[([^\[\]\n]*)\]\]")
MD   = re.compile(r"(!?)\[([^\]\n]*)\]\((<[^>\n]*>|[^)\s]*)\)")
```

The cost is a few known gaps (reference-style `[x]: path` definitions, raw HTML links).
The real server documents them under *Limitations* instead of pretending.

## Not every `[[...]]` is a link: mask the code

````
```
[[In A Fence]]
```
Use `[[inline code]]` to write a link.
````

Those are examples. `mask_code` replaces fenced and inline code with spaces: the same
length and the same newlines, so **an offset in the masked text is an offset in the real
text.** Removing the code would shift everything after it and break every span.

## Wikilink anatomy

For `[[Folder/Note#Intro|read this]]`:

- split the alias off at the first `|`: `Folder/Note#Intro` and `read this`;
- split the heading or block off at the first `#` or `^`: name `Folder/Note`, fragment
  `#Intro`. (Obsidian forbids `#` and `^` in file names, so the first one is always a
  delimiter);
- a backslash before the pipe (`[[Note\|alias]]`) is how you write a wikilink in a Markdown
  *table*, where an unescaped `|` would split the cell. We drop the backslash from the name.

`tstart` and `tend` are the span of the name only. The heading, alias and the brackets are
outside it, so replacing `text[tstart:tend]` keeps them automatically.

## Markdown link anatomy

`[t](my%20note.md#sec)` is a relative path with percent-encoding, and a fragment. We store
the *decoded* target (`my note.md`) for lookups but keep the span of the *raw* text, because
a rename must write it back in the style the author used.

Skipped on purpose: `https:`/`mailto:` (anything with a scheme), and `#anchor`-only links,
which point inside the same note.

## Tags

`#idea`, `#nested/tag`. The regex refuses `#2024` (a tag needs a non-digit), `text#nope`
(no word character before the `#`), `[[note#heading]]`, URL fragments, and anything in
code.

## Run It

```
python main.py
```

It checks a fixture with every tricky form, proves the spans, shows that masking preserves
offsets, rewrites a link by splicing, and counts the links in the sample vault. That count
was cross-checked against the full server's parser.

## What You Learned

- A link parser returns *spans*, not just values.
- Mask code instead of deleting it so offsets stay valid.
- Keep the raw target's span even when you store a decoded copy.

Next: indexing and ranking.
