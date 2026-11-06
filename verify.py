"""Run every module the way CI does.

Each module's main.py is run as a subprocess and must exit 0; main.py checks its own
results with assert, so a chapter whose code drifts out of sync with what its README
claims fails here. Module 07 additionally runs its pytest file over a real stdio MCP
connection.

Usage: python verify.py            # all modules
       python verify.py 03 06      # just these
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd: list[str], cwd: str) -> tuple[bool, str]:
    try:
        # The modules print Turkish names; a Windows console defaults to cp1252 and would crash.
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=cwd, encoding="utf-8", errors="replace", env=env)
    except subprocess.TimeoutExpired:
        return False, "timed out after 300s"
    return proc.returncode == 0, proc.stdout + proc.stderr


def main() -> int:
    wanted = sys.argv[1:]
    modules = sorted(
        d for d in os.listdir(ROOT)
        if os.path.isfile(os.path.join(ROOT, d, "main.py")) and (not wanted or any(d.startswith(w) for w in wanted))
    )
    if not modules:
        print("no modules matched")
        return 1
    failed = []
    for m in modules:
        cwd = os.path.join(ROOT, m)
        start = time.monotonic()
        ok, out = run([sys.executable, "main.py"], cwd)
        if ok and os.path.isfile(os.path.join(cwd, "test_server.py")):
            ok, out2 = run([sys.executable, "-m", "pytest", "-q", "test_server.py"], cwd)
            out += out2
        print(f"{'PASS' if ok else 'FAIL'}  {m}  ({time.monotonic() - start:.1f}s)")
        if not ok:
            failed.append(m)
            print("    " + out.strip().replace("\n", "\n    "))
    print(f"\n{len(modules) - len(failed)}/{len(modules)} modules verified")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
