from __future__ import annotations

from server_logic import (
    build_default_project_path,
    build_status_payload,
    normalize_project_create_params,
    validate_pou_code_params,
    validate_required_params,
)


def test_build_default_project_path_uses_repo_script_dir() -> None:
    path = build_default_project_path(r"C:\repo", "20260317_223000")

    assert path == r"C:\repo\CODESYS_Project_20260317_223000.project"


def test_normalize_project_create_params_adds_default_path_and_preserves_template() -> None:
    params = normalize_project_create_params(
        {"template_path": r"C:\Templates\Standard.project"},
        r"C:\repo",
        "20260317_223000",
    )

    assert params["path"] == r"C:\repo\CODESYS_Project_20260317_223000.project"
    assert params["template_path"] == r"C:\Templates\Standard.project"


def test_normalize_project_create_params_normalizes_windows_slashes() -> None:
    params = normalize_project_create_params(
        {"path": "C:/Temp/MyProject.project"},
        r"C:\repo",
        "20260317_223000",
    )

    assert params["path"] == r"C:\Temp\MyProject.project"


def test_validate_required_params_reports_first_missing_key() -> None:
    error = validate_required_params({"name": "MotorStarter"}, ["name", "type", "language"])

    assert error == "Missing required parameter: type"


def test_validate_pou_code_params_requires_path() -> None:
    error = validate_pou_code_params({"code": "PROGRAM PLC_PRG"})

    assert error == "Missing required parameter: path"


def test_validate_pou_code_params_requires_any_code_field() -> None:
    error = validate_pou_code_params({"path": "Application/PLC_PRG"})

    assert error == (
        "Missing code parameter: need at least one of 'code', 'declaration', or 'implementation'"
    )


def test_build_status_payload_prefers_engine_status_when_available() -> None:
    payload = build_status_payload(
        process_running=True,
        process_status={"state": "running", "timestamp": 123.5},
        session_status_result={
            "success": True,
            "status": {"session_active": True, "project_open": True, "active": True},
        },
        now=999.0,
    )

    assert payload["process"]["running"] is True
    assert payload["process"]["state"] == "running"
    assert payload["process"]["timestamp"] == 123.5
    assert payload["session"]["project_open"] is True


def test_build_status_payload_uses_safe_fallback_when_status_request_fails() -> None:
    payload = build_status_payload(
        process_running=True,
        process_status={"state": "initialized"},
        session_status_result={"success": False, "error": "engine not ready"},
        now=999.0,
    )

    assert payload["process"]["timestamp"] == 999.0
    assert payload["session"] == {
        "active": True,
        "session_active": True,
        "project_open": False,
    }


def test_build_status_payload_reports_inactive_session_when_process_is_down() -> None:
    payload = build_status_payload(
        process_running=False,
        process_status={},
        session_status_result=None,
        now=50.0,
    )

    assert payload["process"] == {
        "running": False,
        "state": "unknown",
        "timestamp": 50.0,
    }
    assert payload["session"] == {
        "active": False,
        "session_active": False,
        "project_open": False,
    }
