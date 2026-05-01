from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_management_wiki_references_quality_gates() -> None:
    release_doc = (REPO_ROOT / "docs" / "wiki" / "Release_Management.md").read_text(encoding="utf-8")

    assert "run_baseline.py" in release_doc
    assert "build_release.py" in release_doc
    assert "codesys-tools" in release_doc
    assert "TestPyPI" in release_doc
