"""The agentic_triage notebook is the deliverable: it must run top to bottom.

The saved defaults are the real held-out run, so the test first switches the
settings cell to the fake model and a dry run (no model, GPU, network, key or Drive),
then fails on the first cell that raises. Output goes to the gitignored runs/.
"""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOK = Path(__file__).resolve().parent.parent / "notebooks" / "agentic_triage.ipynb"


def test_agentic_triage_notebook_runs_without_errors():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    settings = next(c for c in nb.cells if c.cell_type == "code" and "MODEL = " in c.source)
    settings.source += '\nMODEL, RUN, SAVE_TO_DRIVE = "scripted-demo", "dry-run", False\n'
    # Raises CellExecutionError, naming the failing cell, if any cell errors.
    NotebookClient(nb, timeout=180, kernel_name="python3",
                   resources={"metadata": {"path": str(NOTEBOOK.parent)}}).execute()
