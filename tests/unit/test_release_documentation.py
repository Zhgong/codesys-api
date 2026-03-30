from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_document_references_internal_flow_commands() -> None:
    release_doc = (REPO_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")

    assert "python scripts\\run_baseline.py" in release_doc
    assert "python scripts\\build_release.py" in release_doc
    assert "codesys-tools" in release_doc
    assert "codesys-tools-server" in release_doc
    assert "dist\\codesys_tools-*.whl" in release_doc
    assert "RELEASE_NOTES.md" in release_doc
    assert ".github/workflows/ci.yml" in release_doc
    assert ".github/workflows/verify-published-package.yml" in release_doc
    assert "TestPyPI" in release_doc


def test_release_notes_has_unreleased_section() -> None:
    release_notes = (REPO_ROOT / "docs" / "RELEASE_NOTES.md").read_text(encoding="utf-8")

    assert "## Unreleased" in release_notes
