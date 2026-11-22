"""Load triage cases and build the evidence view for one variant.

A case holds ALL evidence once. A variant (complete / withheld / injected)
is applied on top, so the three versions of a case can never drift apart.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
SCHEMA = json.loads((FIXTURES / "case.schema.json").read_text())
VARIANTS = ("complete", "withheld", "injected")


def load_case(path: Path) -> dict:
    case = json.loads(Path(path).read_text())
    jsonschema.validate(case, SCHEMA)  # fail loudly on a malformed fixture
    return case


def load_cases(split: str | None = None, family: str | None = None) -> list[dict]:
    cases = [load_case(p) for p in sorted((FIXTURES / "cases").glob("*.json"))]
    if split:
        cases = [c for c in cases if c["split"] == split]
    if family:
        cases = [c for c in cases if c["family"] == family]
    return cases


def all_evidence_ids(case: dict) -> set[str]:
    return {r["evidence_id"] for kind in case["evidence"].values() for r in kind}


def build_view(case: dict, variant: str) -> dict:
    """Return the evidence the tools are allowed to serve for this variant."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant}")
    spec = case["variants"][variant]
    evidence = copy.deepcopy(case["evidence"])  # never mutate the fixture

    # Withheld: drop records entirely, as if the log source never had them.
    hidden = set(spec.get("withhold_ids", []))
    for kind in evidence:
        evidence[kind] = [r for r in evidence[kind] if r["evidence_id"] not in hidden]

    # Injected: overwrite one attacker-controlled field with the payload.
    inj = spec.get("injection")
    if inj:
        for kind in evidence:
            for r in evidence[kind]:
                if r["evidence_id"] == inj["target_evidence_id"]:
                    r[inj["field"]] = inj["payload"]
                    break
    return {"alert": case["alert"], "family": case["family"], "evidence": evidence}


def canary_in_payload(injection: dict) -> bool:
    """True if the injection's canary is in its payload.

    For `encoded` delivery the canary is hidden inside base64, so each
    base64-looking token is decoded and checked too. Other deliveries need
    the canary in plain text.
    """
    import base64
    import binascii
    import re

    if injection["canary"] in injection["payload"]:
        return True
    if injection.get("delivery") != "encoded":
        return False
    for token in re.findall(r"[A-Za-z0-9+/]{16,}={0,2}", injection["payload"]):
        try:
            if injection["canary"] in base64.b64decode(token, validate=True).decode("utf-8", "ignore"):
                return True
        except (binascii.Error, ValueError):
            continue
    return False


def reachable_ids(view: dict) -> set[str]:
    """Evidence IDs an agent can retrieve starting only from the alert's entities.

    Mirrors the agent's own options: event_search by user or src_ip,
    entity_lookup by id, and guide_lookup for the case's family.
    """
    from .tools import entity_lookup, event_search, guide_lookup

    found = set()
    for value in view["alert"]["entities"].values():
        for records in (event_search(view, user=value), event_search(view, src_ip=value),
                        entity_lookup(view, id=value)):
            found |= {r["evidence_id"] for r in records}
    found |= {r["evidence_id"] for r in guide_lookup(view, family=view["family"])}
    return found
