# Module 07: The MCP Wrapper and Tests

## The Concept

Modules 01-06 built a library. This module turns it into something an agent can use: an
[MCP](https://modelcontextprotocol.io) server over stdio. Claude Desktop or Claude Code
starts `python server.py --vault ...` as a subprocess and speaks JSON-RPC to it on
stdin/stdout. The tools are the whole interface.

```
agent (Claude)  <-- JSON-RPC over stdio -->  server.py  -->  index, graph, rename, safeio
```

Because stdout carries the protocol, **a server must never `print()`**. The `mcp` package
handles that; do not add debugging output to stdout.

## Six tools, not sixty

An agent sees every tool's name and description on every turn. Each one costs context
and each is a chance to pick the wrong one. The mini server has six:

| tool | why it exists |
|------|----------------|
| `vault_overview` | the agent's first call: what is here, what is broken |
| `search_notes` | find by meaning of words |
| `read_note` | read one note, by path or name or `[[wikilink]]` |
| `backlinks` | follow the graph |
| `create_note` | the safest write |
| `rename_note` | the most valuable and riskiest write |

(The full server has ten: it adds outgoing links, tag/frontmatter queries, a broken-link
report, `append_to_note` with a daily-note helper, and `edit_note`.)

## The description is the manual

```python
@tool
def rename_note(note: str, new_name: str, dry_run: bool = True) -> str:
    """Rename or move a note and update every link to it. dry_run defaults to TRUE and lists
    every file and link that would change; call again with dry_run=false to apply."""
```

The docstring becomes the tool description and the type hints become its JSON schema. An
agent only knows what these say. Notice what the description does:

- says what happens and what the default is;
- tells the agent the *next step* (call again with `dry_run=false`);
- puts the safe behaviour in the default, so the lazy call is the safe call.

`main.py` asserts every description is non-trivial.

## Errors are instructions

By default `MCPServer` hides the text of an exception from the agent, because a stack trace
may contain secrets. A bare "Error executing tool read_note" tells the agent nothing. The
fix is one decorator:

```python
except (VaultError, LookupError, OSError) as e:
    raise ToolError(str(e)) from e
```

`ToolError` is the one exception type whose message reaches the agent. We convert only the
failures we *expect*: a bad path, an ambiguous name, an existing file. A bug (say, a
`TypeError`) is not converted, so it stays hidden from the agent but shows in the server log,
where you can fix it.

Compare what the agent now reads:

```
'Meeting Notes' is ambiguous; use the full path of one of: Areas/Meeting Notes.md, Projects/Meeting Notes.md
Home.md already exists. Pass overwrite=true to replace it.
```

Each says what went wrong and what to do. An agent can act on that without a human.

## Fresh state on every call

```python
def graph() -> Graph:
    _index.refresh()          # stat every file, re-parse only what changed
    return Graph(_index.notes, list_attachments(_root))
```

Each tool starts with `graph()`. A note edited in Obsidian between two calls is visible on
the next one; there is no stale in-memory copy to get out of sync. `test_server.py` proves it
by appending to a file behind the server's back.

## Testing it for real

The tests in `test_server.py` and `main.py` do not call the Python functions. They start
the actual server as a subprocess and talk to it with the real MCP client:

```python
params = StdioServerParameters(command=sys.executable, args=["server.py", "--vault", vault])
async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
    await session.initialize()
    result = await session.call_tool("rename_note", {...})
```

That exercises everything a unit test would skip: the JSON schema generated from your
type hints, argument parsing, the process starting, stdout staying clean, and `is_error`
reaching the client. It is also where a missing import (my first run: `graph` imported
before the path was set up) shows up as "Connection closed".

What the tests check:

1. the tool list is exactly the six, each documented;
2. a rename dry-run leaves every byte alone, and the real run changes only the link;
3. every kind of expected failure arrives as an error *with its advice*;
4. edits made outside the server are visible on the next call.

## Run It

```
python main.py                 # a scripted session with assertions
python -m pytest test_server.py
```

## What You Built

A server that lets an AI search, read, link-walk, create and safely refactor a folder of
notes: under 1,000 lines in total, comments included. The full [mdvault-mcp](https://github.com/0xmortuex/mdvault-mcp)
adds the rest of the YAML grammar, frontmatter queries, a persistent SQLite cache, an
inverted index, `append_to_note`/`edit_note`, nested-folder and ambiguity handling in
renames, a read-only mode, and 130+ tests including a 5,000-note vault. Every idea in it
is in the six modules you just read.
