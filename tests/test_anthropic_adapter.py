"""Tests for the Anthropic model adapter, through its public interface: Model.step.

The real Anthropic client is replaced by FakeClient, which records each request
and returns a canned response shaped like the documented Messages API response.
No network, no API key, no cost.
"""
from types import SimpleNamespace

from triage.agent import AnthropicModel, Final, ToolCall, Usage


class FakeClient:
    """Stands in for anthropic.Anthropic(). Only messages.create is used."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []  # every kwargs dict passed to messages.create
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


def text_response(text, input_tokens=10, output_tokens=5):
    """A response whose content is a single text block, as the API returns it."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_text_reply_becomes_final_answer():
    client = FakeClient([text_response('{"disposition": "benign"}')])
    model = AnthropicModel(client=client, model_id="claude-sonnet-5-5")

    act, _usage = model.step("system prompt", [{"role": "user", "content": "ALERT: ..."}], None)

    assert act == Final('{"disposition": "benign"}')


def tool_use_response(name, tool_input, tool_use_id="toolu_01"):
    """A response asking to call one tool, as the API returns it."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", id=tool_use_id, name=name, input=tool_input)],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def test_tool_use_reply_becomes_tool_call():
    client = FakeClient([tool_use_response("event_search", {"user": "jdoe@example.org"})])
    model = AnthropicModel(client=client, model_id="claude-sonnet-5-5")

    act, _usage = model.step("system prompt", [{"role": "user", "content": "ALERT: ..."}], None)

    assert act == ToolCall("event_search", {"user": "jdoe@example.org"})


def test_step_reports_token_usage_from_the_response():
    client = FakeClient([text_response("{}", input_tokens=1234, output_tokens=56)])
    model = AnthropicModel(client=client, model_id="claude-sonnet-5-5")

    _act, usage = model.step("system prompt", [{"role": "user", "content": "ALERT: ..."}], None)

    assert usage == Usage(input_tokens=1234, output_tokens=56)


def test_request_carries_tools_and_fixed_settings():
    """ADR 0001: tools sent as defined, no provider-side strict mode.
    ADR 0002: fixed effort and max_tokens, one tool call per turn, no temperature."""
    tool = {"name": "guide_lookup", "description": "Get the guide.",
            "input_schema": {"type": "object", "properties": {"family": {"type": "string"}}}}
    client = FakeClient([text_response("{}")])
    model = AnthropicModel(client=client, model_id="claude-sonnet-5-5")

    model.step("system prompt", [{"role": "user", "content": "ALERT: ..."}], [tool])

    sent = client.requests[0]
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["max_tokens"] == 16000
    assert sent["output_config"] == {"effort": "medium"}
    assert sent["tools"] == [{"name": "guide_lookup", "description": "Get the guide.",
                              "input_schema": {"type": "object", "properties": {"family": {"type": "string"}}}}]
    assert sent["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    assert "strict" not in sent["tools"][0]
    assert "temperature" not in sent
