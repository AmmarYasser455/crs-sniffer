import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_notebook_runs():
    nb = json.loads((ROOT / "examples" / "demo.ipynb").read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert cells
    assert all(c["outputs"] == [] and c["execution_count"] is None for c in cells)
    old = os.getcwd()
    os.chdir(ROOT)
    try:
        ns = {}
        for c in cells:
            exec("".join(c["source"]), ns)
    finally:
        os.chdir(old)
