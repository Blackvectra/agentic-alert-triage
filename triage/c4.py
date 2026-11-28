"""C4: C3 plus four more guards enforced in code (ADR 0014). The last guarded config.

Like triage/c2.py, this module holds checks only: the agent loop in triage/agent.py calls them.
"""
from __future__ import annotations

import re

from . import c2

# Guard 4, cost cap (ADR 0014): a run stops before any model turn once it has used this many
# tokens. C3's dev run used at most 22,423, so the cap only stops a runaway. The loop cap (a
# repeated identical tool call is not run again) lives in the run loop, triage/agent.py.
TOKEN_CAP = 32_000

# Guard 1, missing-evidence abstain (ADR 0014). A lookup on an alert entity that ran and found
# nothing means the alert cannot be confirmed from the logs: some of its evidence is missing.
# Built-in accounts such as NT AUTHORITY\SYSTEM have no directory record, and IP addresses often
# have none either, so an empty entity_lookup on those says nothing and does not count.
_BUILT_IN_ACCOUNT = re.compile(r"^nt authority\\", re.IGNORECASE)


def _searchable(alert: dict) -> set[tuple[str, str]]:
    """(filter, value) for every alert value event_search can look for: users and source IPs.

    The same rule as C3's coverage rule (c2.missing_coverage), so every search C3 asks for is
    one this guard can read.
    """
    out = set()
    for field, v in c2._alert_values(alert):
        if field == "user" or "@" in v:
            out.add(("user", v.lower()))
        elif c2._IPV4.fullmatch(v) and c2._is_source_field(field):
            out.add(("src_ip", v.lower()))
    return out


def empty_lookups(alert: dict, tool_calls: list[dict]) -> list[str]:
    """Name every lookup on an alert entity that ran and found nothing. Empty means none did.

    Only a search on one alert user or source IP with no other filter counts: an event_type or a
    second filter can find nothing even when every record is there.
    """
    searchable = _searchable(alert)
    values = {v.lower() for _, v in c2._alert_values(alert)}
    gaps = []
    for c in tool_calls:
        if not c.get("executed") or c.get("returned_ids"):
            continue
        args = c["args"]
        if c["name"] == "event_search":
            used = [k for k in ("user", "src_ip", "event_type") if args.get(k)]
            if len(used) == 1 and used[0] != "event_type" and (used[0], str(args[used[0]]).lower()) in searchable:
                gaps.append(f"event_search {used[0]}={args[used[0]]} found nothing")
        elif c["name"] == "entity_lookup":
            v = str(args.get("id", ""))
            if v.lower() in values and not c2._IPV4.fullmatch(v) and not _BUILT_IN_ACCOUNT.match(v):
                gaps.append(f"entity_lookup id={v} found nothing")
    return list(dict.fromkeys(gaps))  # the same empty lookup run twice is one gap


def answer_problems(answer: dict, retrieved_ids: set[str], records: list[dict], gaps: list[str]) -> list[str]:
    """C2's layer-3 checks, plus guard 1: with a gap, only needs_more_info is accepted."""
    problems = c2.answer_problems(answer, retrieved_ids, records)
    if gaps and answer.get("disposition") != "needs_more_info":
        problems += [f"{gap}, so the alert cannot be confirmed: answer needs_more_info" for gap in gaps]
    return problems


FALLBACK = dict(c2.FALLBACK, summary="Answer withheld: it failed C4's answer checks twice.")


def settle_answer(answer, ask_again, retrieved_ids: set[str], records: list[dict], gaps: list[str]):
    """c2.settle_answer with C4's checks: one repair turn, then the needs_more_info fallback."""
    def problems(a):
        return [c2.INVALID] if a is None else answer_problems(a, retrieved_ids, records, gaps)

    first = problems(answer)
    if not first:
        return answer, {"outcome": "accepted", "problems": []}
    feedback = ("Your answer was not accepted:\n- " + "\n- ".join(first)
                + "\nFix these and reply with the corrected JSON answer only.")
    repaired = ask_again(feedback)
    second = problems(repaired)
    if not second:
        return repaired, {"outcome": "repaired", "problems": [first]}
    return dict(FALLBACK), {"outcome": "fallback", "problems": [first, second]}


# Guard 2, quarantine (ADR 0014). A field layer 1 flags as instruction-like is replaced before the
# model reads it, so a planted instruction never reaches the model. Only what the model is shown
# changes: the run keeps the original record, so layer 3 still reads the planted text as a
# known-bad sign and the scorer still sees what was retrieved.
QUARANTINED = "[withheld by C4: suspected prompt injection]"


def quarantine(records: list[dict]) -> list[dict]:
    """Copies of the records with every flagged field replaced by QUARANTINED."""
    flagged = set(c2.suspected_injections(records))
    return [{field: QUARANTINED if (r.get("evidence_id", "?"), field) in flagged else value
             for field, value in r.items()} for r in records]


# Guard 3, action policy (ADR 0014). ADR 0006's scoring rule for recommendations, enforced while
# the agent runs: an action needs a true_positive verdict and evidence this run retrieved. Actions
# are free text, so no list of action types is enforced. What remains still only goes to the
# approval gate, which never executes anything.
def enforce_action_policy(answer: dict | None, retrieved_ids: set[str]) -> tuple[dict | None, list[dict]]:
    """Return the answer with only the actions the policy allows, and each removed action with why."""
    if not answer:
        return answer, []
    kept, blocked = [], []
    for action in answer.get("proposed_actions", []):
        ids = action.get("evidence_ids", [])
        if answer.get("disposition") != "true_positive":
            reason = f"the answer is {answer.get('disposition')}, not true_positive"
        elif not ids:
            reason = "it cites no evidence"
        elif not set(ids) <= retrieved_ids:
            reason = "it cites evidence no tool returned in this run"
        else:
            kept.append(action)
            continue
        blocked.append({"action": action, "reason": reason})
    return dict(answer, proposed_actions=kept), blocked
