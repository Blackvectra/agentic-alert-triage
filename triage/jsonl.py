"""Read JSON Lines files (one JSON object per line). Standard library only."""
from __future__ import annotations

import json
import warnings
from pathlib import Path


def read_jsonl(path) -> list[dict]:
    """Every row in the file, skipping a half-written last line.

    Runs are appended one line at a time, so a disconnect can only cut off the last line.
    A bad line anywhere else is real damage and still raises.
    """
    lines = [x for x in Path(path).read_text().splitlines() if x.strip()]
    rows = [json.loads(x) for x in lines[:-1]]
    if lines:
        try:
            rows.append(json.loads(lines[-1]))
        except json.JSONDecodeError:
            warnings.warn(f"{path}: skipped a half-written last line (an interrupted run); "
                          "rerun with the same --out to redo it", stacklevel=2)
    return rows
