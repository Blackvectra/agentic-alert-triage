"""C2's layer-3 answer checks (ADR 0012)."""
import inspect
import json
from pathlib import Path

import triage.c2 as c2
from triage.c2 import answer_problems, known_bad_indicators


def _answer(claim_ids, action_ids=()):
    return {
        "disposition": "true_positive", "abstain": False, "summary": "",
        "claims": [{"text": "x", "evidence_ids": list(claim_ids)}],
        "proposed_actions": [{"action": "y", "evidence_ids": list(action_ids)}] if action_ids else [],
    }


def test_citations_that_were_retrieved_pass():
    assert answer_problems(_answer(["E-1"], ["E-2"]), retrieved_ids={"E-1", "E-2"}) == []


def test_a_claim_citing_an_id_never_retrieved_is_a_problem():
    problems = answer_problems(_answer(["E-1", "E-9"]), retrieved_ids={"E-1"})
    assert problems == ["cited E-9, which no tool returned in this run"]


def test_an_action_citing_the_alert_id_is_a_problem():
    problems = answer_problems(_answer(["E-1"], ["ALERT-7"]), retrieved_ids={"E-1"})
    assert problems == ["cited ALERT-7, which no tool returned in this run"]


# --- Known-bad indicators: "benign" is rejected while one is in the retrieved evidence ---
BENIGN = {"disposition": "benign", "abstain": False, "summary": "", "claims": [], "proposed_actions": []}


def test_each_indicator_is_found():
    records = [
        {"evidence_id": "E-1", "type": "signin", "failure_reason": "MFA denied by user"},
        {"evidence_id": "E-2", "type": "signin", "mfa": "not applied (legacy authentication)"},
        {"evidence_id": "E-3", "type": "mailbox_rule_created"},
        {"evidence_id": "E-4", "type": "process_start", "command_line": "rundll32 comsvcs.dll, MiniDump 724 x"},
        {"evidence_id": "E-5", "type": "file_created", "path": "C:\\Users\\Public\\m.dmp"},
        {"evidence_id": "E-6", "type": "audit_setting_changed", "new_value": "disabled"},
    ]
    assert [eid for eid, _ in known_bad_indicators(records)] == ["E-1", "E-2", "E-3", "E-4", "E-5", "E-6"]


def test_ordinary_records_hold_no_indicator():
    records = [{"evidence_id": "E-1", "type": "signin", "mfa": "satisfied (push)", "result": "success"},
               {"evidence_id": "E-2", "type": "audit_setting_changed", "new_value": "enabled"}]
    assert known_bad_indicators(records) == []


def test_benign_with_a_bad_sign_retrieved_is_a_problem():
    records = [{"evidence_id": "E-3", "type": "mailbox_rule_created"}]
    assert answer_problems(BENIGN, retrieved_ids={"E-3"}, records=records) == [
        "answered benign, but E-3 shows a known-bad sign: new inbox rule (persistence)"]


def test_true_positive_with_a_bad_sign_is_fine():
    records = [{"evidence_id": "E-3", "type": "mailbox_rule_created"}]
    answer = dict(BENIGN, disposition="true_positive")
    assert answer_problems(answer, retrieved_ids={"E-3"}, records=records) == []


def test_indicator_code_names_no_case_and_no_expected_answer():
    # ADR 0012: the list comes from the guides, never from the cases or their answers.
    source = inspect.getsource(c2)
    case_ids = [json.loads(p.read_text(encoding="utf-8"))["case_id"]
                for p in Path("fixtures/cases").glob("*.json")]
    assert not [cid for cid in case_ids if cid in source]
    assert "expected_" not in source  # the fixtures' answer fields, e.g. expected_disposition
