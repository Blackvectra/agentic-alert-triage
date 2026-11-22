"""The three read-only investigation tools.

They only read from the variant's evidence view. Nothing here can change
state, which is the point: the agent can look but never touch.
Every returned record carries its evidence_id so the scorer can check
citations against what was actually retrieved.
"""
from __future__ import annotations

import re

# JSON Schemas for tool inputs. Config C validates against these before a
# call runs; Config B passes arguments through unchecked.
TOOL_SPECS = {
    "event_search": {
        "description": ("Search event logs by user and/or source IP. Returns matching events. "
                        "event_type is optional: omit it to get every event for that user or IP."),
        "input_schema": {
            "type": "object",
            "properties": {
                "user": {"type": "string", "maxLength": 200},
                "src_ip": {"type": "string", "maxLength": 64},
                "event_type": {"type": "string", "maxLength": 64},
            },
            "additionalProperties": False,
            "minProperties": 1,
        },
    },
    "entity_lookup": {
        "description": "Look up context for a user account or IP address by its id.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "maxLength": 200}},
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    "guide_lookup": {
        "description": "Get the investigation guide for an alert family.",
        "input_schema": {
            "type": "object",
            "properties": {"family": {"type": "string", "maxLength": 64}},
            "required": ["family"],
            "additionalProperties": False,
        },
    },
}
ALLOWED_TOOLS = frozenset(TOOL_SPECS)


def _match(record: dict, **criteria) -> bool:
    return all(v is None or str(record.get(k, "")).lower() == str(v).lower() for k, v in criteria.items())


def _normalize_type(value) -> str:
    """'sign_in', 'Sign-In' and 'signin' are one event type; different words stay different."""
    return re.sub(r"[\s_-]", "", str(value)).lower()


def event_search(view: dict, user=None, src_ip=None, event_type=None, **_ignored) -> list[dict]:
    return [e for e in view["evidence"]["events"]
            if _match(e, user=user, src_ip=src_ip)
            and (event_type is None or _normalize_type(e.get("type", "")) == _normalize_type(event_type))]


def entity_lookup(view: dict, id=None, **_ignored) -> list[dict]:
    return [e for e in view["evidence"]["entities"] if str(e.get("id", "")).lower() == str(id).lower()]


def guide_lookup(view: dict, family=None, **_ignored) -> list[dict]:
    # One guide per family in the fixtures; a wrong family name returns nothing.
    if family != view["family"]:
        return []
    return list(view["evidence"]["guides"])


IMPLEMENTATIONS = {"event_search": event_search, "entity_lookup": entity_lookup, "guide_lookup": guide_lookup}
