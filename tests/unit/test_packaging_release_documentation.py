from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_packaging_doc_references_release_helper_and_build_command() -> None:
    packaging = (REPO_ROOT / "docs" / "PACKAGING.md").read_text(encoding="utf-8")

    assert "python scripts\\build_release.py" in packaging
    assert "python -m build" in packaging
    assert "dist/*.whl" in packaging
    assert "dist/*.tar.gz" in packaging


def test_build_release_script_checks_for_build_module_and_runs_python_m_build() -> None:
    script = (REPO_ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")

    assert "__import__(\"build.__main__\")" in script
    assert '[sys.executable, "-m", "build"]' in script
    assert "Release artifacts:" in script
    assert "tomllib" in script
    assert "_verify_artifact_names" in script
    assert "project[\"version\"]" in script
