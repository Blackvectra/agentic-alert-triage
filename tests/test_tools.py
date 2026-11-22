"""The read-only tools, tested directly. Dry run (2026-11-22) showed every
event_search returning nothing because the model wrote "sign_in" for "signin"."""
from triage.fixtures import build_view, load_cases
from triage.tools import event_search

VIEW = build_view(next(c for c in load_cases() if c["case_id"] == "AUTH-001"), "complete")
USER = "jdoe@example.org"


def ids(records):
    return sorted(r["evidence_id"] for r in records)


def test_event_type_ignores_case_and_separators():
    # The fixture says "signin"; the model wrote "sign_in" in the dry run.
    expected = ["E-EVT-001", "E-EVT-002", "E-EVT-003"]
    for spelling in ("signin", "sign_in", "Sign-In", "SIGN IN"):
        assert ids(event_search(VIEW, user=USER, event_type=spelling)) == expected, spelling


def test_event_type_is_not_guessed():
    # A different word is a different type: no synonym matching.
    assert event_search(VIEW, user=USER, event_type="auth") == []


def test_omitting_event_type_returns_every_event_for_the_user():
    assert ids(event_search(VIEW, user=USER)) == ["E-EVT-001", "E-EVT-002", "E-EVT-003", "E-EVT-004"]


def test_description_tells_the_model_event_type_is_optional():
    # The model can only use what the description tells it (dry run: it always guessed a type).
    from triage.tools import TOOL_SPECS
    desc = TOOL_SPECS["event_search"]["description"].lower()
    assert "optional" in desc and "omit" in desc
