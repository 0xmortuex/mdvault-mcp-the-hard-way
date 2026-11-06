"""Module 01: split YAML frontmatter off a note and parse the part notes actually use.

A deliberately small subset: flat `key: value` lines, quoted strings, numbers,
booleans, null, inline lists `[a, b]` and block lists (`key:` then `- item` lines).
Anything fancier raises FrontmatterError with the line number instead of guessing.
"""

from __future__ import annotations

import re
from typing import Any


class FrontmatterError(ValueError):
    pass


def split_frontmatter(text: str) -> tuple[str | None, int]:
    """Return (the YAML between the fences, offset where the body starts).

    Frontmatter exists only if the FIRST line is `---` and a later line is `---`.
    Otherwise return (None, 0): the whole file is body.
    """
    first_nl = text.find("\n")
    if first_nl == -1 or text[:first_nl].rstrip() != "---":
        return None, 0
    pos = first_nl + 1
    while pos <= len(text):
        nl = text.find("\n", pos)
        end = len(text) if nl == -1 else nl
        if text[pos:end].rstrip() == "---":
            body_start = len(text) if nl == -1 else nl + 1
            return text[first_nl + 1 : pos], body_start
        if nl == -1:
            break
        pos = nl + 1
    return None, 0  # opening fence but no closing fence: not frontmatter


def strip_comment(line: str) -> str:
    """Cut a trailing ` # comment`, but not a # inside quotes."""
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def parse_scalar(s: str, lineno: int) -> Any:
    s = s.strip()
    if s == "" or s in ("~", "null"):
        return None
    if s in ("true", "false"):
        return s == "true"
    if s[0] in "\"'":
        if len(s) < 2 or s[-1] != s[0]:
            raise FrontmatterError(f"line {lineno}: unterminated quoted string")
        inner = s[1:-1]
        return inner.replace('\\"', '"') if s[0] == '"' else inner.replace("''", "'")
    if s[0] == "[":
        if not s.endswith("]"):
            raise FrontmatterError(f"line {lineno}: unterminated list (missing ']')")
        inner = s[1:-1].strip()
        return [parse_scalar(p, lineno) for p in inner.split(",")] if inner else []
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?\d+\.\d+", s):
        return float(s)
    return s  # dates stay strings: "2026-12-01" sorts correctly and needs no date type


def parse_yaml(raw: str, first_line: int = 2) -> dict[str, Any]:
    out: dict[str, Any] = {}
    open_key: str | None = None  # a `key:` with no value yet: a block list may follow
    for i, line in enumerate(raw.split("\n")):
        lineno = first_line + i
        line = line.rstrip("\r")
        content = strip_comment(line)
        if not content.strip():
            continue
        if content.lstrip().startswith("- "):
            if open_key is None:
                raise FrontmatterError(f"line {lineno}: list item with no key above it")
            if out[open_key] is None:
                out[open_key] = []
            out[open_key].append(parse_scalar(content.lstrip()[2:], lineno))
            continue
        if line.startswith((" ", "\t")):
            raise FrontmatterError(f"line {lineno}: nested maps are not supported by this mini parser")
        m = re.match(r"^([^:\s][^:]*?)\s*:(?:\s+(.*))?$", content)
        if not m:
            raise FrontmatterError(f"line {lineno}: expected `key: value`, got {content!r}")
        key, rest = m.group(1), m.group(2)
        if key in out:
            raise FrontmatterError(f"line {lineno}: duplicate key {key!r}")
        if rest is None or rest == "":
            out[key] = None  # null, unless `- item` lines follow
            open_key = key
        else:
            out[key] = parse_scalar(rest, lineno)
            open_key = None
    return out


def set_scalar(text: str, key: str, new_value: str) -> str:
    """Change `key: old` to `key: new_value` inside the frontmatter, touching nothing else.

    Spacing, the trailing comment and the line ending all survive, because we only
    replace the characters of the old value. This is why we never re-serialise.
    """
    raw, _ = split_frontmatter(text)
    if raw is None:
        raise FrontmatterError("note has no frontmatter")
    head_end = text.find("\n") + 1
    pattern = re.compile(rf"^({re.escape(key)}[ \t]*:[ \t]*)([^#\r\n]*?)([ \t]*(?:#[^\r\n]*)?)(\r?)$", re.MULTILINE)
    m = pattern.search(text, head_end, head_end + len(raw))
    if m is None:
        raise FrontmatterError(f"key {key!r} not found as a simple `key: value` line")
    return text[: m.start(2)] + new_value + text[m.end(2) :]
