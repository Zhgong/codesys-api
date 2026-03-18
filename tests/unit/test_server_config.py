from __future__ import annotations

from pathlib import Path

from server_config import load_server_config


def test_load_server_config_uses_current_repo_defaults(tmp_path: Path) -> None:
    config = load_server_config(tmp_path, {})

    assert config.server_host == "0.0.0.0"
    assert config.server_port == 8080
    assert config.codesys_path == Path(r"C:\Program Files\CODESYS 3.5.21.0\CODESYS\Common\CODESYS.exe")
    assert config.codesys_profile_name is None
    assert config.codesys_profile_path is None
    assert config.codesys_no_ui is False
    assert config.transport_name == "named_pipe"
    assert config.pipe_name == "codesys_api_session"
    assert config.script_dir == tmp_path
    assert config.persistent_script == tmp_path / "PERSISTENT_SESSION.py"
    assert config.api_key_file == tmp_path / "api_keys.json"
    assert config.request_dir == tmp_path / "requests"
    assert config.result_dir == tmp_path / "results"
    assert config.termination_signal_file == tmp_path / "terminate.signal"
    assert config.status_file == tmp_path / "session_status.json"
    assert config.log_file == tmp_path / "session.log"
    assert config.script_lib_dir == tmp_path / "ScriptLib"


def test_load_server_config_accepts_environment_overrides(tmp_path: Path) -> None:
    config = load_server_config(
        tmp_path,
        {
            "CODESYS_API_SERVER_HOST": "127.0.0.1",
            "CODESYS_API_SERVER_PORT": "9090",
            "CODESYS_API_CODESYS_PATH": r"D:\CODESYS\CODESYS.exe",
            "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP20 Patch 5",
            "CODESYS_API_CODESYS_NO_UI": "true",
            "CODESYS_API_TRANSPORT": "file",
            "CODESYS_API_PIPE_NAME": "codesys_api_test_pipe",
        },
    )

    assert config.server_host == "127.0.0.1"
    assert config.server_port == 9090
    assert config.codesys_path == Path(r"D:\CODESYS\CODESYS.exe")
    assert config.codesys_profile_name == "CODESYS V3.5 SP20 Patch 5"
    assert config.codesys_profile_path is None
    assert config.codesys_no_ui is True
    assert config.transport_name == "file"
    assert config.pipe_name == "codesys_api_test_pipe"


def test_load_server_config_derives_profile_name_from_profile_path(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles" / "My Profile.profile.xml"
    config = load_server_config(
        tmp_path,
        {
            "CODESYS_API_CODESYS_PROFILE_PATH": str(profile_path),
        },
    )

    assert config.codesys_profile_path == profile_path
    assert config.codesys_profile_name == "My Profile"


def test_load_server_config_auto_discovers_single_profile(tmp_path: Path) -> None:
    codesys_path = tmp_path / "Common" / "CODESYS.exe"
    profiles_dir = tmp_path / "Profiles"
    profiles_dir.mkdir(parents=True)
    discovered_profile = profiles_dir / "CODESYS V3.5 SP20 Patch 5.profile.xml"
    discovered_profile.write_text("<Profile />", encoding="utf-8")

    config = load_server_config(
        tmp_path,
        {
            "CODESYS_API_CODESYS_PATH": str(codesys_path),
        },
    )

    assert config.codesys_profile_path == discovered_profile
    assert config.codesys_profile_name == "CODESYS V3.5 SP20 Patch 5"
