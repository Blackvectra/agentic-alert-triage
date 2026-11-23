"""C2's layer-3 answer checks (ADR 0012)."""
from triage.c2 import answer_problems


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
