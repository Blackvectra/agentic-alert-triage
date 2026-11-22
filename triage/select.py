"""Apply ADR 0007's model selection rule to dev dry-run folders.

Across configs B and C, compare (1) valid output, (2) required-evidence retrieval,
(3) correct disposition on the complete variant, in that order. A full tie keeps 7B.
A harness error (e.g. Ollama HTTP 500) counts as invalid output: a model the GPU
cannot run reliably is not usable for 270 runs.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pandas as pd

from .fixtures import load_cases
from .jsonl import read_jsonl
from .score import score_run

DEFAULT_MODEL = "ollama:qwen2.5:7b"   # kept on a tie (ADR 0007)


def _criteria(logs: list[dict], cases: dict) -> tuple:
    bc = [l for l in logs if l["config"] in ("B", "C")]
    valid = sum(bool(l["output_valid"]) and l["error"] is None for l in bc)
    recalls = []
    for l in bc:
        required = set(cases[l["case_id"]]["variants"][l["variant"]].get("required_evidence", []))
        if required:
            got = {i for c in l["tool_calls"] if c["executed"] for i in c["returned_ids"]}
            recalls.append(Fraction(len(required & got), len(required)))
    complete = [l for l in bc if l["variant"] == "complete"]
    correct = sum(score_run(l, cases[l["case_id"]])["disposition_correct"] for l in complete)
    retrieval = sum(recalls) / len(recalls) if recalls else Fraction(0)
    return (Fraction(valid, len(bc)), retrieval, Fraction(correct, len(complete) or 1)), \
        (valid, len(bc), correct, len(complete))


def select_model(run_dirs: list[Path]) -> tuple[pd.DataFrame, str]:
    cases = {c["case_id"]: c for c in load_cases()}
    by_model: dict[str, list[dict]] = {}
    for d in run_dirs:
        for l in read_jsonl(Path(d) / "logs.jsonl"):
            by_model.setdefault(l["model"], []).append(l)
    rows, keys = {}, {}
    for model, logs in by_model.items():
        key, (v, n, c, k) = _criteria(logs, cases)
        keys[model] = key
        rows[model] = {"valid": f"{v}/{n}", "retrieval": round(float(key[1]), 2),
                       "complete_correct": f"{c}/{k}"}
    best = max(keys.values())
    tied = [m for m, k in keys.items() if k == best]
    winner = DEFAULT_MODEL if DEFAULT_MODEL in tied else tied[0]
    return pd.DataFrame.from_dict(rows, orient="index"), winner
