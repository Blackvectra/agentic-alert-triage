"""Which commit of this code a run used, so every result can be traced back to its code.

In a zip made by scripts/make_colab_zip.py, `git archive` writes the commit into COMMIT below
(the export-subst rule in .gitattributes). In a git checkout, git is asked instead; "-dirty"
means there were uncommitted changes, so the commit alone does not describe the code.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

COMMIT = "$Format:%H$"  # replaced by git archive; left as is in a checkout
ROOT = Path(__file__).resolve().parent.parent


def code_commit() -> str:
    if not COMMIT.startswith("$Format"):
        return COMMIT
    try:
        def git(*args):
            return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                                  text=True).stdout.strip()
        return git("rev-parse", "HEAD") + ("-dirty" if git("status", "--porcelain") else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
