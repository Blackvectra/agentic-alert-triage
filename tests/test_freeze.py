"""Step 6: the prompts and fixtures are frozen before the held-out run."""
import json

from triage import freeze


def test_prompts_and_fixtures_match_frozen_json():
    # Fails on any prompt, tool or case change. If the change is meant, the freeze is
    # broken on purpose: ask the user, then rerun `python -m triage.freeze --write`.
    assert freeze.mismatches() == []


def test_a_changed_case_file_is_reported(tmp_path):
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "X-001.json").write_text('{"a": 1}\n')
    frozen = tmp_path / "FROZEN.json"
    frozen.write_text(json.dumps(freeze.current(cases)))
    (cases / "X-001.json").write_text('{"a": 2}\n')
    assert freeze.mismatches(frozen, cases) == ["fixtures"]
