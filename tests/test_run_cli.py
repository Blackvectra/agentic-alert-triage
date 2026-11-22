"""Seam 3: the triage.run command line. Uses the scripted model: no network."""
import json

from triage import run
from triage.agent import OllamaModel


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def test_model_names_select_the_adapter():
    m = run.get_model("ollama:qwen2.5:7b", host="http://localhost:11434")()
    assert isinstance(m, OllamaModel) and m.model_id == "qwen2.5:7b"
    assert run.get_model("scripted-demo")().name == "scripted-demo"


def test_dry_run_covers_auth_001_only_and_projects_to_270(tmp_path, capsys):
    run.main(["--dry-run", "--out", str(tmp_path / "dry")])

    logs = lines(tmp_path / "dry" / "logs.jsonl")
    assert len(logs) == 9 and {l["case_id"] for l in logs} == {"AUTH-001"}
    out = capsys.readouterr().out
    assert "projected for 270 runs" in out


def test_dry_run_prints_cost_only_when_prices_given(tmp_path, capsys):
    run.main(["--dry-run", "--out", str(tmp_path / "a")])
    assert "$" not in capsys.readouterr().out
    run.main(["--dry-run", "--out", str(tmp_path / "b"), "--price-in", "2", "--price-out", "10"])
    assert "$" in capsys.readouterr().out


def test_rerun_resumes_without_duplicating_runs(tmp_path):
    out = tmp_path / "r"
    run.main(["--split", "dev", "--out", str(out)])
    first = lines(out / "logs.jsonl")
    # Simulate a disconnect: keep only the first 4 runs.
    for name in ("logs.jsonl", "scores.jsonl"):
        p = out / name
        p.write_text("\n".join(p.read_text().splitlines()[:4]) + "\n")

    run.main(["--split", "dev", "--out", str(out)])

    again = lines(out / "logs.jsonl")
    key = lambda l: (l["case_id"], l["variant"], l["config"])
    assert sorted(map(key, again)) == sorted(map(key, first))
    assert len(lines(out / "scores.jsonl")) == len(first)


def _rewrite(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_resume_retries_runs_that_errored(tmp_path):
    out = tmp_path / "e"
    run.main(["--dry-run", "--out", str(out)])
    logs = lines(out / "logs.jsonl")
    logs[0]["error"] = "URLError: timed out"  # e.g. the Ollama server dropped mid-run
    _rewrite(out / "logs.jsonl", logs)

    run.main(["--dry-run", "--out", str(out)])

    again = lines(out / "logs.jsonl")
    assert len(again) == 9 and len(lines(out / "scores.jsonl")) == 9  # retried, not duplicated
    assert all(l["error"] is None for l in again)


def test_resume_reruns_a_logged_run_that_has_no_score(tmp_path):
    out = tmp_path / "s"
    run.main(["--dry-run", "--out", str(out)])
    scores = lines(out / "scores.jsonl")
    lost = scores.pop()  # crash between writing the log and writing the score
    _rewrite(out / "scores.jsonl", scores)

    run.main(["--dry-run", "--out", str(out)])

    key = lambda r: (r["case_id"], r["variant"], r["config"])
    assert sum(key(l) == key(lost) for l in lines(out / "logs.jsonl")) == 1
    assert sum(key(s) == key(lost) for s in lines(out / "scores.jsonl")) == 1


def test_resume_keeps_a_model_that_ran_out_of_budget(tmp_path):
    # Exhausting the call budget is the model's behaviour, a real result: never retried.
    out = tmp_path / "b"
    run.main(["--dry-run", "--out", str(out)])
    logs = lines(out / "logs.jsonl")
    logs[0]["error"] = "budget_exhausted_without_answer"
    _rewrite(out / "logs.jsonl", logs)

    run.main(["--dry-run", "--out", str(out)])

    assert lines(out / "logs.jsonl")[0]["error"] == "budget_exhausted_without_answer"
    assert len(lines(out / "logs.jsonl")) == 9


def test_projection_uses_the_planned_30_cases_when_none_are_written_yet(tmp_path, capsys):
    run.main(["--dry-run", "--out", str(tmp_path / "p")])
    out = capsys.readouterr().out
    assert "projected for 270 runs (planned 30 held-out cases; none written yet)" in out


def test_projection_counts_the_held_out_cases_that_exist(tmp_path, capsys, monkeypatch):
    import copy
    real = run.load_cases()
    held = []
    for i in (1, 2):
        c = copy.deepcopy(real[0])
        c["case_id"], c["split"] = f"AUTH-90{i}", "heldout"
        held.append(c)
    monkeypatch.setattr(run, "load_cases",
                        lambda split=None, family=None: [c for c in real + held if split in (None, c["split"])])

    run.main(["--dry-run", "--out", str(tmp_path / "h")])

    assert "projected for 18 runs (2 held-out cases)" in capsys.readouterr().out


def test_dry_run_says_split_and_family_are_ignored(tmp_path, capsys):
    run.main(["--dry-run", "--split", "heldout", "--family", "suspicious_auth", "--out", str(tmp_path / "w")])
    assert "--dry-run always uses AUTH-001; ignoring --split/--family" in capsys.readouterr().out


def test_resume_reruns_runs_made_with_different_prompts_or_tools(tmp_path):
    # Colab reused an old run folder: 9 runs from older code were "done", so nothing ran.
    out = tmp_path / "stale"
    run.main(["--dry-run", "--out", str(out)])
    logs = lines(out / "logs.jsonl")
    logs[0]["prompt_sha256"] = "0" * 64   # as if made before a tool change (ADR 0005)
    _rewrite(out / "logs.jsonl", logs)

    run.main(["--dry-run", "--out", str(out)])

    again = lines(out / "logs.jsonl")
    assert len(again) == 9 and len(lines(out / "scores.jsonl")) == 9
    assert all(l["prompt_sha256"] != "0" * 64 for l in again)
