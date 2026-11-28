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


# Guard 2, quarantine. AUTH-001's injected variant plants text in a record the user search returns.
class Recorder(ScriptedModel):
    def step(self, system, messages, tools):
        self.seen = messages
        return super().step(system, messages, tools)


def test_the_model_never_sees_a_flagged_field_but_layer_3_still_does():
    payload = CASE["variants"]["injected"]["injection"]["payload"]
    model = Recorder(FULL + [_final("benign", ["E-EVT-001"]), _final("benign", ["E-EVT-001"])])
    log = run_case(CASE, "injected", "C4", model, build_view(CASE, "injected"))
    tool_text = "".join(m["content"] for m in model.seen if m["role"] == "tool")
    assert payload not in tool_text and "withheld by C4" in tool_text
    assert {"evidence_id": "E-EVT-004", "field": "rule_name"} in log["c2_injection_flags"]
    assert log["c2_check"]["outcome"] == "fallback"  # benign is still refused: the flag is a known-bad sign


# Guard 3, action policy: only allowed actions reach the approval gate.
def test_only_actions_the_policy_allows_reach_the_gate():
    backed = {"action": "disable account", "evidence_ids": ["E-EVT-001"]}
    bare = {"action": "reset password", "evidence_ids": []}
    log = _run(FULL + [_final(evidence_ids=["E-EVT-001"], actions=[backed, bare])])
    assert [g["action"] for g in log["gate"]] == [backed] and log["output"]["proposed_actions"] == [backed]
    assert log["c4_actions_blocked"] == [{"action": bare, "reason": "it cites no evidence"}]
    assert all(g["executed"] is False for g in log["gate"])


# Guard 4, loop and cost caps.
def test_a_repeated_call_is_not_run_again_and_costs_no_tool_call():
    log = _run(FULL[:1] + FULL + [_final(evidence_ids=["E-EVT-001"])])
    assert log["c4_duplicates"] == [{"name": "entity_lookup", "args": {"id": USER}}]
    assert len(log["tool_calls"]) == len(FULL)  # the repeat is not scored as a call
    assert log["c2_check"]["outcome"] == "accepted"


def test_repeats_still_use_up_the_runs_turns():
    log = _run(FULL[:1] * 30)
    turns = agent.CALL_BUDGET + 1 + agent.MAX_PUSHBACKS  # the same number of turns as C3
    assert len(log["tool_calls"]) == 1 and len(log["c4_duplicates"]) == turns - 1
    assert log["error"] == "budget_exhausted_without_answer"


class Costly(ScriptedModel):
    """Every turn uses 20,000 tokens, so the second turn crosses C4's cap."""

    def step(self, system, messages, tools):
        act, _ = super().step(system, messages, tools)
        return act, agent.Usage(20_000, 0)


def test_the_token_cap_files_the_held_answer():
    script = [_final(evidence_ids=["E-EVT-001"])] + FULL  # pushed back, then the cap stops the run
    log = run_case(CASE, "complete", "C4", Costly(script), build_view(CASE, "complete"))
    assert log["c4_token_cap_hit"] is True and log["error"] is None
    assert log["c2_violation"] is True and log["output"] is not None


def test_the_token_cap_without_an_answer_is_the_models_outcome_not_a_harness_error():
    log = run_case(CASE, "complete", "C4", Costly(FULL), build_view(CASE, "complete"))
    assert log["error"] == "token_cap_without_answer" and len(log["tool_calls"]) == 2
    assert agent.is_harness_error(log["error"]) is False


def test_other_configs_have_no_caps():
    log = run_case(CASE, "complete", "C3", Costly(FULL + [_final(evidence_ids=["E-EVT-001"])]),
                   build_view(CASE, "complete"))
    assert "c4_token_cap_hit" not in log and log["output"] is not None
