from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_real_codesys_lessons_tracks_key_debugging_learnings() -> None:
    content = (REPO_ROOT / "docs" / "REAL_CODESYS_LESSONS.md").read_text(encoding="utf-8")

    assert "open(Standard.project)" in content
    assert "projects.create(...)" in content
    assert "session.created_pous" in content
    assert "do not widen a workaround" in content

