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
