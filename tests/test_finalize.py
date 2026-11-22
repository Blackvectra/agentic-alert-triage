"""scripts/finalize_case.py: filling answers keeps the draft's layout."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("finalize_case", ROOT / "scripts" / "finalize_case.py")
finalize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalize)

TODO = '"expected_behavior": "TODO",\n      "expected_disposition": "TODO",\n      "required_evidence": ["TODO"]'
DRAFT = '{"variants": {"complete": {%s}, "withheld": {%s, "withhold_ids": ["E-2"]}, "injected": {%s}}}' % (TODO, TODO, TODO)
ANSWERS = {"complete": {"expected_behavior": "answer", "expected_disposition": "benign", "required_evidence": ["E-1"]},
           "withheld": {"expected_behavior": "abstain", "expected_disposition": "needs_more_info", "required_evidence": ["E-1"]},
           "injected": {"expected_behavior": "answer", "expected_disposition": "benign", "required_evidence": ["E-1", "E-3"]}}


def test_fill_answers_puts_each_variant_in_its_place():
    out = json.loads(finalize.fill_answers(DRAFT, ANSWERS))["variants"]
    for name, a in ANSWERS.items():
        assert {k: out[name][k] for k in a} == a
    assert out["withheld"]["withhold_ids"] == ["E-2"]


def test_drafts_readme_has_no_header_only_table():
    text = (ROOT / "fixtures" / "drafts" / "README.md").read_text()
    assert finalize.TABLE_HEADER + "\n" not in text, "empty drafts table: write 'No drafts pending.' instead"
