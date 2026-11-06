"""Module 05: safe writes.

Attacks the write functions on a COPY of the sample vault: path traversal, symlink and
junction escapes, a crash in the middle of a write, CRLF files, overwrite, ambiguous edits.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile

import safeio
from safeio import VaultError, append_to_note, atomic_write, confine, create_note, edit_note

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tree(root: str) -> dict[str, bytes]:
    out = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            with open(os.path.join(dp, fn), "rb") as f:
                out[os.path.relpath(os.path.join(dp, fn), root)] = f.read()
    return out


def raises(fn, *needles: str) -> None:
    try:
        fn()
    except VaultError as e:
        for n in needles:
            assert n in str(e), (n, str(e))
    else:
        raise AssertionError("expected a VaultError")


def link_dir(link: str, target: str) -> bool:
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":  # a junction needs no special privilege
        return subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True).returncode == 0
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    src = ap.parse_args().vault

    with tempfile.TemporaryDirectory() as tmp:
        vault = os.path.realpath(os.path.join(tmp, "vault"))
        shutil.copytree(src, vault)
        outside = os.path.join(tmp, "outside")
        os.makedirs(outside)
        with open(os.path.join(outside, "secret.md"), "w", encoding="utf-8") as f:
            f.write("top secret\n")
        before = tree(vault)

        # 1. Paths that must never be accepted. Nothing is created anywhere.
        for bad in ["../escape.md", "a/../../escape.md", "/etc/passwd", "C:\\Windows\\x.md", ".git/config",
                    ".obsidian/app.json", "bad:name.md", "CON.md", "trailing."]:
            raises(lambda bad=bad: create_note(vault, bad, "x", overwrite=True))
        assert tree(vault) == before
        assert not os.path.exists(os.path.join(tmp, "escape.md"))
        print("1. traversal and hidden paths refused")

        # 2. A symlink / junction inside the vault that points outside.
        if link_dir(os.path.join(vault, "Linked"), outside):
            raises(lambda: create_note(vault, "Linked/new.md", "pwn"), "link")
            raises(lambda: create_note(vault, "Linked/secret.md", "pwn", overwrite=True), "link")
            raises(lambda: append_to_note(vault, "Linked/secret.md", "pwn"), "link")
            with open(os.path.join(outside, "secret.md"), encoding="utf-8") as f:
                assert f.read() == "top secret\n"
            assert os.listdir(outside) == ["secret.md"]
            print("2. symlink/junction escape refused; the outside folder is untouched")
            os.rmdir(os.path.join(vault, "Linked")) if os.name == "nt" else os.unlink(os.path.join(vault, "Linked"))
        else:
            print("2. (skipped: this machine cannot create symlinks or junctions)")

        # 3. Atomic: make os.replace fail halfway. The file keeps its old bytes, no temp file is left.
        target = os.path.join(vault, "Orphan.md")
        with open(target, "rb") as f:
            old_bytes = f.read()
        real_replace = os.replace

        def boom(*a, **k):
            raise OSError("disk exploded")

        os.replace = boom
        try:
            try:
                atomic_write(target, b"NEW CONTENT")
            except OSError as e:
                assert "disk exploded" in str(e)
            else:
                raise AssertionError("expected OSError")
        finally:
            os.replace = real_replace
        with open(target, "rb") as f:
            assert f.read() == old_bytes
        assert not [n for n in os.listdir(vault) if n.startswith(".mdvault-")]
        print("3. a failed write leaves the original file and no temp file")

        # 4. CRLF stays CRLF. The Beta Plan note uses \r\n; the agent sends \n.
        beta = "Projects/Beta/Beta Plan.md"
        with open(os.path.join(vault, beta), "rb") as f:
            beta_before = f.read()
        assert beta_before.count(b"\n") == beta_before.count(b"\r\n")
        append_to_note(vault, beta, "- appended line\n- another")
        with open(os.path.join(vault, beta), "rb") as f:
            beta_after = f.read()
        assert beta_after == beta_before + b"- appended line\r\n- another\r\n"
        edit_note(vault, beta, "# Beta Plan\n\n^b1 paragraph", "# Beta Plan\n\nRewritten paragraph")
        with open(os.path.join(vault, beta), "rb") as f:
            beta_edited = f.read()
        assert b"Rewritten paragraph" in beta_edited and beta_edited.count(b"\n") == beta_edited.count(b"\r\n")
        print("4. CRLF file stays CRLF through append and edit")

        # 5. No surprise overwrite.
        raises(lambda: create_note(vault, "Home", "x"), "already exists", "overwrite=true")
        with open(os.path.join(vault, "Home.md"), "rb") as f:
            assert f.read() == before["Home.md"]
        create_note(vault, "Ideas/New Idea", "hello")
        with open(os.path.join(vault, "Ideas", "New Idea.md"), "rb") as f:
            assert f.read() == b"hello\n"
        print("5. existing notes are never overwritten without overwrite=true")

        # 6. Edits must match exactly once; the error says how to fix it.
        raises(lambda: edit_note(vault, "Home.md", "[[", "(("), "matches", "exactly once")
        raises(lambda: edit_note(vault, "Home.md", "no such text", "x"), "not found")
        updated = edit_note(vault, "Home.md", "Welcome.", "Hello.", dry_run=True)
        assert "Hello." in updated
        with open(os.path.join(vault, "Home.md"), "rb") as f:
            assert f.read() == before["Home.md"]  # dry run wrote nothing
        edit_note(vault, "Home.md", "Welcome.", "Hello.")
        with open(os.path.join(vault, "Home.md"), "rb") as f:
            assert f.read() == before["Home.md"].replace(b"Welcome.", b"Hello.")
        print("6. edits are exact-once, with a dry run")

        # 7. A note that is not UTF-8 is reported and left alone.
        with open(os.path.join(vault, "latin.md"), "wb") as f:
            f.write(b"caf\xe9\n")
        raises(lambda: edit_note(vault, "latin.md", "caf", "x"), "UTF-8")
        with open(os.path.join(vault, "latin.md"), "rb") as f:
            assert f.read() == b"caf\xe9\n"
        print("7. non-UTF-8 note untouched")

        assert confine(vault, "New/Sub/x.md").startswith(vault)
        assert safeio.detect_eol("a\r\nb\r\n") == "\r\n" and safeio.detect_eol("a\nb\n") == "\n"

    print("module 05 ok")


if __name__ == "__main__":
    main()
