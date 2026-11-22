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
