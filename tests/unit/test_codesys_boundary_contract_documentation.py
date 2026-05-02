from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_boundary_contract_enforced_in_proven_primitives() -> None:
    content = (REPO_ROOT / "src" / "codesys_api" / "proven_primitives.py").read_text(encoding="utf-8")

    assert "Do NOT add a function here unless the corresponding probe has passed" in content
    assert "build_create_empty_project_fragment" in content
