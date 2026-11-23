"""C2 through the real run loop (ADR 0012), with a scripted model on a dev case."""
import json

from triage.agent import Final, ScriptedModel, ToolCall, Usage, run_case
from triage.fixtures import build_view, load_cases

CASE = next(c for c in load_cases("dev") if c["case_id"] == "AUTH-001")
SEARCH = ToolCall("event_search", {"user": "jdoe@example.org"})  # returns E-EVT-001 among others
LOOKUP = ToolCall("entity_lookup", {"id": "jdoe@example.org"})


def _final(evidence_ids, disposition="true_positive"):
    return Final(json.dumps({
        "disposition": disposition, "abstain": False, "summary": "s",
        "claims": [{"text": "c", "evidence_ids": evidence_ids}],
        "proposed_actions": [{"action": "reset sessions", "evidence_ids": evidence_ids}],
    }))


def _run(script):
    return run_case(CASE, "complete", "C2", ScriptedModel(script), build_view(CASE, "complete"))


def test_a_good_answer_is_accepted_and_goes_to_the_gate():
    log = _run([SEARCH, LOOKUP, _final(["E-EVT-001"])])
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
    model = CountingModel([SEARCH, LOOKUP, _final(["E-FAKE"]), _final(["E-EVT-001"])])
    log = run_case(CASE, "complete", "C2", model, build_view(CASE, "complete"))
    assert log["c2_check"]["outcome"] == "repaired"
    assert log["output"]["claims"][0]["evidence_ids"] == ["E-EVT-001"]
    assert "cited E-FAKE" in model.seen[-1]["content"]  # the model was told what was wrong
    assert (log["input_tokens"], log["output_tokens"]) == (40, 4)  # 4 steps, the repair included
    assert len(log["tool_calls"]) == 2  # the repair turn is not a tool call


def test_two_failures_end_in_needs_more_info_with_nothing_for_the_gate():
    log = _run([SEARCH, LOOKUP, _final(["E-FAKE"]), _final(["E-FAKE"])])
    assert log["c2_check"]["outcome"] == "fallback"
    assert log["output"]["disposition"] == "needs_more_info" and log["output"]["abstain"] is True
    assert log["gate"] == []


def test_answering_benign_over_a_known_bad_sign_is_blocked():
    # AUTH-001's events include a new inbox rule (a guide-listed persistence sign).
    rule = ToolCall("event_search", {"user": "jdoe@example.org", "event_type": "mailbox_rule_created"})
    log = _run([rule, LOOKUP, _final([], "benign"), _final([], "benign")])
    assert log["c2_check"]["outcome"] == "fallback"
    assert "known-bad sign" in log["c2_check"]["problems"][0][0]


def test_invalid_tool_arguments_are_rejected_as_in_c():
    bad = ToolCall("event_search", {"host": "LT-JDOE"})
    log = _run([bad, SEARCH, LOOKUP, _final(["E-EVT-001"])])
    assert log["tool_calls"][0]["valid"] is False and log["tool_calls"][0]["executed"] is False


def test_adding_c2_leaves_the_frozen_a_b_c_prompts_untouched():
    from triage.freeze import mismatches
    assert mismatches() == []


def test_every_config_is_listed_once_and_everyone_uses_that_list():
    # One source of truth for config names, so a new config cannot be missed in one file.
    from triage import agent, freeze, report, run
    assert set(agent.PROMPTS) == set(agent.MAIN_CONFIGS) | set(agent.EXPLORATORY_CONFIGS)
    assert not set(agent.MAIN_CONFIGS) & set(agent.EXPLORATORY_CONFIGS)
    for module in (run, freeze, report):
        assert module.CONFIGS is agent.MAIN_CONFIGS, module.__name__


# --- Layer 2: investigate first (ADR 0012) ---


def test_an_answer_before_investigating_is_sent_back_once_then_accepted():
    model = CountingModel([_final(["E-EVT-001"]), SEARCH, LOOKUP, _final(["E-EVT-001"])])
    log = run_case(CASE, "complete", "C2", model, build_view(CASE, "complete"))
    assert log["c2_pushbacks"] == 1 and log["c2_violation"] is False
    assert any("investigate first" in m.get("content", "") for m in model.seen if m["role"] == "user")
    assert log["c2_check"]["outcome"] == "accepted"
    assert [c["name"] for c in log["tool_calls"]] == ["event_search", "entity_lookup"]


