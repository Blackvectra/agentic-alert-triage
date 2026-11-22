"""Seam 2: a full run_case run driven by AnthropicModel with a scripted fake client.

Checks what a multi-turn run actually sends to the provider. No network, no key.
"""
import json
from types import SimpleNamespace

from triage.agent import AnthropicModel, run_case
from triage.fixtures import build_view, load_cases

from test_anthropic_adapter import FakeClient, text_response

ANSWER = json.dumps({"disposition": "true_positive", "abstain": False, "summary": "s",
                     "claims": [{"text": "c", "evidence_ids": ["E-EVT-001"]}], "proposed_actions": []})


def auth_001():
    case = next(c for c in load_cases("dev", "suspicious_auth") if c["case_id"] == "AUTH-001")
    return case, build_view(case, "complete")


def thinking_then_tool_use():
    """First reply: a thinking block, then a request to search events for the user."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="", signature="sig-abc"),
            SimpleNamespace(type="tool_use", id="toolu_01", name="event_search",
                            input={"user": "jdoe@example.org"}),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


def test_second_request_replays_reply_and_pairs_tool_result_with_its_id():
    case, view = auth_001()
    first = thinking_then_tool_use()
    client = FakeClient([first, text_response(ANSWER)])

    log = run_case(case, "complete", "B", AnthropicModel(client=client, model_id="claude-sonnet-5-5"), view)

    assert log["error"] is None
    second = client.requests[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    # Claude's first reply goes back unchanged, thinking block included.
    assert second[1]["content"] is first.content
    # The tool output answers tool call toolu_01 and holds the records the tool returned.
    result = second[2]["content"][0]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_01"
    assert "E-EVT-001" in result["content"]
