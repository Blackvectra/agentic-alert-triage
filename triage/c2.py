"""C2: guardrails enforced in code rather than asked for in the prompt (ADR 0012).

This module holds the checks only. They read an answer and say what is wrong with it;
they never change the answer themselves.
"""
from __future__ import annotations


def answer_problems(answer: dict, retrieved_ids: set[str]) -> list[str]:
    """List every reason this answer must not be accepted as it is. Empty means it passes.

    Layer 3, citation check: an answer may only cite evidence ids that a tool returned
    in this run. Anything else (a made-up id, or the alert's own id) is not evidence.
    """
    problems = []
    cited = [eid for item in answer.get("claims", []) + answer.get("proposed_actions", [])
             for eid in item.get("evidence_ids", [])]
    for eid in cited:
        if eid not in retrieved_ids:
            problems.append(f"cited {eid}, which no tool returned in this run")
    return problems
