"""Tests for the free local-model adapter (Ollama /api/chat), through Model.step.

FakePost stands in for the HTTP call to the Ollama server and returns canned
JSON shaped like Ollama's documented /api/chat response. No server needed.
"""
from triage.agent import Final, OllamaModel, ToolCall, Usage

USER_MSG = [{"role": "user", "content": "ALERT: ..."}]


class FakePost:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []  # (url, payload) for every call

    def __call__(self, url, payload):
        self.requests.append((url, payload))
        return self._responses.pop(0)


def text_reply(text, prompt_tokens=10, output_tokens=5):
    return {"message": {"role": "assistant", "content": text},
            "prompt_eval_count": prompt_tokens, "eval_count": output_tokens, "done_reason": "stop"}


def tool_reply(*calls):
    return {"message": {"role": "assistant", "content": "",
                        "tool_calls": [{"function": {"name": n, "arguments": a}} for n, a in calls]},
            "prompt_eval_count": 10, "eval_count": 5, "done_reason": "stop"}


def model(post):
    return OllamaModel(model_id="qwen2.5:7b", post=post)


def test_text_reply_becomes_final_answer():
    act, _ = model(FakePost([text_reply('{"disposition": "benign"}')])).step("sys", USER_MSG, None)
    assert act == Final('{"disposition": "benign"}')


def test_tool_call_reply_becomes_tool_call():
    act, _ = model(FakePost([tool_reply(("event_search", {"user": "jdoe@example.org"}))])).step("sys", USER_MSG, None)
    assert act == ToolCall("event_search", {"user": "jdoe@example.org"})


def test_step_reports_token_usage():
    _, usage = model(FakePost([text_reply("{}", prompt_tokens=812, output_tokens=47)])).step("sys", USER_MSG, None)
    assert usage == Usage(input_tokens=812, output_tokens=47)


TOOL = {"name": "guide_lookup", "description": "Get the guide.",
        "input_schema": {"type": "object", "properties": {"family": {"type": "string"}}}}


def test_request_is_reproducible_and_carries_tools():
    post = FakePost([text_reply("{}")])
    model(post).step("sys", USER_MSG, [TOOL])

    url, sent = post.requests[0]
    assert url == "http://localhost:11434/api/chat"
    assert sent["model"] == "qwen2.5:7b" and sent["stream"] is False
    # Local models accept temperature and seed, so runs are repeatable (unlike the Anthropic API).
    assert sent["options"] == {"temperature": 0, "seed": 672, "num_ctx": 16384}
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert sent["tools"] == [{"type": "function", "function": {
        "name": "guide_lookup", "description": "Get the guide.",
        "parameters": {"type": "object", "properties": {"family": {"type": "string"}}}}}]


def test_prompt_only_request_sends_no_tools():
    post = FakePost([text_reply("{}")])
    model(post).step("sys", USER_MSG, None)
    assert "tools" not in post.requests[0][1]


def test_only_the_first_of_several_tool_calls_is_used():
    # One call per turn, same as the Anthropic adapter, so the budget counts calls one at a time.
    reply = tool_reply(("event_search", {"user": "a"}), ("entity_lookup", {"id": "a"}))
    act, _ = model(FakePost([reply])).step("sys", USER_MSG, None)
    assert act == ToolCall("event_search", {"user": "a"})


# --- Seam 2: full run_case runs driven by OllamaModel ---------------------------
import json  # noqa: E402

from triage.agent import run_case  # noqa: E402
from triage.fixtures import build_view, load_cases  # noqa: E402

ANSWER = json.dumps({"disposition": "true_positive", "abstain": False, "summary": "s",
                     "claims": [{"text": "c", "evidence_ids": ["E-EVT-001"]}], "proposed_actions": []})


def auth_001():
    case = next(c for c in load_cases("dev", "suspicious_auth") if c["case_id"] == "AUTH-001")
    return case, build_view(case, "complete")


def test_second_request_replays_the_used_call_and_names_the_tool_result():
    case, view = auth_001()
    post = FakePost([tool_reply(("event_search", {"user": "jdoe@example.org"}), ("entity_lookup", {"id": "x"})),
                     text_reply(ANSWER)])

    log = run_case(case, "complete", "B", model(post), view)

    assert log["error"] is None
    msgs = post.requests[1][1]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    # Only the call that actually ran is replayed, so the model never waits on an unanswered call.
    assert msgs[2]["tool_calls"] == [{"function": {"name": "event_search", "arguments": {"user": "jdoe@example.org"}}}]
    assert msgs[3]["tool_name"] == "event_search"
    assert "E-EVT-001" in msgs[3]["content"]


def test_b_and_c_send_byte_identical_tool_definitions():
    case, view = auth_001()
    sent = {}
    for config in ("B", "C"):
        post = FakePost([text_reply(ANSWER)])
        run_case(case, "complete", config, model(post), view)
        sent[config] = json.dumps(post.requests[0][1]["tools"])
    assert sent["B"] == sent["C"]


def test_arguments_sent_as_a_json_string_are_decoded():
    # Some models return arguments as a JSON string rather than an object.
    act, _ = model(FakePost([tool_reply(("event_search", '{"user": "a"}'))])).step("sys", USER_MSG, None)
    assert act == ToolCall("event_search", {"user": "a"})


def test_log_records_settings_prompt_hash_and_stop_reasons():
    case, view = auth_001()
    logs = {}
    for config in ("B", "C"):
        post = FakePost([tool_reply(("event_search", {"user": "jdoe@example.org"})), text_reply(ANSWER)])
        logs[config] = run_case(case, "complete", config, model(post), view)

    log = logs["C"]
    assert log["model_settings"] == {"model_id": "qwen2.5:7b", "temperature": 0, "seed": 672, "num_ctx": 16384}
    assert log["stop_reasons"] == ["stop", "stop"]
    # The hash proves which prompt and tools a run used; B and C prompts differ by design.
    assert len(log["prompt_sha256"]) == 64
    assert logs["B"]["prompt_sha256"] != logs["C"]["prompt_sha256"]
