"""Seam 3: the triage.run command line. Uses the scripted model: no network."""
import json

from triage import run
from triage.agent import OllamaModel


def _dev_only(monkeypatch):
    # Pretend no held-out cases exist yet, so projection tests stay stable as cases are added.
    real = run.load_cases()
    monkeypatch.setattr(run, "load_cases",
                        lambda split=None, family=None: [c for c in real if c["split"] == "dev" and split in (None, "dev")])


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def test_model_names_select_the_adapter():
    m = run.get_model("ollama:qwen2.5:7b", host="http://localhost:11434")()
    assert isinstance(m, OllamaModel) and m.model_id == "qwen2.5:7b"
    assert run.get_model("scripted-demo")().name == "scripted-demo"


def test_dry_run_covers_auth_001_only_and_projects_to_270(tmp_path, capsys, monkeypatch):
    _dev_only(monkeypatch)
    run.main(["--dry-run", "--out", str(tmp_path / "dry")])

    logs = lines(tmp_path / "dry" / "logs.jsonl")
    assert len(logs) == 9 and {l["case_id"] for l in logs} == {"AUTH-001"}
    out = capsys.readouterr().out
    assert "projected for 270 runs" in out


def test_each_run_prints_its_place_in_the_batch_and_the_time_left(tmp_path, capsys):
    run.main(["--dry-run", "--out", str(tmp_path / "dry")])
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("[1/9] AUTH-001 complete  A") and out[0].endswith("min left")
    assert out[8].startswith("[9/9] AUTH-001 injected  C") and "min left" not in out[8]


def test_progress_counts_runs_an_earlier_session_already_did(tmp_path, capsys):
    out_dir = tmp_path / "dry"
    run.main(["--dry-run", "--out", str(out_dir)])
    for name in ("logs.jsonl", "scores.jsonl"):   # drop the last run, as a disconnect would
        kept = (out_dir / name).read_text().splitlines()[:-1]
        (out_dir / name).write_text("\n".join(kept) + "\n")
    capsys.readouterr()
    run.main(["--dry-run", "--out", str(out_dir)])
    assert capsys.readouterr().out.splitlines()[0].startswith("[9/9] AUTH-001 injected  C")


def test_time_left_on_a_resumed_run_counts_only_the_runs_still_to_do(tmp_path, capsys):
    out_dir = tmp_path / "dry"
    run.main(["--dry-run", "--out", str(out_dir)])
    logs = lines(out_dir / "logs.jsonl")
    logs[0]["error"] = "URLError: timed out"   # the very first run failed; the eight after it are fine
    _rewrite(out_dir / "logs.jsonl", logs)
    capsys.readouterr()
    run.main(["--dry-run", "--out", str(out_dir)])
    first = capsys.readouterr().out.splitlines()[0]
    # One run to redo: it is the 9th to finish and nothing is left after it.
    assert first.startswith("[9/9] AUTH-001 complete  A") and "min left" not in first


def test_time_left_uses_the_typical_run_not_the_slow_first_one():
    logs = [{"latency_s": 600.0}, {"latency_s": 60.0}, {"latency_s": 60.0}]
    assert run._time_left(logs, 10) == "  about 10 min left"
    assert run._time_left(logs, 0) == ""


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


def test_projection_uses_the_planned_30_cases_when_none_are_written_yet(tmp_path, capsys, monkeypatch):
    _dev_only(monkeypatch)
    run.main(["--dry-run", "--out", str(tmp_path / "p")])
    out = capsys.readouterr().out
    assert "projected for 270 runs (planned 30 held-out cases; none written yet)" in out


def test_projection_counts_the_held_out_cases_that_exist(tmp_path, capsys, monkeypatch):
    import copy
    real = [c for c in run.load_cases() if c["split"] == "dev"]
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


def test_resume_reruns_runs_read_by_an_older_answer_parser(tmp_path, capsys):
    # Dev run (2026-11-23): config A's prompt did not change when the parser learned to read
    # code blocks, so its 36 old "no answer" rows would have been kept on resume (ADR 0010).
    out = tmp_path / "oldparser"
    run.main(["--dry-run", "--out", str(out)])
    logs = lines(out / "logs.jsonl")
    for l in logs:
        if l["config"] == "A":
            l.pop("answer_parser", None)   # as written by code from before the version was logged
    _rewrite(out / "logs.jsonl", logs)
    capsys.readouterr()

    run.main(["--dry-run", "--out", str(out)])

    assert "3 new runs, 6 already done" in capsys.readouterr().out
    again = lines(out / "logs.jsonl")
    assert len(again) == 9 and len(lines(out / "scores.jsonl")) == 9
    assert all("answer_parser" in l for l in again)


def test_model_name_typo_fails_fast_with_the_valid_forms():
    import pytest
    for ok in ("scripted-demo", "ollama:qwen2.5:7b", "anthropic:claude-sonnet-5-5"):
        run.check_model_name(ok)   # no error
    with pytest.raises(SystemExit) as err:
        run.check_model_name("ollm:qwen2.5:7b")   # the typo seen in Colab
    assert "ollama:<tag>" in str(err.value)
    with pytest.raises(SystemExit):
        run.check_model_name("ollama:")            # prefix with no model tag


def test_run_warns_when_harness_errors_remain(tmp_path, capsys, monkeypatch):
    original = run.demo_model

    def broken():
        m = original()
        m.script = []   # nothing scripted: the adapter raises, like a dropped server
        return m
    monkeypatch.setattr(run, "demo_model", broken)
    run.main(["--dry-run", "--out", str(tmp_path / "x")])
    assert "9 harness errors; rerun the same --out to retry" in capsys.readouterr().out
