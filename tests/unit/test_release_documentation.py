from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_document_references_internal_flow_commands() -> None:
    release_doc = (REPO_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")

    assert "python scripts\\run_baseline.py" in release_doc
    assert "python scripts\\build_release.py" in release_doc
    assert "codesys-cli" in release_doc
    assert "codesys-api-server" in release_doc
    assert "dist\\codesys_api-*.whl" in release_doc
    assert "RELEASE_NOTES.md" in release_doc


def test_release_notes_tracks_current_internal_release_candidate() -> None:
    release_notes = (REPO_ROOT / "docs" / "RELEASE_NOTES.md").read_text(encoding="utf-8")

    assert "## Unreleased" in release_notes
    assert "Current Internal Release Candidate" in release_notes
    assert "Commit: fill this in when cutting the internal release" in release_notes
    assert "160 passed, 8 skipped" in release_notes
    assert "`54` source files" in release_notes
