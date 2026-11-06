"""Module 06: the rename refactor.

Runs dry-runs and real renames on a COPY of the sample vault, and after each one re-parses
the whole vault in a fresh index to prove that every link still resolves to the same note.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile

from rename import apply_plan, plan_rename, render  # importing rename puts modules 01-05 on sys.path
from graph import build  # noqa: E402
from safeio import VaultError  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tree(root: str) -> dict[str, bytes]:
    out = {}
    for dp, dn, fns in os.walk(root):
        for fn in fns:
            with open(os.path.join(dp, fn), "rb") as f:
                out[os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")] = f.read()
    return out


def resolution_map(root: str, cache: str) -> dict[tuple[str, int], tuple[str, str | None]]:
    """For every link in the vault: what does it resolve to? Built from scratch each time."""
    if os.path.exists(cache):
        os.unlink(cache)
    g = build(root, cache)
    return {(src, i): (r.status, r.target) for src, rs in g.out.items() for i, r in enumerate(rs)}


def check_preserved(before, after, old: str, new: str) -> None:
    """The oracle. Same links, same statuses, and each target is the same note under its new name."""
    rename = lambda p: new if p == old else p  # noqa: E731
    assert len(before) == len(after)
    for (src, i), (status, target) in before.items():
        a_status, a_target = after[(rename(src), i)]
        assert a_status == status, (src, i, status, a_status)
        assert a_target == (rename(target) if target else None), (src, i, target, a_target)


def do(root: str, tmp: str, ref: str, new_name: str, old_path: str, new_path: str):
    cache = os.path.join(tmp, "c.json")
    before = resolution_map(root, cache)
    g = build(root, cache)
    plan = plan_rename(root, g, ref, new_name)
    apply_plan(root, plan)
    after = resolution_map(root, cache)
    check_preserved(before, after, old_path, new_path)
    return plan


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    src = ap.parse_args().vault

    with tempfile.TemporaryDirectory() as tmp:
        vault = os.path.realpath(os.path.join(tmp, "vault"))
        shutil.copytree(src, vault)
        cache = os.path.join(tmp, "cache.json")
        original = tree(vault)

        # 1. The dry run: a full report, zero bytes written.
        g = build(vault, cache)
        plan = plan_rename(vault, g, "Beta Plan", "Beta Roadmap")
        print(render(plan, dry_run=True))
        assert tree(vault) == original
        assert set(plan.files) == {"Home.md", "Projects/Alpha/Alpha Plan.md"}
        assert sum(len(e) for e in plan.files.values()) == 3

        # 2. Apply it. Only the three link targets change; every other byte is identical.
        apply_plan(vault, plan)
        now = tree(vault)
        assert "Projects/Beta/Beta Plan.md" not in now
        assert now["Projects/Beta/Beta Roadmap.md"] == original["Projects/Beta/Beta Plan.md"]
        assert now["Home.md"] == original["Home.md"].replace(b"[[Beta Plan|the beta]]", b"[[Beta Roadmap|the beta]]")
        alpha = original["Projects/Alpha/Alpha Plan.md"]
        assert now["Projects/Alpha/Alpha Plan.md"] == alpha.replace(b"[[Beta Plan#^b1|beta block]]", b"[[Beta Roadmap#^b1|beta block]]").replace(
            b"../Beta/Beta%20Plan.md#top", b"../Beta/Beta%20Roadmap.md#top")
        check_preserved(resolution_map(shutil.copytree(src, os.path.join(tmp, "v2")), os.path.join(tmp, "c2.json")),
                        resolution_map(vault, cache), "Projects/Beta/Beta Plan.md", "Projects/Beta/Beta Roadmap.md")
        print("2. applied; links re-parsed in a fresh index all resolve to the same notes")

        # 3. A move to another folder: bare wikilinks need NO change, relative markdown links DO,
        #    and so do the moved note's own relative links.
        shutil.rmtree(vault)
        shutil.copytree(src, vault)
        before = tree(vault)
        do(vault, tmp, "Beta Plan", "Archive/Beta Plan", "Projects/Beta/Beta Plan.md", "Archive/Beta Plan.md")
        after = tree(vault)
        assert after["Home.md"] == before["Home.md"]  # [[Beta Plan]] still finds it by name
        assert b"../../Archive/Beta%20Plan.md#top" in after["Projects/Alpha/Alpha Plan.md"]
        assert b"../Projects/Alpha/Alpha%20Plan.md" in after["Archive/Beta Plan.md"]
        assert after["Archive/Beta Plan.md"].count(b"\n") == after["Archive/Beta Plan.md"].count(b"\r\n") > 0  # still CRLF
        print("3. move: relative links recomputed, CRLF preserved")

        # 4. Turkish names and a path-qualified wikilink, then the self-link in the note itself.
        shutil.rmtree(vault)
        shutil.copytree(src, vault)
        do(vault, tmp, "şeker notu", "Şeker Tarifi", "Turkce/Şeker Notu.md", "Turkce/Şeker Tarifi.md")
        home = tree(vault)["Home.md"].decode()
        assert "[[Şeker Tarifi]]" in home and "[[Şeker Tarifi#Tarif]]" in home
        shutil.rmtree(vault)
        shutil.copytree(src, vault)
        do(vault, tmp, "Projects/Alpha/Alpha Plan.md", "Alpha Roadmap", "Projects/Alpha/Alpha Plan.md", "Projects/Alpha/Alpha Roadmap.md")
        assert b"[[Alpha Roadmap#Goal]]" in tree(vault)["Projects/Alpha/Alpha Roadmap.md"]
        print("4. Turkish rename and self-link ok")

        # 5. Ambiguous links are reported, never rewritten.
        shutil.rmtree(vault)
        shutil.copytree(src, vault)
        before = tree(vault)
        g = build(vault, cache)
        plan = plan_rename(vault, g, "Areas/Meeting Notes.md", "Areas Standup")
        text = render(plan, dry_run=True)
        assert "NOT updated (ambiguous)" in text and "Home.md" in text
        apply_plan(vault, plan)
        assert tree(vault)["Home.md"] == before["Home.md"]
        print("5. ambiguous links reported and left alone")

        # 6. Refusals leave the vault untouched.
        shutil.rmtree(vault)
        shutil.copytree(src, vault)
        before = tree(vault)
        g = build(vault, cache)
        for ref, name, needle in [("Home", "Orphan", "already exists"), ("Home", "../out", "inside the vault"),
                                  ("Orphan", "Beta Plan", "another note"), ("Meeting Notes", "x", "ambiguous")]:
            try:
                plan_rename(vault, g, ref, name)
            except (VaultError, LookupError) as e:
                assert needle in str(e), (needle, str(e))
            else:
                raise AssertionError(f"expected a refusal for {ref!r} -> {name!r}")
        assert tree(vault) == before

        # 7. A file edited between planning and applying aborts the rename before anything moves.
        g = build(vault, cache)
        plan = plan_rename(vault, g, "Beta Plan", "Beta Renamed")
        with open(os.path.join(vault, "Home.md"), "ab") as f:
            f.write(b"\nsomeone else edited this\n")
        try:
            apply_plan(vault, plan)
        except VaultError as e:
            assert "changed while" in str(e)
        else:
            raise AssertionError("expected an abort")
        assert os.path.exists(os.path.join(vault, "Projects", "Beta", "Beta Plan.md"))
        assert b"[[Beta Plan#^b1|beta block]]" in tree(vault)["Projects/Alpha/Alpha Plan.md"]
        print("6-7. refusals and the concurrent-edit guard ok")

    print("module 06 ok")


if __name__ == "__main__":
    main()
