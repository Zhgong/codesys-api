from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_baseline_script_executes_expected_tools() -> None:
    script = (REPO_ROOT / "scripts" / "run_baseline.py").read_text(encoding="utf-8")

    assert 'run_step(\n        "pytest"' in script
    assert '"pytest"' in script
    assert '"mypy"' in script
    assert "py_compile ok" in script
