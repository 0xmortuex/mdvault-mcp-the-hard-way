"""Module 03: index and ranking.

Builds the index of the sample vault, checks BM25 against a hand computation, and proves
the cache: a second run parses nothing, and touching one file re-parses exactly one.

Usage: python main.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import math
import os
import tempfile

from index import Index, tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.join(ROOT, "sample-vault"))
    vault = ap.parse_args().vault

    with tempfile.TemporaryDirectory() as tmp:
        cache = os.path.join(tmp, "cache.json")
        idx = Index(vault, cache)

        # 1. First run parses everything.
        st = idx.refresh()
        n = len(idx.notes)
        print(f"{n} notes: parsed {st.parsed}, from cache {st.from_cache}")
        assert st.parsed == n == 11 and st.from_cache == 0

        # 2. Notes with bad frontmatter are kept (searchable) but flagged.
        assert idx.notes["Bad Frontmatter.md"].fm_error is not None
        assert idx.search("bad frontmatter")[0][0] == "Bad Frontmatter.md"

        # 3. Search quality.
        top = idx.search("kernel scheduler")
        print("kernel scheduler ->", [(p, round(s, 2)) for p, s in top[:3]])
        assert top[0][0] == "Reading/Kernel Scheduler.md"  # title + body hits beat a passing mention
        assert idx.search("seker cicek")[0][0] == "Turkce/Şeker Notu.md"  # diacritics folded
        assert tokenize("Şeker İSTANBUL Işık") == ["seker", "istanbul", "isik"]
        assert idx.search("zzzzz") == []

        # 4. BM25 by hand for one term and one document must equal the library's number.
        term, doc = "paging", "Reading/Memory Notes.md"
        notes = list(idx.notes.values())
        df = sum(1 for x in notes if term in x.tf)
        idf = math.log(1 + (len(notes) - df + 0.5) / (df + 0.5))
        avg = sum(x.length for x in notes) / len(notes)
        d = idx.notes[doc]
        expected = idf * d.tf[term] * 2.2 / (d.tf[term] + 1.2 * (1 - 0.75 + 0.75 * d.length / avg))
        got = dict(idx.search(term))[doc]
        assert abs(got - expected) < 1e-12, (got, expected)

        # 5. The cache: a fresh Index object (a restarted server) parses nothing.
        idx2 = Index(vault, cache)
        st = idx2.refresh()
        print(f"restart: parsed {st.parsed}, from cache {st.from_cache}")
        assert st.parsed == 0 and st.from_cache == 11
        assert idx2.search("kernel scheduler") == idx.search("kernel scheduler")  # identical results

        # 6. Change one file (on a copy, never the sample vault): exactly one re-parse.
        copy = os.path.join(tmp, "vault")
        import shutil

        shutil.copytree(vault, copy)
        idx3 = Index(copy, os.path.join(tmp, "cache3.json"))
        idx3.refresh()
        target = os.path.join(copy, "Orphan.md")
        with open(target, "ab") as f:
            f.write(b"\nA brand new sentence about zebras.\n")
        st = idx3.refresh()
        assert st.parsed == 1 and st.from_cache == 10, st
        assert idx3.search("zebras")[0][0] == "Orphan.md"
        os.remove(target)
        st = idx3.refresh()
        assert st.removed == 1 and "Orphan.md" not in idx3.notes
        assert idx3.search("zebras") == []

        # 7. Tags: frontmatter and inline, nested.
        assert idx.notes["Projects/Beta/Beta Plan.md"].tags == ["beta/launch", "project"]

    print("module 03 ok")


if __name__ == "__main__":
    main()
