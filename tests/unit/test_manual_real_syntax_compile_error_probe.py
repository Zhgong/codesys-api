from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_syntax_compile_error_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_syntax_compile_error_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_syntax_error_implementation_is_hard_error_sample() -> None:
    module = load_probe_module()

    assert module.TARGET_PATH == "Application/PLC_PRG"
    assert module.SYNTAX_ERROR_IMPLEMENTATION == "IF TRUE THEN\n    x := 1;\n"


def test_print_manual_follow_up_includes_project_path_and_steps(capsys: pytest.CaptureFixture[str]) -> None:
    module = load_probe_module()

    module.print_manual_follow_up(r"C:\temp\demo.project")

    captured = capsys.readouterr()
    output = captured.out
    assert r"C:\temp\demo.project" in output
    assert "Application/PLC_PRG" in output
    assert "Compile/build the project manually." in output


def test_is_retryable_project_create_error_matches_threading_exception() -> None:
    module = load_probe_module()

    assert module.is_retryable_project_create_error(
        500,
        {"success": False, "error": "Controls created on one thread cannot be parented to a control on a different thread."},
    )
    assert module.is_retryable_project_create_error(
        500,
        {"success": False, "error": "A primary project is already open at C:\\demo\\Standard.project"},
    )
    assert module.is_retryable_project_create_error(500, {"success": False, "error": "No active project in session"}) is False
    assert module.is_retryable_project_create_error(200, {"success": False, "error": "Controls created on one thread cannot be parented to a control on a different thread."}) is False


def test_create_project_with_retry_retries_only_retryable_threading_error() -> None:
    module = load_probe_module()
    calls: list[tuple[str, str]] = []
    sleep_calls: list[float] = []

    def fake_call_json(base_url: str, path: str, **kwargs: object) -> tuple[int, dict[str, object]]:
        calls.append((base_url, path))
        if path == "/api/v1/project/create" and len([call for call in calls if call[1] == path]) == 1:
            return 500, {
                "success": False,
                "error": "Controls created on one thread cannot be parented to a control on a different thread.",
            }
        return 200, {"success": True}

    status_code, payload, attempts = module.create_project_with_retry(
        base_url="http://127.0.0.1:1234",
        project_path=r"C:\temp\demo.project",
        timeout=120,
        call_json=fake_call_json,
        sleep_fn=sleep_calls.append,
    )

    assert status_code == 200
    assert payload == {"success": True}
    assert attempts == 2
    assert calls == [
        ("http://127.0.0.1:1234", "/api/v1/project/create"),
        ("http://127.0.0.1:1234", "/api/v1/project/close"),
        ("http://127.0.0.1:1234", "/api/v1/session/restart"),
        ("http://127.0.0.1:1234", "/api/v1/project/create"),
    ]
    assert sleep_calls == [module.PROJECT_CREATE_RETRY_DELAY_SECONDS]


def test_recover_after_project_create_failure_closes_and_restarts_session() -> None:
    module = load_probe_module()
    calls: list[tuple[str, str]] = []
    sleep_calls: list[float] = []

    def fake_call_json(base_url: str, path: str, **kwargs: object) -> tuple[int, dict[str, object]]:
        calls.append((base_url, path))
        return 200, {"success": True}

    module.recover_after_project_create_failure(
        base_url="http://127.0.0.1:1234",
        call_json=fake_call_json,
        sleep_fn=sleep_calls.append,
    )

    assert calls == [
        ("http://127.0.0.1:1234", "/api/v1/project/close"),
        ("http://127.0.0.1:1234", "/api/v1/session/restart"),
    ]
    assert sleep_calls == [module.PROJECT_CREATE_RETRY_DELAY_SECONDS]


def test_active_project_matches_requires_expected_session_project_path() -> None:
    module = load_probe_module()

    def fake_call_json(base_url: str, path: str, **kwargs: object) -> tuple[int, dict[str, object]]:
        return 200, {
            "success": True,
            "status": {
                "session": {
                    "project": {
                        "path": r"C:\temp\demo.project",
                    }
                }
            },
        }

    matched, status_code, payload = module.active_project_matches(
        base_url="http://127.0.0.1:1234",
        expected_project_path=r"C:\temp\demo.project",
        call_json=fake_call_json,
    )

    assert matched is True
    assert status_code == 200
    assert payload["success"] is True
