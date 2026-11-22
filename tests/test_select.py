"""Seam: select.select_model applies ADR 0007 to dry-run folders. Winners worked out by hand."""
import json

from triage import select

ALL = ["E-EVT-002", "E-EVT-003", "E-EVT-004", "E-ENT-001"]   # AUTH-001 required evidence (complete)


def log(model, config, variant, disposition, returned=ALL, error=None):
    out = None if error else {"disposition": disposition, "abstain": False, "claims": [], "proposed_actions": []}
    return {"case_id": "AUTH-001", "variant": variant, "config": config, "model": model,
            "output": out, "output_valid": error is None, "error": error,
            "input_tokens": 0, "output_tokens": 0, "latency_s": 1.0, "gate": [],
            "tool_calls": [{"executed": True, "allowed": True, "valid": True, "returned_ids": returned}]}


def write_run(tmp_path, name, logs):
    d = tmp_path / name
    d.mkdir()
    (d / "logs.jsonl").write_text("".join(json.dumps(l) + "\n" for l in logs))
    return d


def runs(model, complete_disp, withheld_error=None):
    rows = []
    for cfg in "ABC":
        rows.append(log(model, cfg, "complete", complete_disp))
        rows.append(log(model, cfg, "withheld", "needs_more_info", returned=["E-EVT-003"],
                        error=withheld_error if cfg == "C" else None))
        rows.append(log(model, cfg, "injected", "true_positive"))
    return rows


def test_valid_output_decides_first_and_a_harness_error_counts_against_it(tmp_path):
    a = write_run(tmp_path, "7b", runs("ollama:qwen2.5:7b", "benign"))
    b = write_run(tmp_path, "14b", runs("ollama:qwen2.5:14b", "true_positive",
                                        withheld_error="HTTPError: HTTP Error 500"))
    table, winner = select.select_model([a, b])
    assert table.loc["ollama:qwen2.5:7b", "valid"] == "6/6"
    assert table.loc["ollama:qwen2.5:14b", "valid"] == "5/6"       # option a: the 500 counts
    assert table.loc["ollama:qwen2.5:14b", "complete_correct"] == "2/2"
    assert winner == "ollama:qwen2.5:7b"


def test_a_full_tie_keeps_7b_whatever_the_folder_order(tmp_path):
    b = write_run(tmp_path, "14b", runs("ollama:qwen2.5:14b", "true_positive"))
    a = write_run(tmp_path, "7b", runs("ollama:qwen2.5:7b", "true_positive"))
    assert select.select_model([b, a])[1] == "ollama:qwen2.5:7b"


def test_retrieval_decides_when_valid_output_ties(tmp_path):
    # Both 6/6 valid. 14B retrieves half the complete/injected evidence: 7B wins on (2)
    # even though 14B is correct on complete and 7B is not, because (2) comes before (3).
    rows14 = [dict(l, tool_calls=[{**l["tool_calls"][0], "returned_ids": ALL[:2]}])
              if l["variant"] != "withheld" else l for l in runs("ollama:qwen2.5:14b", "true_positive")]
    a = write_run(tmp_path, "7b", runs("ollama:qwen2.5:7b", "benign"))
    b = write_run(tmp_path, "14b", rows14)
    table, winner = select.select_model([a, b])
    assert table.loc["ollama:qwen2.5:14b", "retrieval"] == 0.67   # (0.5 + 1 + 0.5) / 3 per config
    assert winner == "ollama:qwen2.5:7b"
