from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_public_release_gate_runs_baseline_build_and_wheel_smoke() -> None:
    script = (REPO_ROOT / "scripts" / "check_public_release.py").read_text(encoding="utf-8")

    assert 'run_step("baseline"' in script
    assert 'run_step("build"' in script
    assert 'scripts\\run_baseline.py' in script
    assert 'scripts\\build_release.py' in script
    assert "codesys-cli.exe" in script
    assert "codesys-api-server.exe" in script
    assert "public_release_smoke" in script


def test_public_release_gate_checks_required_public_metadata_and_docs() -> None:
    script = (REPO_ROOT / "scripts" / "check_public_release.py").read_text(encoding="utf-8")

    assert 'Homepage = "https://github.com/Zhgong/codesys-api"' in script
    assert "Development Status :: 3 - Alpha" in script
    assert 'assert_contains(README_PATH, "Windows-only")' in script
    assert 'assert_contains(README_PATH, "experimental")' in script
    assert 'assert_contains(README_PATH, "local CODESYS")' in script