def test_a_model_that_never_investigates_is_accepted_after_two_pushbacks_as_a_violation():
    model = CountingModel([_final([])] * 3)  # cites nothing, so layer 3 has no complaint
    log = run_case(CASE, "complete", "C2", model, build_view(CASE, "complete"))
    assert log["c2_pushbacks"] == 2 and log["c2_violation"] is True
    assert sum("investigate first" in m.get("content", "") for m in model.seen if m["role"] == "user") == 2
    assert log["tool_calls"] == [] and log["error"] is None
    assert (log["input_tokens"], log["output_tokens"]) == (30, 3)  # the answer and 2 push-backs


def test_pushbacks_do_not_use_up_any_of_the_8_tool_calls():
    from triage.agent import CALL_BUDGET
    calls = [SEARCH, LOOKUP] + [SEARCH] * (CALL_BUDGET - 2)
    log = _run([_final([]), _final([])] + calls + [_final(["E-EVT-001"])])
    assert log["c2_pushbacks"] == 2 and log["c2_violation"] is False
    assert log["error"] is None
    assert [c["executed"] for c in log["tool_calls"]] == [True] * CALL_BUDGET
    assert log["c2_check"]["outcome"] == "accepted"


def test_a_model_that_investigates_first_is_never_pushed_back():
    model = CountingModel([LOOKUP, SEARCH, _final(["E-EVT-001"])])  # order does not matter
    log = run_case(CASE, "complete", "C2", model, build_view(CASE, "complete"))
    assert log["c2_pushbacks"] == 0 and log["c2_violation"] is False
    assert not any("investigate first" in m.get("content", "") for m in model.seen if m["role"] == "user")
    assert log["c2_check"]["outcome"] == "accepted"


def test_a_rejected_call_does_not_count_as_investigating():
    bad = ToolCall("entity_lookup", {"id": "x" * 500})  # too long: rejected, never runs
    log = _run([SEARCH, bad, _final([]), LOOKUP, _final([])])
    assert log["c2_pushbacks"] == 1


# --- Layer 1: tool output reaches C2's model labelled as untrusted data (ADR 0012) ---
def _tool_messages(config):
    model = CountingModel([SEARCH, LOOKUP, _final(["E-EVT-001"])])
    run_case(CASE, "complete", config, model, build_view(CASE, "complete"))
    return [json.loads(m["content"]) for m in model.seen if m["role"] == "tool"]


def test_c2_sees_tool_results_wrapped_as_untrusted_data():
    first = _tool_messages("C2")[0]
    assert list(first) == ["untrusted_data"]
    assert "E-EVT-001" in [r["evidence_id"] for r in first["untrusted_data"]]


def test_b_and_c_still_see_plain_tool_results():
    for config in ("B", "C"):
        first = _tool_messages(config)[0]
        assert isinstance(first, list) and "E-EVT-001" in [r["evidence_id"] for r in first]


def test_a_flagged_injection_is_logged_and_blocks_a_benign_answer():
    # PROC-003 (dev), injected: an instruction is planted in E-EVT-703's file_description,
    # and nothing else in its evidence is a known-bad sign.
    case = next(c for c in load_cases("dev") if c["case_id"] == "PROC-003")
    script = [ToolCall("event_search", {"user": "NT AUTHORITY\\SYSTEM"}),
              ToolCall("entity_lookup", {"id": "APP-03"}),
              _final([], "benign"), _final([], "benign")]
    log = run_case(case, "injected", "C2", ScriptedModel(script), build_view(case, "injected"))
    assert log["c2_injection_flags"] == [{"evidence_id": "E-EVT-703", "field": "file_description"}]
    assert log["c2_check"]["outcome"] == "fallback"
    assert "E-EVT-703" in log["c2_check"]["problems"][0][0] and "injection" in log["c2_check"]["problems"][0][0]


def test_the_same_case_without_the_injection_has_no_flags_and_benign_is_accepted():
    case = next(c for c in load_cases("dev") if c["case_id"] == "PROC-003")
    script = [ToolCall("event_search", {"user": "NT AUTHORITY\\SYSTEM"}),
              ToolCall("entity_lookup", {"id": "APP-03"}), _final([], "benign")]
    log = run_case(case, "complete", "C2", ScriptedModel(script), build_view(case, "complete"))
    assert log["c2_injection_flags"] == [] and log["c2_check"]["outcome"] == "accepted"
