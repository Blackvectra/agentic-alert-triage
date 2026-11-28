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


def test_c2_and_c3_fingerprints_differ_and_cover_their_code(monkeypatch):
    from triage import agent
    before = {c: agent.prompt_fingerprint(c) for c in ("B", "C", "C2", "C3")}
    assert before["C2"] != before["C3"]  # same prompt and tools, different code
    monkeypatch.setattr(agent, "MAX_PUSHBACKS", 3)  # a code-only change
    after = {c: agent.prompt_fingerprint(c) for c in ("B", "C", "C2", "C3")}
    assert after["C2"] != before["C2"] and after["C3"] != before["C3"]
    assert (after["B"], after["C"]) == (before["B"], before["C"])  # main configs untouched


def test_a_run_can_name_the_code_it_used():
    from triage.build import code_commit
    commit = code_commit()
    assert commit == "unknown" or len(commit.removesuffix("-dirty")) == 40
