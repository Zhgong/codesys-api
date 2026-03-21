from __future__ import annotations

from pathlib import Path

from _repo_bootstrap import bootstrap_src_path

bootstrap_src_path()

from codesys_api.runtime_paths import (
    default_api_key_file,
    default_runtime_log_dir,
    default_user_data_dir,
    packaged_persistent_script,
    packaged_script_lib_dir,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_packaged_asset_paths_point_inside_package_tree() -> None:
    assert packaged_persistent_script() == REPO_ROOT / "src" / "codesys_api" / "assets" / "PERSISTENT_SESSION.py"
    assert packaged_script_lib_dir() == REPO_ROOT / "src" / "codesys_api" / "assets" / "ScriptLib"


def test_default_api_key_file_uses_appdata_when_available(tmp_path: Path) -> None:
    env = {"APPDATA": str(tmp_path / "Roaming")}

    assert default_user_data_dir(env) == tmp_path / "Roaming" / "codesys-api"
    assert default_api_key_file(env) == tmp_path / "Roaming" / "codesys-api" / "api_keys.json"
    assert default_runtime_log_dir(env) == tmp_path / "Roaming" / "codesys-api" / "logs"
