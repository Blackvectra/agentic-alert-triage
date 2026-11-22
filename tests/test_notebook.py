"""The walkthrough notebook is the deliverable: it must run top to bottom.

Executes it as saved (MODEL = "scripted-demo": no model, GPU, network or key)
and fails on the first cell that raises. Output goes to the gitignored runs/.
"""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOK = Path(__file__).resolve().parent.parent / "notebooks" / "01_walkthrough.ipynb"


def test_walkthrough_notebook_runs_without_errors():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    # Raises CellExecutionError, naming the failing cell, if any cell errors.
    NotebookClient(nb, timeout=180, kernel_name="python3",
                   resources={"metadata": {"path": str(NOTEBOOK.parent)}}).execute()
