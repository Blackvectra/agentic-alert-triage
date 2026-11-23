"""C2 through the real run loop (ADR 0012), with a scripted model on a dev case."""
import json

from triage.agent import Final, ScriptedModel, ToolCall, Usage, run_case
from triage.fixtures import build_view, load_cases

CASE = next(c for c in load_cases("dev") if c["case_id"] == "AUTH-001")
SEARCH = ToolCall("event_search", {"user": "jdoe@example.org"})  # returns E-EVT-001 among others


def _final(evidence_ids, disposition="true_positive"):
    return Final(json.dumps({
        "disposition": disposition, "abstain": False, "summary": "s",
        "claims": [{"text": "c", "evidence_ids": evidence_ids}],
        "proposed_actions": [{"action": "reset sessions", "evidence_ids": evidence_ids}],
    }))


def _run(script):
    return run_case(CASE, "complete", "C2", ScriptedModel(script), build_view(CASE, "complete"))


def test_a_good_answer_is_accepted_and_goes_to_the_gate():
    log = _run([SEARCH, _final(["E-EVT-001"])])
    assert log["c2_check"]["outcome"] == "accepted"
    assert log["output"]["disposition"] == "true_positive"
    assert len(log["gate"]) == 1  # proposals still go to the mock approval gate, as in C


class CountingModel(ScriptedModel):
    """A scripted model that reports 10 input and 1 output token per step, to check token counting."""
    def step(self, system, messages, tools):
        self.seen = messages
        act, _ = super().step(system, messages, tools)
        return act, Usage(10, 1)


def test_a_made_up_citation_gets_one_repair_turn_and_its_tokens_count():
    model = CountingModel([SEARCH, _final(["E-FAKE"]), _final(["E-EVT-001"])])
    log = run_case(CASE, "complete", "C2", model, build_view(CASE, "complete"))
    assert log["c2_check"]["outcome"] == "repaired"
    assert log["output"]["claims"][0]["evidence_ids"] == ["E-EVT-001"]
    assert "cited E-FAKE" in model.seen[-1]["content"]  # the model was told what was wrong
    assert (log["input_tokens"], log["output_tokens"]) == (30, 3)  # 3 steps, the repair included
    assert len(log["tool_calls"]) == 1  # the repair turn is not a tool call


def test_two_failures_end_in_needs_more_info_with_nothing_for_the_gate():
    log = _run([SEARCH, _final(["E-FAKE"]), _final(["E-FAKE"])])
    assert log["c2_check"]["outcome"] == "fallback"
    assert log["output"]["disposition"] == "needs_more_info" and log["output"]["abstain"] is True
    assert log["gate"] == []


def test_answering_benign_over_a_known_bad_sign_is_blocked():
    # AUTH-001's events include a new inbox rule (a guide-listed persistence sign).
    rule = ToolCall("event_search", {"user": "jdoe@example.org", "event_type": "mailbox_rule_created"})
    log = _run([rule, _final([], "benign"), _final([], "benign")])
    assert log["c2_check"]["outcome"] == "fallback"
    assert "known-bad sign" in log["c2_check"]["problems"][0][0]


def test_invalid_tool_arguments_are_rejected_as_in_c():
    bad = ToolCall("event_search", {"host": "LT-JDOE"})
    log = _run([bad, SEARCH, _final(["E-EVT-001"])])
    assert log["tool_calls"][0]["valid"] is False and log["tool_calls"][0]["executed"] is False


def test_adding_c2_leaves_the_frozen_a_b_c_prompts_untouched():
    from triage.freeze import mismatches
    assert mismatches() == []
