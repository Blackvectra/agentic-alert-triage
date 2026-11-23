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


def test_entity_lookup_description_names_every_entity_kind_in_the_fixtures():
    # A kind the description omits is one the model may never think to look up.
    from triage.fixtures import load_cases
    from triage.tools import TOOL_SPECS
    desc = TOOL_SPECS["entity_lookup"]["description"].lower()
    kinds = {e["kind"] for c in load_cases() for e in c["evidence"]["entities"]}
    missing = {k for k in kinds if ("ip address" if k == "ip" else k) not in desc}
    assert not missing, f"entity kinds missing from entity_lookup description: {missing}"


def test_event_search_example_types_exist_in_the_fixtures():
    from triage.fixtures import load_cases
    from triage.tools import TOOL_SPECS
    types = {e["type"] for c in load_cases() for e in c["evidence"]["events"]}
    for example in ("signin", "process_start", "network_connection"):
        assert example in TOOL_SPECS["event_search"]["description"] and example in types


def test_event_search_description_says_there_is_no_host_filter():
    # Wording guard only. What a host argument does is tested through run_case in test_scoring.py.
    from triage.tools import TOOL_SPECS
    assert "no host filter" in TOOL_SPECS["event_search"]["description"]
