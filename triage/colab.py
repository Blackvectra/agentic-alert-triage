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
