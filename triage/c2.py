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
# wording (docs/research/real-world-guardrails.md), never from held-out cases. Flagged text is kept,
# never deleted: a planted instruction is itself evidence of an attack.
INJECTION_PATTERNS = [
    # Overriding the reader's instructions.
    r"\bignore (all |any )?(the )?(previous|prior|above|earlier|vendor)\b",
    r"\b(disregard|override) (all |any )?(the |your )?(previous|prior|above|instructions|rules)\b",
    r"\byou are now\b",
    # Text addressed to an automated reader rather than to a person.
    r"\b(note|message|instructions?) (to|for) (the |any )?(ai|assistant|llm|automated|triage)\b",
    r"\b(ai|llm|assistant|automated triage|triage (assistant|tools?|automation))\s*:",
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
    return problems


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
