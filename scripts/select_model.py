"""Apply ADR 0007 to dev dry-run results (folders or the zips the notebook saves).

  python scripts/select_model.py results-7b.zip results-14b.zip
"""
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage.select import select_model  # noqa: E402


def run_dirs(paths, tmp):
    for i, p in enumerate(map(Path, paths)):
        if p.suffix == ".zip":
            dest = Path(tmp) / str(i)
            zipfile.ZipFile(p).extractall(dest)
            p = dest
        yield from (f.parent for f in p.rglob("logs.jsonl"))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        dirs = list(run_dirs(sys.argv[1:], tmp))
        if not dirs:
            raise SystemExit("no logs.jsonl found in the given paths")
        table, winner = select_model(dirs)
    print(table.to_string())
    print(f"\nADR 0007 winner: {winner}")
