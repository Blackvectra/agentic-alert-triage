"""Read JSON Lines files (one JSON object per line). Standard library only."""
from __future__ import annotations

import json
from pathlib import Path


def read_jsonl(path) -> list[dict]:
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
