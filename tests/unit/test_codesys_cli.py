from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any, cast

from codesys_api.action_layer import ActionRequest, ActionResult
import codesys_api.cli_entry as codesys_cli
from codesys_api.cli_entry import run_cli
import pytest


class FakeActionService:
    def __init__(self, result: ActionResult) -> None:
        self.result = result
        self.requests: list[ActionRequest] = []

    def execute(self, request: ActionRequest) -> ActionResult:
        self.requests.append(request)
        return self.result


@pytest.fixture
def repo_root_path() -> Path:
    return Path(__file__).resolve().parents[2]


def _reset_cli_logger_state() -> None:
    handler = codesys_cli._CLI_LOGGING_HANDLER
    if handler is not None:
        codesys_cli.logger.removeHandler(handler)
        handler.close()
    codesys_cli._CLI_LOGGING_HANDLER = None
    codesys_cli._CLI_LOGGING_CONFIGURED = False


def test_cli_session_start_uses_action_layer_and_prints_human_message() -> None:
    service = FakeActionService(ActionResult(body={"success": True, "message": "Session started"}))
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["session", "start"], action_service=cast(Any, service), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Session started"
    assert stderr.getvalue() == ""
    assert service.requests[0].action.value == "session.start"


def test_cli_root_help_includes_examples_and_returns_success() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(["--help"], stdout=stdout)

    assert exit_code == 0
    help_text = stdout.getvalue()
    assert "Examples:" in help_text
    assert "project create --path" in help_text
    assert "session start" in help_text
    assert "named_pipe only" in help_text
    assert "Exit codes: 0=success, 1=business/runtime failure, 2=setup/input error" in help_text
    assert "Each CLI invocation executes one action." in help_text
    assert "CODESYS_API_PIPE_NAME" in help_text
    assert "codesys-tools-server" in help_text


def test_cli_project_help_returns_success() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(["project", "--help"], stdout=stdout)

    assert exit_code == 0
    help_text = stdout.getvalue()
    assert "create" in help_text
    assert "compile" in help_text
    assert "list" in help_text
    assert "project save" in help_text
    assert "project close" in help_text


def test_cli_session_help_returns_success() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(["session", "--help"], stdout=stdout)

    assert exit_code == 0
    help_text = stdout.getvalue()
    assert "session start" in help_text
    assert "session restart" in help_text
    assert "session stop" in help_text


def test_cli_pou_help_returns_success() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(["pou", "--help"], stdout=stdout)

    assert exit_code == 0
    help_text = stdout.getvalue()
    assert "pou create" in help_text
    assert "pou list --parent-path Application" in help_text
    assert "pou code --path Application\\PLC_PRG" in help_text


def test_cli_pou_code_help_includes_supported_path_formats() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(["pou", "code", "--help"], stdout=stdout)

    assert exit_code == 0
    help_text = stdout.getvalue()
    assert "CounterFB" in help_text
    assert "Application/CounterFB" in help_text
    assert "Application\\CounterFB" in help_text


def test_cli_project_compile_help_includes_no_ui_and_header_warning() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(["project", "compile", "--help"], stdout=stdout)

    assert exit_code == 0
    help_text = stdout.getvalue()
    assert "CODESYS_API_CODESYS_NO_UI=1" in help_text
    assert "FUNCTION_BLOCK/PROGRAM header line" in help_text


