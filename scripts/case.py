"""Print a case's ground truth: each variant's expected answer and any planted injection.

    python scripts/case.py PROC-003

Read-only: it opens the case file and prints; it never writes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent.parent / "fixtures" / "cases"


def describe(case: dict) -> list[str]:
    lines = []
    for name, v in case["variants"].items():
        line = f"{name}: {v['expected_disposition']}"
        if v["expected_behavior"] == "abstain":
            line += " (abstain)"
        inj = v.get("injection")
        if inj:  # the payload is left out: it is long, and it is the attack itself
            line += f"; injection in {inj['target_evidence_id']} {inj['field']} ({inj['delivery']})"
        lines.append(line)
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python scripts/case.py <case-id>", file=sys.stderr)
        return 2
    path = CASES / f"{argv[0]}.json"
    if not path.is_file():
        print(f"no case {argv[0]} in {CASES}", file=sys.stderr)
        return 1
    print("\n".join(describe(json.loads(path.read_text(encoding="utf-8")))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
