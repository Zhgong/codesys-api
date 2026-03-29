from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_continue_tomorrow_tracks_contract_ladder_milestone() -> None:
    content = (REPO_ROOT / "docs" / "CONTINUE_TOMORROW.md").read_text(encoding="utf-8")

    assert "Real CODESYS Contract Ladder v1" in content
    assert "0.3.0" in content
    assert "Do not reframe this as `0.2.x`." in content


def test_continue_tomorrow_points_to_layered_real_validation_entrypoints() -> None:
    content = (REPO_ROOT / "docs" / "CONTINUE_TOMORROW.md").read_text(encoding="utf-8")

    assert "python scripts\\manual\\profile_launch_probe.py --mode shell_string" in content
    assert "python scripts\\manual\\real_project_open_raw_probe.py --mode template" in content
    assert "python scripts\\manual\\real_project_create_direct_raw_probe.py" in content
    assert "python scripts\\manual\\real_pou_code_roundtrip_probe.py" in content
    assert "python scripts\\manual\\real_cli_compile_error_probe.py" in content
    assert "http-all" in content
    assert "cli-all" in content
