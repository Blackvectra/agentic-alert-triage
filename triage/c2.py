"""C2: guardrails enforced in code rather than asked for in the prompt (ADR 0012).

This module holds the checks only. They read an answer and say what is wrong with it;
they never change the answer themselves.
"""
from __future__ import annotations

import base64
import binascii
import re


def _text(record: dict, field: str) -> str:
    return str(record.get(field, "")).lower()


# Known-bad indicators (ADR 0012). Each is written from a step in the investigation guides,
# never from the cases or their expected answers. Each entry: what it means, and a test on one
# retrieved record.
KNOWN_BAD = [
    # "Check for MFA fatigue: denied prompts followed by an approval from the same new IP."
    ("MFA prompt denied by the user (MFA fatigue)",
     lambda r: "mfa denied" in _text(r, "failure_reason")),
    # "Check whether that sign-in used legacy authentication that bypasses MFA."
    ("sign-in with legacy authentication, so MFA was not applied",
     lambda r: "legacy authentication" in _text(r, "mfa")),
    # "Check for post-login persistence such as new inbox rules."
    ("new inbox rule (persistence)",
     lambda r: _text(r, "type") == "mailbox_rule_created"),
    # "Check whether a memory dump file was written."
    ("memory dump written",
     lambda r: "minidump" in _text(r, "command_line") or _text(r, "path").endswith(".dmp")),
    # "Escalate as true positive if ... the new admin weakened security controls."
    ("audit setting disabled (security control weakened)",
     lambda r: _text(r, "type") == "audit_setting_changed" and _text(r, "new_value") == "disabled"),
]


def known_bad_indicators(records: list[dict]) -> list[tuple[str, str]]:
    """Return (evidence_id, what it means) for every retrieved record that shows a known-bad sign.

    A suspected prompt injection counts as one (ADR 0012): someone planting instructions for
    the triage tool in the logs is itself a sign of an attack.
    """
    guide_signs = [(r.get("evidence_id", "?"), meaning)
                   for r in records for meaning, test in KNOWN_BAD if test(r)]
    injections = [(eid, f"suspected prompt injection in its {field} field")
                  for eid, field in suspected_injections(records)]
    return guide_signs + injections


# Layer 1 (ADR 0012): instruction-like text in tool output. Written from common prompt-injection
# wording (docs/research/real-world-guardrails.md), never from any case's planted text: words
# fitted to a dev case's injection were removed on 2026-11-28 (code review). Flagged text is kept,
# never deleted: a planted instruction is itself evidence of an attack.
INJECTION_PATTERNS = [
    # Overriding the reader's instructions.
    r"\bignore (all |any )?(the |your )?(previous|prior|above|earlier)\b",
    r"\bignore (all |any )?(the |your |these |this )?(instructions?|rules|guidance|warnings?|alerts?)\b",
    r"\b(disregard|override) (all |any )?(the |your )?(previous|prior|above|instructions|rules)\b",
    r"\byou are now\b",
    # Text addressed to an automated reader rather than to a person.
    r"\b(note|message|instructions?) (to|for) (the |any )?(ai|assistant|llm|automated|triage)\b",
    r"\b(ai|llm|assistant|automated (reader|system|analysis|review|triage))\s*:",
    r"\bsystem (note|prompt|message)\b",
    r"\bbefore answering\b",
    # Telling the reader what verdict to give.
    r"\b(mark|classify|treat|report|close) (this|it|the alert)( alert)? as (benign|a false positive|safe|authori[sz]ed)\b",
]
_INJECTION = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


_BASE64_TOKEN = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


def _readable_text(value) -> str:
    """The field as written, plus any base64 chunks in it decoded, so a hidden instruction is seen too."""
    text = str(value)
    decoded = []
    for token in _BASE64_TOKEN.findall(text):
        try:
            decoded.append(base64.b64decode(token, validate=True).decode("utf-8", "ignore"))
        except (binascii.Error, ValueError):
            continue  # not base64 after all
    return "\n".join([text, *decoded])


