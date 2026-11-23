"""Run case x variant x config, write one JSONL log line per run, then score.

  python -m triage.run --split dev --family suspicious_auth                 # free scripted demo
  python -m triage.run --model ollama:qwen2.5:7b --dry-run                  # 9 real runs on AUTH-001
  python -m triage.run --model ollama:qwen2.5:7b --split heldout --out runs/heldout   # resumable

Re-running with the same --out skips runs already logged, so an interrupted
session (e.g. a Colab disconnect) picks up where it stopped.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .agent import Final, is_harness_error, OllamaModel, ScriptedModel, ToolCall, prompt_fingerprint, run_case
from .fixtures import ROOT, VARIANTS, build_view, load_cases
from .jsonl import read_jsonl
from .score import score_run

CONFIGS = ("A", "B", "C")
PLANNED_HELDOUT_CASES = 30  # the proposal's held-out set: 30 x 3 variants x 3 configs = 270 runs
RUNS_PER_CASE = len(VARIANTS) * len(CONFIGS)
DRY_RUN_CASE = "AUTH-001"


def demo_model() -> ScriptedModel:
    """Fixed script to exercise the harness end to end without any model."""
    answer = {"disposition": "true_positive", "abstain": False, "summary": "demo",
              "claims": [{"text": "MFA denied then approved from new IP", "evidence_ids": ["E-EVT-002", "E-EVT-003"]}],
              "proposed_actions": []}
    return ScriptedModel(script=[ToolCall("event_search", {"user": "jdoe@example.org"}),
                                 Final(json.dumps(answer))], name="scripted-demo")


def check_model_name(name: str) -> None:
    """Fail fast on a malformed model name (e.g. a typo in the notebook's settings cell)."""
    ok = name == "scripted-demo" or any(
        name.startswith(prefix) and len(name) > len(prefix) for prefix in ("ollama:", "anthropic:"))
    if not ok:
        raise SystemExit(f"unknown model '{name}': use scripted-demo, ollama:<tag> or anthropic:<model-id>")


def get_model(name: str, host: str = "http://localhost:11434"):
    """Return a factory that makes a fresh model per run (adapters keep per-run state)."""
    check_model_name(name)
    if name == "scripted-demo":
        return demo_model
    if name.startswith("ollama:"):
        tag = name.split(":", 1)[1]
        return lambda: OllamaModel(model_id=tag, host=host)
    if name.startswith("anthropic:"):
        import anthropic  # optional dependency: pip install -e ".[anthropic]"

        from .agent import AnthropicModel
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        model_id = name.split(":", 1)[1]
        return lambda: AnthropicModel(client=client, model_id=model_id)
    raise SystemExit(f"unknown model '{name}': use scripted-demo, ollama:<tag> or anthropic:<model-id>")


def _key(row: dict) -> tuple:
    return (row["case_id"], row["variant"], row["config"])


def _time_left(new_logs: list, remaining: int) -> str:
    """A rough "about N min left" for the progress line; empty after the last run."""
    if not remaining:
        return ""
    # The middle run time, not the average: the first run also loads the model and is much slower.
    typical = statistics.median(l["latency_s"] for l in new_logs)
    return f"  about {max(1, round(typical * remaining / 60))} min left"


def _prepare_resume(out_dir: Path) -> set:
    """Keep only complete runs (a log without a harness error AND a score) and return their keys.

    Incomplete runs are removed from both files so they are rerun once, never duplicated.
    """
    logs_path, scores_path = out_dir / "logs.jsonl", out_dir / "scores.jsonl"
    logs = read_jsonl(logs_path) if logs_path.exists() else []
    scores = read_jsonl(scores_path) if scores_path.exists() else []
    scored = {_key(s) for s in scores}
    # Done = scored, no harness error, and made with the current prompts and tools.
    current = {cfg: prompt_fingerprint(cfg) for cfg in CONFIGS}
    done = {_key(l) for l in logs
            if _key(l) in scored and not is_harness_error(l["error"])
            and l.get("prompt_sha256") == current.get(l["config"])}

    def keep(rows):
        seen, kept = set(), []
        for r in rows:
            if _key(r) in done and _key(r) not in seen:
                seen.add(_key(r))
                kept.append(r)
        return kept

    for path, rows in ((logs_path, logs), (scores_path, scores)):
        if path.exists():
            path.write_text("".join(json.dumps(r) + "\n" for r in keep(rows)))
    return done


def _print_projection(logs: list[dict], price_in: float | None, price_out: float | None,
                      heldout_cases: int) -> None:
    n = len(logs)
    print(f"\n{'config':6} {'runs':>4} {'in tok/run':>11} {'out tok/run':>12} {'sec/run':>8} {'steps/run':>10}")
    for cfg in CONFIGS:
        rs = [l for l in logs if l["config"] == cfg]
        if not rs:
            continue
        k = len(rs)
        print(f"{cfg:6} {k:>4} {sum(l['input_tokens'] for l in rs) / k:>11.0f} "
              f"{sum(l['output_tokens'] for l in rs) / k:>12.0f} {sum(l['latency_s'] for l in rs) / k:>8.1f} "
              f"{sum(len(l.get('stop_reasons', [])) for l in rs) / k:>10.1f}")
    if heldout_cases:
        cases, label = heldout_cases, f"{heldout_cases} held-out cases"
    else:
        cases, label = PLANNED_HELDOUT_CASES, f"planned {PLANNED_HELDOUT_CASES} held-out cases; none written yet"
    target = cases * RUNS_PER_CASE
    scale = target / n
    tin = sum(l["input_tokens"] for l in logs) * scale
    tout = sum(l["output_tokens"] for l in logs) * scale
    hours = sum(l["latency_s"] for l in logs) * scale / 3600
    print(f"\nprojected for {target} runs ({label}): {tin:,.0f} input tokens, {tout:,.0f} output tokens, "
          f"~{hours:.1f} hours of model time")
    if price_in is not None and price_out is not None:
        print(f"projected cost: ${(tin * price_in + tout * price_out) / 1e6:,.2f} "
              f"(at ${price_in}/M input, ${price_out}/M output)")
    print("Projection assumes held-out cases behave like this sample; treat it as a rough estimate.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["dev", "heldout"], help="default: dev")
    ap.add_argument("--family")
    ap.add_argument("--model", default="scripted-demo", help="scripted-demo | ollama:<tag> | anthropic:<model-id>")
    ap.add_argument("--host", default="http://localhost:11434", help="Ollama server URL")
    ap.add_argument("--out", help="output directory; reuse it to resume an interrupted run")
    ap.add_argument("--dry-run", action="store_true", help=f"run {DRY_RUN_CASE} only and project to the held-out pass")
    ap.add_argument("--price-in", type=float, help="USD per million input tokens (paid models only)")
    ap.add_argument("--price-out", type=float, help="USD per million output tokens (paid models only)")
    args = ap.parse_args(argv)

    make_model = get_model(args.model, args.host)
    if args.out:
        out_dir = Path(args.out)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        label = "dryrun" if args.dry_run else (args.split or "dev")
        out_dir = ROOT / "runs" / f"{stamp}_{label}_{args.model.replace(':', '-')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        if args.split or args.family:
            print(f"--dry-run always uses {DRY_RUN_CASE}; ignoring --split/--family")
        cases = [c for c in load_cases() if c["case_id"] == DRY_RUN_CASE]
    else:
        cases = load_cases(args.split or "dev", args.family)

    done = _prepare_resume(out_dir)
    new_logs = []
    planned = [(case["case_id"], variant, config) for case in cases for variant in VARIANTS for config in CONFIGS]
    total = len(planned)
    # Start from what an earlier session already finished, so the counter and the time left
    # only ever count runs that are still to do.
    finished = sum(key in done for key in planned)
    with open(out_dir / "logs.jsonl", "a") as logs, open(out_dir / "scores.jsonl", "a") as scores:
        for case in cases:
            for variant in VARIANTS:
                view = build_view(case, variant)
                for config in CONFIGS:
                    if (case["case_id"], variant, config) in done:
                        continue
                    log = run_case(case, variant, config, make_model(), view)  # fresh model per run
                    logs.write(json.dumps(log) + "\n")
                    scores.write(json.dumps(score_run(log, case)) + "\n")
                    logs.flush(), scores.flush()  # survive a disconnect mid-batch
                    new_logs.append(log)
                    finished += 1
                    print(f"[{finished:{len(str(total))}}/{total}] {case['case_id']} {variant:9} {config}  "
                          f"{log['latency_s']:6.1f}s  error={log['error']}"
                          f"{_time_left(new_logs, total - finished)}", flush=True)

    print(f"{len(new_logs)} new runs, {total - len(new_logs)} already done -> {out_dir}")
    failed = sum(is_harness_error(l["error"]) for l in new_logs)
    if failed:
        print(f"WARNING: {failed} harness errors; rerun the same --out to retry")
    if args.dry_run and new_logs:
        _print_projection(new_logs, args.price_in, args.price_out, len(load_cases("heldout")))


if __name__ == "__main__":
    main()
