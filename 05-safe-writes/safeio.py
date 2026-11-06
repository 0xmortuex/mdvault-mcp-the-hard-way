"""Module 05: write to the vault without hurting it.

Four promises, each enforced in one small function:

  confine()       the path stays inside the vault, and never passes through a symlink
  atomic_write()  a crash mid-write leaves the old file or the new file, never half of one
  eol helpers     CRLF files stay CRLF; a BOM stays a BOM
  create/append/edit never overwrite by surprise, and say exactly what changed
"""

from __future__ import annotations

import os
import re
import tempfile


class VaultError(Exception):
    """An expected failure with a message written for the agent."""


BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def clean_rel(rel: str) -> str:
    """Validate a vault-relative path typed by a user or an agent. Returns it with '/' separators."""
    s = rel.replace("\\", "/").strip()
    if not s or s.startswith("/") or re.match(r"^[A-Za-z]:", s):
        raise VaultError(f"{rel!r} must be a path relative to the vault, like 'Projects/Plan.md'")
    parts = [p for p in s.split("/") if p not in ("", ".")]
    for p in parts:
        if p == "..":
            raise VaultError(f"{rel!r} contains '..'; paths must stay inside the vault")
        if p.startswith("."):
            raise VaultError(f"{rel!r}: names starting with '.' (.git, .obsidian) are off limits")
        if BAD_CHARS.search(p) or p != p.rstrip(" .") or p.split(".")[0].lower() in RESERVED:
            raise VaultError(f"{rel!r}: {p!r} is not a legal file name on Windows")
    return "/".join(parts)


def confine(root: str, rel: str) -> str:
    """Absolute path for `rel`, or VaultError if it could leave the vault.

    `root` must already be os.path.realpath()'d. realpath resolves every symlink (and
    Windows junction) in the path; if the answer is not exactly where we expected, a link
    is involved and we refuse. Simple to reason about: no links on a write path, ever.
    """
    parts = clean_rel(rel).split("/")
    target = os.path.join(root, *parts)
    if os.path.normcase(os.path.realpath(target)) != os.path.normcase(target):
        raise VaultError(f"{rel!r} goes through a symbolic link or junction; refusing to write there")
    return target


def atomic_write(path: str, data: bytes) -> None:
    """Temp file in the SAME folder (so the rename cannot cross file systems), fsync, replace."""
    fd, tmp = tempfile.mkstemp(prefix=".mdvault-", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())  # the bytes are on disk before the name points at them
        os.replace(tmp, path)  # atomic: readers see the old file or the new one
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def detect_eol(text: str) -> str:
    crlf = text.count("\r\n")
    return "\r\n" if crlf > text.count("\n") - crlf else "\n"


def to_eol(text: str, eol: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", eol)


def read_note(path: str) -> tuple[str, bool]:
    """(text, had_bom). Binary read so '\\r\\n' survives; invalid UTF-8 is an error, not a guess."""
    with open(path, "rb") as f:
        raw = f.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        return raw[3:].decode("utf-8") if bom else raw.decode("utf-8"), bom
    except UnicodeDecodeError as e:
        raise VaultError(f"{path} is not valid UTF-8; not touching it") from e


def write_note(path: str, text: str, bom: bool) -> None:
    atomic_write(path, (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


# -- the three write operations --------------------------------------------------------


def create_note(root: str, rel: str, content: str, overwrite: bool = False) -> str:
    rel = clean_rel(rel)
    rel = rel if rel.lower().endswith(".md") else rel + ".md"
    target = confine(root, rel)
    existed = os.path.exists(target)
    if existed and not overwrite:
        raise VaultError(f"{rel} already exists. Pass overwrite=true to replace it.")
    eol = detect_eol(read_note(target)[0]) if existed else "\n"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    atomic_write(target, to_eol(content if content.endswith("\n") or not content else content + "\n", eol).encode("utf-8"))
    return rel


def append_to_note(root: str, rel: str, text: str) -> None:
    target = confine(root, rel)
    if not os.path.isfile(target):
        raise VaultError(f"{rel} does not exist; use create_note")
    cur, bom = read_note(target)
    eol = detect_eol(cur)
    add = to_eol(text, eol)
    if cur and not cur.endswith("\n"):
        add = eol + add
    if not add.endswith("\n"):
        add += eol
    write_note(target, cur + add, bom)


def edit_note(root: str, rel: str, old: str, new: str, dry_run: bool = False) -> str:
    """Replace `old` with `new`. `old` must occur exactly once: ambiguity is an error."""
    if not old:
        raise VaultError("old_text is empty")
    target = confine(root, rel)
    cur, bom = read_note(target)
    eol = detect_eol(cur)
    old, new = to_eol(old, eol), to_eol(new, eol)  # the agent sends \n; the file may use \r\n
    n = cur.count(old)
    if n == 0:
        raise VaultError(f"old_text not found in {rel}")
    if n > 1:
        raise VaultError(f"old_text matches {n} places in {rel}; add surrounding text so it matches exactly once")
    updated = cur.replace(old, new)
    if not dry_run:
        write_note(target, updated, bom)
    return updated