def suspected_injections(records: list[dict]) -> list[tuple[str, str]]:
    """Return (evidence_id, field) for every field of a retrieved record that reads like an instruction."""
    return [(r.get("evidence_id", "?"), field)
            for r in records for field, value in r.items()
            if field != "evidence_id" and _INJECTION.search(_readable_text(value))]


def answer_problems(answer: dict, retrieved_ids: set[str], records: list[dict] = ()) -> list[str]:
    """List every reason this answer must not be accepted as it is. Empty means it passes.

    Layer 3 has two checks:
    - Citations: an answer may only cite evidence ids that a tool returned in this run.
      Anything else (a made-up id, or the alert's own id) is not evidence.
    - Known-bad signs: "benign" is not allowed while a retrieved record shows one.
    """
    problems = []
    cited = [eid for item in answer.get("claims", []) + answer.get("proposed_actions", [])
             for eid in item.get("evidence_ids", [])]
    for eid in cited:
        if eid not in retrieved_ids:
            problems.append(f"cited {eid}, which no tool returned in this run")
    if answer.get("disposition") == "benign":
        for eid, meaning in known_bad_indicators(list(records)):
            problems.append(f"answered benign, but {eid} shows a known-bad sign: {meaning}")
    return list(dict.fromkeys(problems))  # a record fetched twice is one reason, not two


# What a failed answer becomes after its one repair turn: abstain and propose nothing. The code
# never sets true_positive itself, so the verdict always comes from the model (ADR 0012).
FALLBACK = {
    "disposition": "needs_more_info", "abstain": True,
    "summary": "Answer withheld: it failed C2's answer checks twice.",
    "claims": [], "proposed_actions": [],
}
INVALID = "the answer was not valid JSON in the required format"


def settle_answer(answer, ask_again, retrieved_ids: set[str], records: list[dict] = ()):
    """Check an answer, allow one repair turn, and fall back to needs_more_info.

    answer is the parsed answer, or None when it was not valid. ask_again(feedback) asks the
    model to fix its answer and returns the new parsed answer (or None). Returns the answer to
    keep and a record of what happened, for the log.
    """
    def problems(a):
        return [INVALID] if a is None else answer_problems(a, retrieved_ids, records)

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


# C3's coverage rule (ADR 0013): before answering, look up every entity the alert names and run
# one unfiltered event_search on every user and IP in it. Built from the alert alone, so it can run
# on real alerts; it never reads a case's answers.
_IPV4 = re.compile(r"\d{1,3}(\.\d{1,3}){3}")


def _alert_values(alert: dict) -> list[tuple[str, str]]:
    """(field, value) for every entity value in the alert, list values one by one, in order."""
    pairs = []
    for field, value in (alert.get("entities") or {}).items():
        for v in value if isinstance(value, list) else [value]:
            pairs.append((field, str(v)))
    return pairs


def missing_coverage(alert: dict, tool_calls: list[dict]) -> list[str]:
    """Name every lookup the coverage rule still needs. Empty means the rule is met.

    Only executed calls count: a rejected call did not look at anything. Matching ignores case.
    A search filtered by event_type does not count, because filtering hid the records that
    cleared the alert in C2's misses.
    """
    ran = [c for c in tool_calls if c.get("executed")]
    looked_up = {str(c["args"].get("id", "")).lower() for c in ran if c["name"] == "entity_lookup"}
    unfiltered = [c["args"] for c in ran if c["name"] == "event_search" and not c["args"].get("event_type")]
    searched = {(k, str(a[k]).lower()) for a in unfiltered for k in ("user", "src_ip") if a.get(k)}

    pairs = list(dict.fromkeys(_alert_values(alert)))
    missing = [f"entity_lookup id={v}" for _, v in pairs if v.lower() not in looked_up]
    for field, v in pairs:
        if field == "user" or "@" in v:
            key = "user"
        elif _IPV4.fullmatch(v):
            key = "src_ip"
        else:
            continue
        if (key, v.lower()) not in searched:
            missing.append(f"event_search {key}={v} (no event_type filter)")
    return missing
