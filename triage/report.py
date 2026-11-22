"""Turn a run folder's scores.jsonl (and logs.jsonl) into per-config tables and plots.

  python -m triage.report runs/<run-folder>

Writes runs/<run-folder>/report/: summary.csv, summary.md and PNG plots.
Every number here is derived from score rows produced by the fixed rules in
score.py; this module adds no judgement of its own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .jsonl import read_jsonl

CONFIGS = ["A", "B", "C"]
LABELS = ["true_positive", "benign", "needs_more_info"]
ABSTAIN_CELLS = ["answered", "correct_abstain", "abstained_when_could_answer", "answered_when_should_abstain"]


def _macro_f1(expected: list, predicted: list) -> float:
    """Mean F1 over the three expected labels. An unusable answer (None) is wrong for every label."""
    f1s = []
    for label in LABELS:
        tp = sum(e == label and p == label for e, p in zip(expected, predicted))
        fp = sum(e != label and p == label for e, p in zip(expected, predicted))
        fn = sum(e == label and p != label for e, p in zip(expected, predicted))
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(f1s) / len(f1s)


def _mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict], logs: list[dict] | None = None) -> pd.DataFrame:
    """One row per config with every metric the report compares."""
    out = {}
    for cfg in sorted({r["config"] for r in rows}):
        rs = [r for r in rows if r["config"] == cfg]
        attacks = [r for r in rs if r["expected_disposition"] == "true_positive"]
        withheld = [r for r in rs if r["variant"] == "withheld"]
        injected = [r for r in rs if r["variant"] == "injected" and r.get("injection")]
        cells = {c: sum(r["abstain_cell"] == c for r in rs) for c in ABSTAIN_CELLS}
        m = {
            "runs": len(rs),
            "disposition_accuracy": _mean([float(r["disposition_correct"]) for r in rs]),
            "macro_f1": _macro_f1([r["expected_disposition"] for r in rs], [r["predicted_disposition"] for r in rs]),
            # Attacks not called true_positive (Tsegai et al. 2026 lead with this rate).
            "missed_attack_rate": _mean([float(r["predicted_disposition"] != "true_positive") for r in attacks]),
            # Withheld evidence called benign: the "empty search means nothing happened" failure.
            "withheld_called_benign": _mean([float(r["predicted_disposition"] == "benign") for r in withheld]),
            "supported_claim_rate": _mean([r["supported_claim_rate"] for r in rs]),
            "evidence_recall": _mean([r["evidence_recall"] for r in rs]),
            "runs_with_fabricated_citations": sum(bool(r["fabricated_citations"]) for r in rs),
            "unauthorized_attempts": sum(r["unauthorized_attempts"] for r in rs),
            "unauthorized_executed": sum(r["unauthorized_executed"] for r in rs),
            "injection_success": _mean([float(r["injection"]["success"]) for r in injected]),
            "injection_canary": _mean([float(r["injection"]["canary"]) for r in injected]),
            "injection_disposition_flip": _mean([float(r["injection"]["disposition_flip"]) for r in injected]),
            "injection_tool_attempt": _mean([float(r["injection"]["tool_attempt"]) for r in injected]),
            "output_valid_rate": _mean([float(bool(r["output_valid"])) for r in rs]),
            "errors": sum(r["error"] is not None for r in rs),
            "mean_tokens": _mean([r["tokens"] for r in rs]),
            "mean_latency_s": _mean([r["latency_s"] for r in rs]),
            **cells,
        }
        if logs is not None:
            # Provider refusals are reported apart from guardrail abstentions (ADR 0003).
            # A model that cannot report refusals (local Ollama, scripted) shows n/a, not 0.
            cfg_logs = [l for l in logs if l["config"] == cfg]
            m["refusals"] = (sum(any(str(s).startswith("refusal") for s in l.get("stop_reasons", []))
                                 for l in cfg_logs)
                             if any(l.get("refusals_measured") for l in cfg_logs) else None)
        out[cfg] = m
    return pd.DataFrame.from_dict(out, orient="index")


def confusion(rows: list[dict]) -> dict[str, pd.DataFrame]:
    """Per config: counts of expected disposition (rows) by predicted disposition (columns).

    Unusable output has no prediction and is counted under "no_answer".
    """
    cols = LABELS + ["no_answer"]
    out = {}
    for cfg in sorted({r["config"] for r in rows}):
        cm = pd.DataFrame(0, index=LABELS, columns=cols)
        for r in rows:
            if r["config"] == cfg:
                cm.loc[r["expected_disposition"], r["predicted_disposition"] or "no_answer"] += 1
        cm.index.name = "expected \\ predicted"
        out[cfg] = cm
    return out


def injection_by_label(rows: list[dict], cases: list[dict]) -> pd.DataFrame:
    """Injection success rate per config, by delivery technique and by attacker intent."""
    labels = {c["case_id"]: c["variants"]["injected"]["injection"] for c in cases}
    recs = []
    for r in rows:
        if r["variant"] != "injected" or not r.get("injection") or r["case_id"] not in labels:
            continue
        inj = labels[r["case_id"]]
        recs.append({"config": r["config"], "label": f"delivery={inj['delivery']}", "success": r["injection"]["success"]})
        for intent in inj["intent"]:
            recs.append({"config": r["config"], "label": f"intent={intent}", "success": r["injection"]["success"]})
    if not recs:
        return pd.DataFrame()
    return pd.DataFrame(recs).pivot_table(index="label", columns="config", values="success", aggfunc="mean")


COUNT_METRICS = {"runs", "runs_with_fabricated_citations", "unauthorized_attempts", "unauthorized_executed",
                 "errors", "refusals", *ABSTAIN_CELLS}


def _markdown(df: pd.DataFrame) -> str:
    def fmt(v, count):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "n/a"
        if count:
            return str(int(v))
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    t = df.T  # metrics as rows, configs as columns: easier to read
    lines = ["| metric | " + " | ".join(map(str, t.columns)) + " |", "|---" * (len(t.columns) + 1) + "|"]
    lines += [f"| {idx} | " + " | ".join(fmt(v, idx in COUNT_METRICS) for v in t.loc[idx]) + " |" for idx in t.index]
    return "\n".join(lines) + "\n"


def _table(df: pd.DataFrame) -> str:
    """Plain Markdown table of counts, rows and columns as given."""
    lines = [f"| {df.index.name or ''} | " + " | ".join(map(str, df.columns)) + " |",
             "|---" * (len(df.columns) + 1) + "|"]
    lines += [f"| {idx} | " + " | ".join(str(int(v)) for v in df.loc[idx]) + " |" for idx in df.index]
    return "\n".join(lines) + "\n"


def _plots(s: pd.DataFrame, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")  # no display needed (Colab, CI)
    import matplotlib.pyplot as plt

    def bars(cols, title, fname, ylabel="rate"):
        ax = s[cols].astype(float).plot.bar(figsize=(8, 4), rot=0)
        ax.set_title(title), ax.set_xlabel("config"), ax.set_ylabel(ylabel)
        if ylabel == "rate":
            ax.set_ylim(0, 1.05)  # rates on a fixed scale so plots compare across runs
        ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
        plt.tight_layout(), plt.savefig(out / fname, dpi=150), plt.close()

    bars(["disposition_accuracy", "macro_f1", "supported_claim_rate", "evidence_recall"],
         "Accuracy and evidence support by config", "accuracy_support.png")
    bars(["missed_attack_rate", "withheld_called_benign", "injection_success"],
         "Failure rates by config (lower is better)", "failure_rates.png")
    bars(["unauthorized_attempts", "unauthorized_executed"],
         "Unauthorized tool use: attempted vs executed", "unauthorized.png", ylabel="count")
    bars(ABSTAIN_CELLS, "Abstention 2x2 by config", "abstention.png", ylabel="runs")
    bars(["mean_tokens"], "Mean tokens per run", "tokens.png", ylabel="tokens")


def write_report(run_dir) -> Path:
    run_dir = Path(run_dir)
    rows = read_jsonl(run_dir / "scores.jsonl")
    logs_path = run_dir / "logs.jsonl"
    logs = read_jsonl(logs_path) if logs_path.exists() else None
    out = run_dir / "report"
    out.mkdir(exist_ok=True)

    s = summarize(rows, logs)
    s.to_csv(out / "summary.csv")
    md = ["# Results by config\n", f"Source: `{run_dir.name}` ({len(rows)} runs)\n", _markdown(s)]
    try:
        from .fixtures import load_cases
        by_label = injection_by_label(rows, load_cases())
    except Exception as exc:  # report still useful without the case labels
        by_label, md = pd.DataFrame(), md + [f"\n(injection breakdown unavailable: {exc})\n"]
    md.append("\n## Confusion matrices\nRows: expected disposition. Columns: what the model answered.\n")
    for cfg, cm in confusion(rows).items():
        cm.to_csv(out / f"confusion_{cfg}.csv")
        md += [f"\n### Confusion matrix: config {cfg}\n", _table(cm)]
    if not by_label.empty:
        by_label.to_csv(out / "injection_by_label.csv")
        md += ["\n## Injection success by label\n", _markdown(by_label.T)]
    (out / "summary.md").write_text("\n".join(md))
    _plots(s, out)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m triage.report runs/<run-folder>")
    print(f"report written to {write_report(sys.argv[1])}")
