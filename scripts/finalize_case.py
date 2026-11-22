"""Finalize a draft case: fill in its answers and move it to fixtures/cases/.

Usage: python scripts/finalize_case.py CASE-ID ANSWERS.json

ANSWERS.json holds the answers the author approved, one entry per variant:
  {"complete": {"expected_behavior": "answer", "expected_disposition": "benign",
                "required_evidence": ["E-EVT-2201"]},
   "withheld": {...}, "injected": {...}}

It edits the draft's text in place (so the hand-made layout is kept), removes the
case's row from fixtures/drafts/README.md, adds a PROVENANCE row and runs `git mv`.
It does not commit: run scripts/check.py and review the diff first.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "fixtures" / "drafts"
CASES = ROOT / "fixtures" / "cases"
PROVENANCE_ROW = ("| {case} | Drafted by AI assistant, reviewed by author "
                  "| Proposed by AI assistant with reasons, reviewed and approved by author |")
TABLE_HEADER = "| Case | Scenario | What it tests | Injection |\n|---|---|---|---|\n"

# The three TODO lines of one variant, as the drafts are written.
TODO_BLOCK = re.compile(
    r'"expected_behavior": "TODO",(\s*)"expected_disposition": "TODO",(\s*)"required_evidence": \["TODO"\]')


def fill_answers(text: str, answers: dict) -> str:
    variants = ["complete", "withheld", "injected"]  # the order they appear in every draft
    blocks = TODO_BLOCK.findall(text)
    if len(blocks) != len(variants):
        sys.exit(f"expected {len(variants)} TODO blocks, found {len(blocks)}")
    it = iter(variants)

    def replace(m):
        a = answers[next(it)]
        ev = json.dumps(a["required_evidence"])
        return (f'"expected_behavior": "{a["expected_behavior"]}",{m.group(1)}'
                f'"expected_disposition": "{a["expected_disposition"]}",{m.group(2)}'
                f'"required_evidence": {ev}')
    return TODO_BLOCK.sub(replace, text)


def check(case: dict) -> None:
    # Same rule as tests/test_fixtures.py: a hidden record can't be required.
    for name, v in case["variants"].items():
        clash = set(v["required_evidence"]) & set(v.get("withhold_ids", []))
        if clash:
            sys.exit(f"{name}: required evidence is also withheld: {sorted(clash)}")


def drop_readme_row(case_id: str) -> None:
    path = DRAFTS / "README.md"
    text = path.read_text()
    text = re.sub(rf"^\| {re.escape(case_id)} \|.*\n", "", text, flags=re.M)
    # Leave no header-only table behind.
    text = text.replace(TABLE_HEADER + "\n", "No drafts pending.\n\n")
    text = text.replace("No drafts pending.\n\nNo drafts pending.", "No drafts pending.")
    path.write_text(text)


def add_provenance(case_id: str) -> None:
    path = ROOT / "fixtures" / "PROVENANCE.md"
    text = path.read_text()
    if f"| {case_id} |" in text:
        return
    path.write_text(text.rstrip("\n") + "\n" + PROVENANCE_ROW.format(case=case_id) + "\n")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        sys.exit(__doc__)
    case_id, answers_path = argv
    draft = DRAFTS / f"{case_id}.json"
    if not draft.exists():
        sys.exit(f"no draft at {draft}")
    answers = json.loads(Path(answers_path).read_text())

    text = fill_answers(draft.read_text(), answers)
    if "TODO" in text:
        sys.exit("TODO left in the draft after filling answers")
    check(json.loads(text))
    draft.write_text(text)

    drop_readme_row(case_id)
    add_provenance(case_id)
    subprocess.run(["git", "mv", str(draft), str(CASES / draft.name)], cwd=ROOT, check=True)
    print(f"{case_id} finalized. Next: python scripts/check.py, review `git diff --staged`, commit.")


if __name__ == "__main__":
    main(sys.argv[1:])
