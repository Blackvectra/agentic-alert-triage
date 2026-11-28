"""C4 through the real run loop (ADR 0014): C3 plus four guards enforced in code."""
import json

from triage import agent
from triage.agent import Final, ScriptedModel, ToolCall, run_case
from triage.fixtures import build_view, load_cases

CASE = next(c for c in load_cases("dev") if c["case_id"] == "AUTH-001")
USER, IP1, IP2 = "jdoe@example.org", "198.51.100.23", "203.0.113.77"  # AUTH-001's alert entities
FULL = [ToolCall("entity_lookup", {"id": USER}), ToolCall("entity_lookup", {"id": IP1}),
        ToolCall("entity_lookup", {"id": IP2}), ToolCall("event_search", {"user": USER}),
        ToolCall("event_search", {"src_ip": IP1}), ToolCall("event_search", {"src_ip": IP2})]


def _final(disposition="true_positive", evidence_ids=(), actions=()):
    return Final(json.dumps({"disposition": disposition, "abstain": disposition == "needs_more_info",
                             "summary": "s", "claims": [{"text": "c", "evidence_ids": list(evidence_ids)}],
                             "proposed_actions": list(actions)}))


def _run(script, variant="complete", case=CASE):
    return run_case(case, variant, "C4", ScriptedModel(script), build_view(case, variant))


def test_c4_is_registered_with_c3s_prompt_tools_and_coverage_rule():
    assert agent.PROMPTS["C4"] == agent.PROMPTS["C3"] and agent.tools_for("C4") == agent.tools_for("B")
    assert "C4" in agent.EXPLORATORY_CONFIGS and "C4" in agent.GUARDED and "C4" in agent.C2_FAMILY
    assert agent.LAYER_2["C4"] is agent.LAYER_2["C3"]
    assert agent.prompt_fingerprint("C4") != agent.prompt_fingerprint("C3")


def test_c4_keeps_c3s_layers():
    log = _run([_final()] + FULL + [_final(evidence_ids=["E-EVT-001"])])
    assert log["c2_pushbacks"] == 1 and log["c2_check"]["outcome"] == "accepted"
    assert "c2_injection_flags" in log and log["error"] is None


# Guard 1, missing-evidence abstain. AUTH-001's withheld variant has no directory record for the user.
def test_withheld_evidence_turns_a_verdict_into_a_repair_request():
    log = _run(FULL + [_final(evidence_ids=["E-EVT-001"]), _final("needs_more_info")], variant="withheld")
    assert log["c4_empty_lookups"] == [f"entity_lookup id={USER} found nothing"]
    assert log["c2_check"]["outcome"] == "repaired" and log["output"]["disposition"] == "needs_more_info"


def test_a_verdict_kept_despite_the_gap_falls_back_to_needs_more_info():
    log = _run(FULL + [_final(evidence_ids=["E-EVT-001"])] * 2, variant="withheld")
    assert log["c2_check"]["outcome"] == "fallback" and log["output"] == agent.c4.FALLBACK


def test_complete_evidence_has_no_gap():
    log = _run(FULL + [_final(evidence_ids=["E-EVT-001"])])
    assert log["c4_empty_lookups"] == [] and log["c2_check"]["outcome"] == "accepted"
