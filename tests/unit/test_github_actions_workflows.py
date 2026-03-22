from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ci_workflow_runs_baseline_build_and_public_gate_on_master() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "windows-latest" in workflow
    assert "matrix:" in workflow
    assert '          - "3.13"' in workflow
    assert '          - "3.14"' in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "- master" in workflow
    assert r"python scripts\run_baseline.py" in workflow
    assert r"python scripts\build_release.py" in workflow
    assert r"python scripts\check_public_release.py" in workflow


def test_release_build_workflow_uploads_dist_and_writes_summary() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release-build.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert 'python-version: "3.14"' in workflow
    assert "dist-artifacts" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "Version:" in workflow
    assert "Commit:" in workflow


def test_publish_workflow_uses_manual_targeted_trusted_publishing() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "testpypi" in workflow
    assert "pypi" in workflow
    assert 'python-version: "3.14"' in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "https://test.pypi.org/legacy/" in workflow


def test_verify_published_package_workflow_installs_exact_target_version() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "verify-published-package.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "testpypi" in workflow
    assert "pypi" in workflow
    assert "version:" in workflow
    assert "windows-latest" in workflow
    assert 'python-version: "3.14"' in workflow
    assert r"python scripts\verify_installed_package.py" in workflow
