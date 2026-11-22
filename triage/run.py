"""Run case x variant x config and write one JSONL log line per run, then score.

  python -m triage.run --split dev --family suspicious_auth --model scripted-demo
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent import Final, ScriptedModel, ToolCall, run_case
from .fixtures import ROOT, VARIANTS, build_view, load_cases
from .score import score_run

CONFIGS = ("A", "B", "C")


def demo_model() -> ScriptedModel:
    """Fixed script to exercise the harness end to end without an API key."""
    answer = {"disposition": "true_positive", "abstain": False, "summary": "demo",
              "claims": [{"text": "MFA denied then approved from new IP", "evidence_ids": ["E-EVT-002", "E-EVT-003"]}],
              "proposed_actions": []}
    return ScriptedModel(script=[ToolCall("event_search", {"user": "jdoe@example.org"}),
                                 Final(json.dumps(answer))], name="scripted-demo")


def get_model(name: str):
    if name == "scripted-demo":
        return demo_model
    raise SystemExit(f"model '{name}' not wired up yet: add an adapter in triage/agent.py")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "heldout"], default="dev")
    ap.add_argument("--family")
    ap.add_argument("--model", default="scripted-demo")
    args = ap.parse_args(argv)

    make_model = get_model(args.model)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "runs" / f"{stamp}_{args.split}_{args.model}"
    out_dir.mkdir(parents=True)
    cases = load_cases(args.split, args.family)
    with open(out_dir / "logs.jsonl", "w") as logs, open(out_dir / "scores.jsonl", "w") as scores:
        for case in cases:
            for variant in VARIANTS:
                view = build_view(case, variant)
                for config in CONFIGS:
                    log = run_case(case, variant, config, make_model(), view)  # fresh model per run
                    logs.write(json.dumps(log) + "\n")
                    scores.write(json.dumps(score_run(log, case)) + "\n")
    print(f"{len(cases) * len(VARIANTS) * len(CONFIGS)} runs -> {out_dir}")


if __name__ == "__main__":
    main()
