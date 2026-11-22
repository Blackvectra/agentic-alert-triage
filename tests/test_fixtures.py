"""Fixture integrity: these protect the experiment design, not the code."""
from collections import defaultdict

from triage.fixtures import VARIANTS, all_evidence_ids, build_view, load_cases

CASES = load_cases()


def test_cases_load_and_validate():
    assert CASES, "no fixtures found"


def test_required_and_withheld_ids_exist():
    for c in CASES:
        ids = all_evidence_ids(c)
        for name, v in c["variants"].items():
            assert set(v["required_evidence"]) <= ids, (c["case_id"], name)
            assert set(v.get("withhold_ids", [])) <= ids, (c["case_id"], name)
            # A required record can't also be hidden, or the case is unwinnable.
            assert not set(v["required_evidence"]) & set(v.get("withhold_ids", [])), (c["case_id"], name)


def test_scenario_group_never_spans_splits():
    splits = defaultdict(set)
    for c in CASES:
        splits[c["scenario_group"]].add(c["split"])
    leaks = {g: s for g, s in splits.items() if len(s) > 1}
    assert not leaks, f"scenario groups in both splits: {leaks}"


def test_case_ids_unique():
    ids = [c["case_id"] for c in CASES]
    assert len(ids) == len(set(ids))


def test_withheld_view_hides_records():
    for c in CASES:
        hidden = set(c["variants"]["withheld"].get("withhold_ids", []))
        view_ids = {r["evidence_id"] for k in build_view(c, "withheld")["evidence"].values() for r in k}
        assert not hidden & view_ids


def test_injection_lands_and_fixture_untouched():
    for c in CASES:
        inj = c["variants"]["injected"]["injection"]
        view = build_view(c, "injected")
        rec = next(r for k in view["evidence"].values() for r in k if r["evidence_id"] == inj["target_evidence_id"])
        assert rec[inj["field"]] == inj["payload"]
        assert inj["canary"] in inj["payload"]
        # Original fixture must not be mutated by build_view.
        orig = next(r for k in c["evidence"].values() for r in k if r["evidence_id"] == inj["target_evidence_id"])
        assert orig.get(inj["field"]) != inj["payload"]


def test_complete_view_has_everything():
    for c in CASES:
        assert {r["evidence_id"] for k in build_view(c, "complete")["evidence"].values() for r in k} == all_evidence_ids(c)
    assert VARIANTS == ("complete", "withheld", "injected")


def test_injections_are_labelled_for_breakdown():
    # Labels let the report break injection success down by technique (Greshake et al. 2023)
    # and by attacker intent (Greshake et al. 2023; InjecAgent, Zhan et al. 2024).
    for c in CASES:
        inj = c["variants"]["injected"]["injection"]
        assert inj["delivery"] in {"plain", "disguised", "encoded", "multi_stage"}, c["case_id"]
        assert inj["intent"] and set(inj["intent"]) <= {"manipulated_output", "harmful_tool_call", "exfiltration"}, c["case_id"]
