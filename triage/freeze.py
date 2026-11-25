"""Step 6 freeze: record and check the prompt and fixture hashes the held-out run must use.

    python -m triage.freeze            # check: exit 1 if anything changed since the freeze
    python -m triage.freeze --write    # record the current hashes (only when the user asks)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from triage.agent import EXPLORATORY_CONFIGS, MAIN_CONFIGS, prompt_fingerprint

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ROOT / "FROZEN.json"
CASES = ROOT / "fixtures" / "cases"
CONFIGS = MAIN_CONFIGS + EXPLORATORY_CONFIGS  # C2 frozen after its dev run (ADR 0012)


def _fixtures_sha256(cases: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(cases.glob("*.json")):
        h.update(f.name.encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))  # same hash after a Windows checkout
    return h.hexdigest()


def current(cases: Path = CASES) -> dict:
    return {"prompts": {c: prompt_fingerprint(c) for c in CONFIGS}, "fixtures": _fixtures_sha256(cases)}


def mismatches(frozen: Path = FROZEN, cases: Path = CASES) -> list[str]:
    """Names of what differs from the freeze: prompt configs, then "fixtures"."""
    want, have = json.loads(frozen.read_text()), current(cases)
    out = [c for c in CONFIGS if want["prompts"].get(c) != have["prompts"][c]]
    return out + (["fixtures"] if want["fixtures"] != have["fixtures"] else [])


def main(argv=None) -> int:
    if "--write" in (argv if argv is not None else sys.argv[1:]):
        FROZEN.write_text(json.dumps(current(), indent=2) + "\n")
        print(f"wrote {FROZEN.name}")
        return 0
    bad = mismatches()
    print(f"changed since the freeze: {', '.join(bad)}" if bad else "matches the freeze")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
