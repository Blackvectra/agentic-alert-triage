"""Colab helpers. Standard library only."""
from __future__ import annotations

import zipfile
from pathlib import Path


def unpack_latest_zip(content_dir) -> str | None:
    """Unpack the newest agentic-alert-triage*.zip in content_dir over the project folder.

    Always unpacking means a new upload replaces old code even when the folder
    already exists (a reused Colab session once ran stale code). Files the zip
    does not contain, such as earlier results in runs/, are kept. Returns the
    commit id stored in the zip by git archive, or None if there is no zip.
    """
    zips = sorted(Path(content_dir).glob("agentic-alert-triage*.zip"), key=lambda p: p.stat().st_mtime)
    if not zips:
        return None
    with zipfile.ZipFile(zips[-1]) as z:
        z.extractall(content_dir)  # the zip holds one folder: agentic-alert-triage/
        return z.comment.decode() or "unknown"


def copy_clone_over_project(clone_dir, project_dir) -> str:
    """Copy a git clone over the project folder and return its commit id.

    For editors that cannot show Colab's upload widget (VS Code and others):
    the notebook clones the repo on the Colab machine, then calls this. Like
    unpack_latest_zip, files the clone does not have, such as runs/, are kept.
    The .git folder is left out so the project folder stays a plain copy.
    """
    import shutil
    import subprocess

    commit = subprocess.run(["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    shutil.copytree(clone_dir, project_dir, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git"))
    return commit


def save_run_copy(run_dir, drive_dir) -> Path:
    """Copy a run folder into drive_dir and return where it went. Never overwrites.

    Two runs with the same settings (two dev runs of the same configs, say) get the same folder
    name, and a new Colab session starts with an empty disk, so copying over the old folder
    would replace the earlier run's logs. A name already taken gets _2, _3, ... instead.
    """
    import shutil

    run_dir, drive_dir = Path(run_dir), Path(drive_dir)
    dest, n = drive_dir / run_dir.name, 1
    while dest.exists():
        n += 1
        dest = drive_dir / f"{run_dir.name}_{n}"
    shutil.copytree(run_dir, dest)
    return dest
