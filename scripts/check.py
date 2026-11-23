"""The one check, used both locally and in CI: fresh venv, install, lint, run every test.

    python scripts/check.py

A brand-new virtual environment means packages that happen to be installed
on your machine cannot hide a missing dependency (CI starts clean too).
Standard library only, so it runs on Windows, macOS, Linux and CI alike.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".check-venv"
INSTALL = ".[dev,report]"  # single source of truth for what the tests need


def main() -> int:
    if VENV.exists():
        shutil.rmtree(VENV)
    print(f"creating clean environment in {VENV.name}/", flush=True)
    venv.create(VENV, with_pip=True)
    python = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    steps = [
        [str(python), "-m", "pip", "install", "-q", "-e", INSTALL],
        [str(python), "-m", "ruff", "check", "."],  # lint first: fast, and catches leftovers
        [str(python), "-m", "pytest", "-q"],
    ]
    for cmd in steps:
        print("$", " ".join(cmd[2:]), flush=True)
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"check FAILED at: {' '.join(cmd[2:])}")
            return result.returncode
    print("check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
