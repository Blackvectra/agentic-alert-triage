"""C3 through the real run loop (ADR 0013): C2 with layer 2 replaced by the coverage rule."""
import json

from triage.agent import CALL_BUDGET, Final, ScriptedModel, ToolCall, run_case
from triage.fixtures import build_view, load_cases

CASE = next(c for c in load_cases("dev") if c["case_id"] == "AUTH-001")
USER, IP1, IP2 = "jdoe@example.org", "198.51.100.23", "203.0.113.77"  # AUTH-001's alert entities
FULL = [ToolCall("entity_lookup", {"id": USER}), ToolCall("entity_lookup", {"id": IP1}),
        ToolCall("entity_lookup", {"id": IP2}), ToolCall("event_search", {"user": USER}),
        ToolCall("event_search", {"src_ip": IP1}), ToolCall("event_search", {"src_ip": IP2})]


def _final(evidence_ids=()):
    return Final(json.dumps({"disposition": "true_positive", "abstain": False, "summary": "s",
                             "claims": [{"text": "c", "evidence_ids": list(evidence_ids)}],
                             "proposed_actions": []}))


class Recorder(ScriptedModel):
    def step(self, system, messages, tools):
        self.seen = messages
        return super().step(system, messages, tools)


def _run(script):
    model = Recorder(script)
    log = run_case(CASE, "complete", "C3", model, build_view(CASE, "complete"))
    pushbacks = [m["content"] for m in model.seen if m["role"] == "user"][1:]
    return log, pushbacks


def test_full_coverage_is_accepted_without_a_pushback():
    log, pushbacks = _run(FULL + [_final(["E-EVT-001"])])
    assert log["c2_pushbacks"] == 0 and log["c2_violation"] is False and pushbacks == []
    assert log["c2_check"]["outcome"] == "accepted"  # layer 3 still checks the answer


def test_c2s_two_calls_are_not_enough_and_the_pushback_names_what_is_missing():
    log, pushbacks = _run(FULL[:1] + FULL[3:4] + [_final()] + FULL[1:3] + FULL[4:] + [_final()])
    assert log["c2_pushbacks"] == 1 and log["c2_violation"] is False
    assert f"entity_lookup id={IP1}" in pushbacks[0] and f"event_search src_ip={IP2}" in pushbacks[0]
    assert f"entity_lookup id={USER}" not in pushbacks[0]  # already done, so not listed


def test_never_covering_is_accepted_after_two_pushbacks_as_a_violation():
    log, pushbacks = _run([_final()] * 3)
    assert log["c2_pushbacks"] == 2 and log["c2_violation"] is True and len(pushbacks) == 2
    assert log["error"] is None


def test_pushbacks_cost_no_tool_calls():
    log, _ = _run([_final(), _final()] + FULL + [FULL[0]] * (CALL_BUDGET - len(FULL)) + [_final()])
    assert log["c2_pushbacks"] == 2 and log["c2_violation"] is False
    assert [c["executed"] for c in log["tool_calls"]] == [True] * CALL_BUDGET


def test_c3_keeps_c2s_layers_1_and_3_and_its_prompt():
    from triage import agent
    model = Recorder(FULL + [_final(["E-EVT-001"])])
    log = run_case(CASE, "complete", "C3", model, build_view(CASE, "complete"))
    assert list(json.loads(next(m["content"] for m in model.seen if m["role"] == "tool"))) == ["untrusted_data"]
    assert "c2_injection_flags" in log
    assert agent.PROMPTS["C3"] == agent.PROMPTS["C2"] and agent.tools_for("C3") == agent.tools_for("B")
    assert "C3" in agent.EXPLORATORY_CONFIGS and "C3" in agent.GUARDED


def test_budget_running_out_after_a_pushback_keeps_the_earlier_answer():
    # Dev run finding: the model answers, is pushed back, then spends the rest of the
    # budget on searches that don't close the gap. The earlier answer must not be lost.
    log, _ = _run(FULL[:1] + [_final(["E-EVT-001"])] + [FULL[0]] * (CALL_BUDGET + 3) + [_final()])
    assert log["c2_pushbacks"] == 1 and log["error"] is None  # layer 3 still repairs the kept answer
    assert log["c2_violation"] is True and log["output"] is not None
