"""Colab setup: always run the newest uploaded project zip, never a stale folder."""
import os
import zipfile

from triage.colab import unpack_latest_zip


def make_zip(path, commit, files, mtime):
    with zipfile.ZipFile(path, "w") as z:
        z.comment = commit.encode()   # git archive stores the commit id here
        for name, text in files.items():
            z.writestr(f"agentic-alert-triage/{name}", text)
    os.utime(path, (mtime, mtime))


def test_newest_zip_replaces_old_code_and_keeps_results(tmp_path):
    project = tmp_path / "agentic-alert-triage"
    (project / "runs").mkdir(parents=True)
    (project / "code.py").write_text("old")
    (project / "runs" / "logs.jsonl").write_text("results")
    make_zip(tmp_path / "agentic-alert-triage.zip", "aaa111", {"code.py": "older"}, 1000)
    make_zip(tmp_path / "agentic-alert-triage (1).zip", "bbb222", {"code.py": "new"}, 2000)  # Colab renames re-uploads

    commit = unpack_latest_zip(tmp_path)

    assert commit == "bbb222"
    assert (project / "code.py").read_text() == "new"
    assert (project / "runs" / "logs.jsonl").read_text() == "results"   # earlier runs survive


def test_no_zip_returns_none(tmp_path):
    assert unpack_latest_zip(tmp_path) is None
