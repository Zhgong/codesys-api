from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_codesys_boundary_contract_records_approved_and_rejected_primitives() -> None:
    content = (REPO_ROOT / "docs" / "CODESYS_BOUNDARY_CONTRACT.md").read_text(encoding="utf-8")

    assert "scriptengine.projects.create(path, primary=True)" in content
    assert "scriptengine.projects.open(existing_project_path" in content
    assert 'scriptengine.projects.open("...\\\\Templates\\\\Standard.project")' in content
    assert "rejected" in content


def test_codesys_boundary_contract_requires_raw_probe_before_host_dependency() -> None:
    content = (REPO_ROOT / "docs" / "CODESYS_BOUNDARY_CONTRACT.md").read_text(encoding="utf-8")

    assert "add a raw probe using `/api/v1/script/execute`" in content
    assert "only then wrap it in product code" in content
