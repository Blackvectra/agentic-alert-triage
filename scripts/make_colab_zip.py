"""Build the project zip for Colab from the last commit, then prove it works.

    python scripts/make_colab_zip.py            # writes dist/agentic-alert-triage.zip

Upload the zip when the notebook's setup cell asks. The zip holds one folder,
agentic-alert-triage/, with exactly what is committed (git archive HEAD), so
uncommitted changes would be silently left out: the script refuses to build
until they are committed. Verification unpacks the zip into an empty folder,
installs it in a fresh venv and runs every test, as Colab would start clean.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "agentic-alert-triage.zip"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    if git("status", "--porcelain"):
        print("Uncommitted changes would be missing from the zip. Commit them first, then rerun.")
        return 1
    OUT.parent.mkdir(exist_ok=True)
    git("archive", "--prefix=agentic-alert-triage/", "-o", str(OUT), "HEAD")
    print(f"built {OUT.relative_to(ROOT)} from commit {git('rev-parse', '--short', 'HEAD')}")

    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(OUT).extractall(tmp)
        project = Path(tmp) / "agentic-alert-triage"
        venv.create(Path(tmp) / "venv", with_pip=True)
        python = Path(tmp) / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        for cmd in ([str(python), "-m", "pip", "install", "-q", "-e", ".[dev,report]"],
                    [str(python), "-m", "pytest", "-q"],
                    # Step 6 freeze: the zip must carry the frozen prompts and fixtures.
                    [str(python), "-m", "triage.freeze"]):
            if subprocess.run(cmd, cwd=project).returncode != 0:
                print(f"verification FAILED at: {' '.join(cmd[2:])}  (do not upload this zip)")
                return 1
    print(f"verified: the zip installs and passes every test. Upload {OUT.relative_to(ROOT)} to Colab.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
