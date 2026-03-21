from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_baseline_document_includes_current_gate_commands() -> None:
    baseline = (REPO_ROOT / "docs" / "BASELINE.md").read_text(encoding="utf-8")

    assert "python -m pytest -q --basetemp C:\\Users\\vboxuser\\Desktop\\pytest_manual_root" in baseline
    assert "python -m mypy" in baseline
    assert "python -m py_compile" in baseline
    assert "158 passed, 8 skipped" in baseline


def test_baseline_document_references_cli_and_http_contracts() -> None:
    baseline = (REPO_ROOT / "docs" / "BASELINE.md").read_text(encoding="utf-8")

    assert "tests/unit/test_codesys_cli.py" in baseline
    assert "tests/unit/test_http_server_system_info.py" in baseline
    assert "tests/unit/test_http_server_system_logs.py" in baseline
    assert "tests/e2e/codesys/test_real_codesys_cli.py" in baseline
    assert "tests/e2e/codesys/test_real_codesys_e2e.py" in baseline


def test_run_baseline_script_executes_expected_tools() -> None:
    script = (REPO_ROOT / "scripts" / "run_baseline.py").read_text(encoding="utf-8")

    assert 'run_step(\n        "pytest"' in script
    assert '"pytest"' in script
    assert '"mypy"' in script
    assert "py_compile ok" in script
