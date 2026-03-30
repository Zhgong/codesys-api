from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_cli_compile_error_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_cli_compile_error_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_is_benign_cli_stderr_accepts_known_startup_warning() -> None:
    module = load_probe_module()

    assert module.is_benign_cli_stderr("") is True
    assert module.is_benign_cli_stderr("CODESYS not running, attempting to start it") is True
    assert module.is_benign_cli_stderr("unexpected error") is False


def test_is_retryable_cli_project_create_error_matches_known_markers() -> None:
    module = load_probe_module()

    assert module.is_retryable_cli_project_create_error(
        1,
        {"success": False, "error": "Controls created on one thread cannot be parented to a control on a different thread."},
    )
    assert module.is_retryable_cli_project_create_error(
        1,
        {"success": False, "error": "A primary project is already open at C:\\demo\\foo.project"},
    )
    assert module.is_retryable_cli_project_create_error(0, {"success": False, "error": "Controls created on one thread"}) is False
    assert module.is_retryable_cli_project_create_error(1, {"success": False, "error": "No active project in session"}) is False


def test_create_project_with_retry_recovers_once_for_retryable_cli_error(monkeypatch: Any) -> None:
    module = load_probe_module()
    cli_calls: list[tuple[str, ...]] = []
    recover_calls: list[str] = []

    responses = [
        (1, {"success": False, "error": "Controls created on one thread cannot be parented to a control on a different thread."}, ""),
        (0, {"success": True, "project": {"path": r"C:\temp\demo.project"}}, ""),
    ]

    def fake_run_cli_json(env: dict[str, str], *args: str) -> tuple[int, dict[str, object], str]:
        cli_calls.append(args)
        return responses.pop(0)

    def fake_recover_after_project_create_failure(*, base_url: str, call_json: object, sleep_fn: object = None) -> None:
        recover_calls.append(base_url)

    monkeypatch.setattr(module, "run_cli_json", fake_run_cli_json)
    monkeypatch.setattr(module.syntax_probe, "recover_after_project_create_failure", fake_recover_after_project_create_failure)

    exit_code, payload, stderr, attempts = module.create_project_with_retry(
        env={"CODESYS_API_PIPE_NAME": "pipe"},
        base_url="http://127.0.0.1:1234",
        project_path=r"C:\temp\demo.project",
    )

    assert exit_code == 0
    assert payload == {"success": True, "project": {"path": r"C:\temp\demo.project"}}
    assert stderr == ""
    assert attempts == 2
    assert cli_calls == [
        ("project", "create", "--path", r"C:\temp\demo.project"),
        ("project", "create", "--path", r"C:\temp\demo.project"),
    ]
    assert recover_calls == ["http://127.0.0.1:1234"]