def test_cli_session_restart_maps_action_and_prints_message() -> None:
    service = FakeActionService(ActionResult(body={"success": True, "message": "Session restarted"}))
    stdout = io.StringIO()

    exit_code = run_cli(["session", "restart"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Session restarted"
    assert service.requests[0].action.value == "session.restart"


def test_cli_project_compile_prints_message_counts() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "message": "Project compiled successfully",
                "message_counts": {"errors": 0, "warnings": 1, "infos": 2},
            }
        )
    )
    stdout = io.StringIO()

    exit_code = run_cli(["project", "compile"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Compile succeeded (errors=0, warnings=1, infos=2)"
    assert service.requests[0].action.value == "project.compile"
    assert service.requests[0].params == {"clean_build": False}


def test_cli_project_create_maps_path_and_prints_project_summary() -> None:
    service = FakeActionService(
        ActionResult(body={"success": True, "project": {"path": "C:/demo.project"}})
    )
    stdout = io.StringIO()

    exit_code = run_cli(
        ["project", "create", "--path", "C:/demo.project"],
        action_service=cast(Any, service),
        stdout=stdout,
    )

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Project ready: C:/demo.project"
    assert service.requests[0].action.value == "project.create"
    assert service.requests[0].params == {"path": "C:/demo.project"}


def test_cli_project_save_maps_action_and_prints_message() -> None:
    service = FakeActionService(ActionResult(body={"success": True, "message": "Project saved"}))
    stdout = io.StringIO()

    exit_code = run_cli(["project", "save"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Project saved"
    assert service.requests[0].action.value == "project.save"
    assert service.requests[0].params == {}


def test_cli_project_close_maps_action_and_prints_message() -> None:
    service = FakeActionService(ActionResult(body={"success": True, "message": "Project closed"}))
    stdout = io.StringIO()

    exit_code = run_cli(["project", "close"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Project closed"
    assert service.requests[0].action.value == "project.close"
    assert service.requests[0].params == {}


def test_cli_project_list_prints_paths_one_per_line() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "projects": [
                    {"path": "C:/alpha.project"},
                    {"name": "beta.project"},
                ],
            }
        )
    )
    stdout = io.StringIO()

    exit_code = run_cli(["project", "list"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "C:/alpha.project\nbeta.project"
    assert service.requests[0].action.value == "project.list"
    assert service.requests[0].params == {}


def test_cli_project_list_prints_empty_state() -> None:
    service = FakeActionService(ActionResult(body={"success": True, "projects": []}))
    stdout = io.StringIO()

    exit_code = run_cli(["project", "list"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "No recent projects"


def test_cli_session_status_prints_human_readable_summary() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "status": {
                    "process": {"state": "running"},
                    "session": {"session_active": True, "project_open": True},
                },
            }
        )
    )
    stdout = io.StringIO()

    exit_code = run_cli(["session", "status"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "Process: running | Session active: True | Project open: True"
    assert service.requests[0].action.value == "session.status"


def test_cli_json_mode_prints_raw_result() -> None:
    service = FakeActionService(ActionResult(body={"success": False, "error": "boom"}, status_code=500))
    stdout = io.StringIO()

    exit_code = run_cli(["--json", "session", "stop"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {"success": False, "error": "boom"}


def test_cli_failure_prints_error_to_stderr() -> None:
    service = FakeActionService(ActionResult(body={"success": False, "error": "compile failed"}, status_code=500))
    stderr = io.StringIO()

    exit_code = run_cli(["project", "compile"], action_service=cast(Any, service), stderr=stderr)

    assert exit_code == 1
    assert stderr.getvalue().strip() == "Compile failed: compile failed (message counts unavailable)"


def test_cli_failure_without_error_uses_message_text() -> None:
    service = FakeActionService(ActionResult(body={"success": False, "message": "Project is not open"}, status_code=400))
    stderr = io.StringIO()

    exit_code = run_cli(["project", "save"], action_service=cast(Any, service), stderr=stderr)

    assert exit_code == 1
    assert stderr.getvalue().strip() == "Project is not open"


def test_cli_pou_list_prints_name_type_and_language() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "container": "Application",
                "pous": [
                    {"name": "PLC_PRG", "type": "Program", "language": "ST"},
                    {"name": "MotorController", "type": "FunctionBlock", "language": "Unknown"},
                ],
            }
        )
    )
    stdout = io.StringIO()

    exit_code = run_cli(["pou", "list"], action_service=cast(Any, service), stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue().strip() == "PLC_PRG [Program] <ST>\nMotorController [FunctionBlock]"
    assert service.requests[0].action.value == "pou.list"
    assert service.requests[0].params == {"parentPath": "Application"}


def test_cli_pou_list_respects_parent_path_and_empty_state() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "container": "Application/SubFolder",
                "pous": [],
            }
        )
    )
    stdout = io.StringIO()

    exit_code = run_cli(
        ["pou", "list", "--parent-path", "Application/SubFolder"],
        action_service=cast(Any, service),
        stdout=stdout,
    )

    assert exit_code == 0
    assert stdout.getvalue().strip() == "No POUs found under Application/SubFolder"
    assert service.requests[0].params == {"parentPath": "Application/SubFolder"}


def test_cli_pou_code_requires_at_least_one_input_file() -> None:
    service = FakeActionService(ActionResult(body={"success": True}))
    stderr = io.StringIO()

    exit_code = run_cli(
        ["pou", "code", "--path", "Application/PLC_PRG"],
        action_service=cast(Any, service),
        stderr=stderr,
    )

    assert exit_code == 2
    assert "At least one of --declaration-file or --implementation-file is required" in stderr.getvalue()
    assert service.requests == []


def test_cli_pou_code_missing_input_file_returns_usage_error() -> None:
    service = FakeActionService(ActionResult(body={"success": True}))
    stderr = io.StringIO()

    exit_code = run_cli(
        [
            "pou",
            "code",
            "--path",
            "Application/PLC_PRG",
            "--implementation-file",
            "missing.txt",
        ],
        action_service=cast(Any, service),
        stderr=stderr,
    )

    assert exit_code == 2
    assert "missing.txt" in stderr.getvalue()
    assert service.requests == []


def test_cli_reports_missing_profile_before_runtime_build(monkeypatch: Any, repo_root_path: Path) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_is_supported = True
        codesys_path = repo_root_path / "README.md"
        codesys_profile_name = None
        codesys_profile_path = None

    stderr = io.StringIO()
    monkeypatch.setattr(codesys_cli, "load_server_config", lambda base_dir, env: FakeConfig())

    exit_code = run_cli(["session", "start"], stderr=stderr, base_dir=repo_root_path, env={})

    assert exit_code == 2
    assert "CODESYS profile is not configured" in stderr.getvalue()


def test_cli_reports_missing_codesys_executable_before_runtime_build(monkeypatch: Any, repo_root_path: Path) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_is_supported = True
        codesys_path = repo_root_path / "missing.exe"
        codesys_profile_name = "Demo"
        codesys_profile_path = None

    stderr = io.StringIO()
    monkeypatch.setattr(codesys_cli, "load_server_config", lambda base_dir, env: FakeConfig())

    exit_code = run_cli(["session", "start"], stderr=stderr, base_dir=repo_root_path, env={})

    assert exit_code == 2
    assert "CODESYS executable not found" in stderr.getvalue()


def test_cli_reports_unsupported_transport_before_runtime_build(monkeypatch: Any, repo_root_path: Path) -> None:
    class FakeConfig:
        transport_name = "file"
        transport_is_supported = False
        codesys_path = repo_root_path / "README.md"
        codesys_profile_name = "Demo"
        codesys_profile_path = None

    stderr = io.StringIO()
    monkeypatch.setattr(codesys_cli, "load_server_config", lambda base_dir, env: FakeConfig())

    exit_code = run_cli(["session", "start"], stderr=stderr, base_dir=repo_root_path, env={})

    assert exit_code == 2
    assert "supports named_pipe only" in stderr.getvalue()


def test_cli_reports_missing_profile_path_before_runtime_build(monkeypatch: Any, repo_root_path: Path) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_is_supported = True
        codesys_path = repo_root_path / "README.md"
        codesys_profile_name = "Demo"
        codesys_profile_path = repo_root_path / "missing.profile.xml"

    stderr = io.StringIO()
    monkeypatch.setattr(codesys_cli, "load_server_config", lambda base_dir, env: FakeConfig())

    exit_code = run_cli(["session", "start"], stderr=stderr, base_dir=repo_root_path, env={})

    assert exit_code == 2
    assert "CODESYS profile file not found" in stderr.getvalue()


def test_cli_reports_runtime_builder_value_error(monkeypatch: Any, repo_root_path: Path) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_is_supported = True
        codesys_path = repo_root_path / "README.md"
        codesys_profile_name = "Demo"
        codesys_profile_path = None

    stderr = io.StringIO()
    monkeypatch.setattr(codesys_cli, "load_server_config", lambda base_dir, env: FakeConfig())
    monkeypatch.setattr(codesys_cli, "build_app_runtime", lambda config, logger: (_ for _ in ()).throw(ValueError("boom")))

    exit_code = run_cli(["session", "start"], stderr=stderr, base_dir=repo_root_path, env={})

    assert exit_code == 2
    assert stderr.getvalue().strip() == "boom"


def test_cli_configures_file_logger_and_disables_propagation(tmp_path: Path) -> None:
    _reset_cli_logger_state()
    appdata = tmp_path / "Roaming"
    appdata.mkdir(parents=True, exist_ok=True)

    try:
        codesys_cli._configure_cli_logging({"APPDATA": str(appdata)})
        codesys_cli.logger.warning("cli-warning-for-file")
        if codesys_cli._CLI_LOGGING_HANDLER is not None:
            codesys_cli._CLI_LOGGING_HANDLER.flush()

        assert codesys_cli.logger.propagate is False
        assert isinstance(codesys_cli._CLI_LOGGING_HANDLER, logging.FileHandler)
        log_file = appdata / "codesys-api" / "logs" / "codesys_api_cli.log"
        assert log_file.exists()
        assert "cli-warning-for-file" in log_file.read_text(encoding="utf-8")
    finally:
        _reset_cli_logger_state()


def test_cli_logging_fallback_uses_null_handler_without_stderr_leak(monkeypatch: Any, capsys: Any) -> None:
    _reset_cli_logger_state()
    monkeypatch.setattr(
        codesys_cli,
        "default_runtime_log_dir",
        lambda env: (_ for _ in ()).throw(OSError("permission denied")),
    )

    try:
        codesys_cli._configure_cli_logging({"APPDATA": r"C:\does-not-matter"})
        codesys_cli.logger.warning("cli-warning-with-null-handler")
        captured = capsys.readouterr()

        assert isinstance(codesys_cli._CLI_LOGGING_HANDLER, logging.NullHandler)
        assert captured.err == ""
    finally:
        _reset_cli_logger_state()


def test_cli_pou_code_reads_file_inputs(repo_root_path: Path) -> None:
    declaration = repo_root_path / "docs" / "BASELINE.md"
    implementation = repo_root_path / "README.md"
    service = FakeActionService(ActionResult(body={"success": True, "message": "POU code updated successfully"}))

    exit_code = run_cli(
        [
            "pou",
            "code",
            "--path",
            "Application/Demo",
            "--declaration-file",
            str(declaration),
            "--implementation-file",
            str(implementation),
        ],
        action_service=cast(Any, service),
        stdout=io.StringIO(),
    )

    assert exit_code == 0
    assert service.requests[0].params == {
        "path": "Application/Demo",
        "declaration": declaration.read_text(encoding="utf-8"),
        "implementation": implementation.read_text(encoding="utf-8"),
    }
