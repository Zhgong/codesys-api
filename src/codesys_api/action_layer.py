from __future__ import annotations

import importlib
import json
import logging
import os
import socket
import sys
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from .engine_adapter import EngineAdapter
from .server_config import load_server_config
from .server_logic import (
    build_status_payload,
    normalize_project_create_params,
    validate_pou_code_params,
    validate_required_params,
)


NowFn = Callable[[], float]
TimestampFn = Callable[[], str]


class ProcessManagerLike(Protocol):
    def is_running(self) -> bool: ...

    def start(self) -> bool: ...

    def stop(self) -> bool: ...

    def get_status(self) -> dict[str, object]: ...

    def is_no_ui_mode(self) -> bool: ...

    def set_no_ui_mode(self, no_ui: bool) -> None: ...

    def reset_runtime_mode(self) -> None: ...


class ScriptExecutorLike(Protocol):
    def execute_script(self, script: str, timeout: int = 60) -> dict[str, object]: ...


class ActionType(str, Enum):
    SESSION_START = "session.start"
    SESSION_STOP = "session.stop"
    SESSION_RESTART = "session.restart"
    SESSION_STATUS = "session.status"
    SYSTEM_DOCTOR = "system.doctor"
    SCRIPT_EXECUTE = "script.execute"
    PROJECT_CREATE = "project.create"
    PROJECT_OPEN = "project.open"
    PROJECT_SAVE = "project.save"
    PROJECT_CLOSE = "project.close"
    PROJECT_LIST = "project.list"
    PROJECT_COMPILE = "project.compile"
    POU_CREATE = "pou.create"
    POU_CODE = "pou.code"
    POU_LIST = "pou.list"


@dataclass(frozen=True)
class ActionRequest:
    action: ActionType
    params: dict[str, object]
    timeout: int | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class ActionResult:
    body: dict[str, object]
    status_code: int = 200
    request_id: str | None = field(default=None, repr=False)


class ActionService:
    def __init__(
        self,
        *,
        process_manager: ProcessManagerLike,
        script_executor: ScriptExecutorLike,
        engine_adapter: EngineAdapter,
        logger: logging.Logger,
        now_fn: NowFn,
        script_dir: Path,
        timestamp_fn: TimestampFn = lambda: time.strftime("%Y%m%d_%H%M%S"),
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.process_manager = process_manager
        self.script_executor = script_executor
        self.engine_adapter = engine_adapter
        self.logger = logger
        self.now_fn = now_fn
        self.script_dir = script_dir
        self.timestamp_fn = timestamp_fn
        self.sleep_fn = sleep_fn

    def execute(self, request: ActionRequest) -> ActionResult:
        if request.action == ActionType.SESSION_START:
            return self._session_start(request)
        if request.action == ActionType.SESSION_STOP:
            return self._session_stop(request)
        if request.action == ActionType.SESSION_RESTART:
            return self._session_restart(request)
        if request.action == ActionType.SESSION_STATUS:
            return self._session_status(request)
        if request.action == ActionType.SYSTEM_DOCTOR:
            return self._system_doctor(request)
        if request.action == ActionType.SCRIPT_EXECUTE:
            return self._script_execute(request)
        if request.action == ActionType.PROJECT_CREATE:
            return self._project_create(request)
        if request.action == ActionType.PROJECT_OPEN:
            return self._project_open(request)
        if request.action == ActionType.PROJECT_SAVE:
            return self._project_save(request)
        if request.action == ActionType.PROJECT_CLOSE:
            return self._project_close(request)
        if request.action == ActionType.PROJECT_LIST:
            return self._project_list(request)
        if request.action == ActionType.PROJECT_COMPILE:
            return self._project_compile(request)
        if request.action == ActionType.POU_CREATE:
            return self._pou_create(request)
        if request.action == ActionType.POU_CODE:
            return self._pou_code(request)
        if request.action == ActionType.POU_LIST:
            return self._pou_list(request)

        return ActionResult(body={"success": False, "error": "Unsupported action"}, status_code=400)

    def _unsupported_action(self, action: ActionType, request_id: str | None) -> ActionResult:
        return ActionResult(
            body={
                "success": False,
                "error": f"Action not supported by engine: {action.value}",
                "engine": self.engine_adapter.engine_name,
            },
            status_code=501,
            request_id=request_id,
        )

    def _execute_engine_action(
        self,
        *,
        action: ActionType,
        params: dict[str, object],
        timeout_override: int | None,
    ) -> dict[str, object]:
        execution = self.engine_adapter.build_execution(action.value, params)
        raw_result = self.script_executor.execute_script(
            execution.script,
            timeout=timeout_override or execution.timeout,
        )
        return self.engine_adapter.normalize_result(action.value, raw_result)

    def _session_start(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().session_start:
            return self._unsupported_action(request.action, request.request_id)

        self.logger.info("Session start requested - checking CODESYS process")

        if not self.process_manager.is_running():
            self.logger.info("CODESYS process not running, attempting to start")
            if not self.process_manager.start():
                return ActionResult(
                    body={"success": False, "error": "Failed to start CODESYS process"},
                    status_code=500,
                    request_id=request.request_id,
                )

        result = self._execute_engine_action(
            action=request.action,
            params={},
            timeout_override=request.timeout,
        )
        return ActionResult(body=result, request_id=request.request_id)

    def _session_stop(self, request: ActionRequest) -> ActionResult:
        if not self.process_manager.stop():
            return ActionResult(
                body={"success": False, "error": "Failed to stop CODESYS session"},
                status_code=500,
                request_id=request.request_id,
            )

        self.process_manager.reset_runtime_mode()

        return ActionResult(
            body={"success": True, "message": "Session stopped"},
            request_id=request.request_id,
        )

    def _session_restart(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().session_start:
            return self._unsupported_action(request.action, request.request_id)

        if not self.process_manager.stop():
            return ActionResult(
                body={"success": False, "error": "Failed to stop CODESYS session"},
                status_code=500,
                request_id=request.request_id,
            )

        self.process_manager.reset_runtime_mode()
        self.sleep_fn(2.0)

        if not self.process_manager.start():
            return ActionResult(
                body={"success": False, "error": "Failed to restart CODESYS session"},
                status_code=500,
                request_id=request.request_id,
            )

        result = self._execute_engine_action(
            action=ActionType.SESSION_START,
            params={},
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _session_status(self, request: ActionRequest) -> ActionResult:
        process_running = self.process_manager.is_running()
        process_status = self.process_manager.get_status()

        if process_running:
            if not self.engine_adapter.capabilities().session_status:
                return self._unsupported_action(request.action, request.request_id)
            self.logger.info("Executing session status script in CODESYS")
            status_result = self._execute_engine_action(
                action=request.action,
                params={},
                timeout_override=request.timeout,
            )
        else:
            status_result = None

        status = build_status_payload(
            process_running=process_running,
            process_status=process_status,
            session_status_result=status_result,
            now=self.now_fn(),
        )
        return ActionResult(
            body={"success": True, "status": status},
            request_id=request.request_id,
        )

    def _doctor_check(
        self,
        *,
        name: str,
        status: str,
        detail: str,
        suggestion: str,
    ) -> dict[str, str]:
        return {
            "name": name,
            "status": status,
            "detail": detail,
            "suggestion": suggestion,
        }

    def _check_python_dependency(self, module_name: str, install_hint: str) -> dict[str, str]:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            return self._doctor_check(
                name="Python dependency: {0}".format(module_name),
                status="FAIL",
                detail="Cannot import '{0}': {1}".format(module_name, exc),
                suggestion=install_hint,
            )
        return self._doctor_check(
            name="Python dependency: {0}".format(module_name),
            status="PASS",
            detail="Module '{0}' is importable.".format(module_name),
            suggestion="No action required.",
        )

    def _check_os_windows(self) -> dict[str, str]:
        if sys.platform == "win32":
            return self._doctor_check(
                name="Operating system",
                status="PASS",
                detail="Detected Windows platform: {0}".format(sys.platform),
                suggestion="No action required.",
            )
        return self._doctor_check(
            name="Operating system",
            status="FAIL",
            detail="Unsupported platform detected: {0}".format(sys.platform),
            suggestion="Use a Windows operating system.",
        )

    def _resolve_codesys_path_from_env(self) -> tuple[str, str] | None:
        for key in ("CODESYS_API_CODESYS_PATH", "CODESYS_PATH"):
            raw_value = os.environ.get(key)
            if isinstance(raw_value, str):
                value = raw_value.strip()
                if value:
                    return key, value
        return None

    def _check_codesys_profile_env(self) -> dict[str, str]:
        profile_name = os.environ.get("CODESYS_API_CODESYS_PROFILE")
        if isinstance(profile_name, str) and profile_name.strip():
            return self._doctor_check(
                name="CODESYS profile environment",
                status="PASS",
                detail="Using CODESYS_API_CODESYS_PROFILE={0}".format(profile_name.strip()),
                suggestion="No action required.",
            )
        return self._doctor_check(
            name="CODESYS profile environment",
            status="FAIL",
            detail="CODESYS_API_CODESYS_PROFILE is not defined.",
            suggestion="Set CODESYS_API_CODESYS_PROFILE.",
        )

    def _check_config_file_validity(self) -> dict[str, str]:
        try:
            load_server_config(Path.cwd(), os.environ)
        except json.JSONDecodeError as exc:
            return self._doctor_check(
                name="Configuration validity",
                status="FAIL",
                detail="Configuration parse failure: {0}".format(exc),
                suggestion="Fix formatting errors in your .env or config file.",
            )
        except ValueError as exc:
            return self._doctor_check(
                name="Configuration validity",
                status="FAIL",
                detail="Invalid configuration value: {0}".format(exc),
                suggestion="Fix formatting errors in your .env or config file.",
            )
        return self._doctor_check(
            name="Configuration validity",
            status="PASS",
            detail="Server configuration loaded successfully.",
            suggestion="No action required.",
        )

    def _check_codesys_path_env(self) -> dict[str, str]:
        resolved = self._resolve_codesys_path_from_env()
        if resolved is None:
            return self._doctor_check(
                name="CODESYS path environment",
                status="FAIL",
                detail="Neither CODESYS_API_CODESYS_PATH nor CODESYS_PATH is defined.",
                suggestion="Set CODESYS_API_CODESYS_PATH to the full path of CODESYS.exe.",
            )
        key, value = resolved
        return self._doctor_check(
            name="CODESYS path environment",
            status="PASS",
            detail="Using {0}={1}".format(key, value),
            suggestion="No action required.",
        )

    def _check_codesys_binary(self) -> dict[str, str]:
        resolved = self._resolve_codesys_path_from_env()
        if resolved is None:
            return self._doctor_check(
                name="CODESYS binary",
                status="FAIL",
                detail="CODESYS path environment variable is not configured.",
                suggestion="Set CODESYS_API_CODESYS_PATH to CODESYS.exe before running doctor.",
            )

        _, value = resolved
        codesys_path = Path(value)
        if not codesys_path.exists():
            return self._doctor_check(
                name="CODESYS binary",
                status="FAIL",
                detail="Configured path does not exist: {0}".format(codesys_path),
                suggestion="Verify CODESYS installation path and update CODESYS_API_CODESYS_PATH.",
            )
        if not codesys_path.is_file():
            return self._doctor_check(
                name="CODESYS binary",
                status="FAIL",
                detail="Configured path is not a file: {0}".format(codesys_path),
                suggestion="Point CODESYS_API_CODESYS_PATH to the CODESYS.exe file.",
            )
        if not os.access(codesys_path, os.X_OK):
            return self._doctor_check(
                name="CODESYS binary",
                status="FAIL",
                detail="Current user lacks execute permission for: {0}".format(codesys_path),
                suggestion="Grant execution permissions to the current user for CODESYS.exe.",
            )
        if codesys_path.name.lower() != "codesys.exe":
            return self._doctor_check(
                name="CODESYS binary",
                status="WARN",
                detail="Configured file is not named CODESYS.exe: {0}".format(codesys_path.name),
                suggestion="Double-check the executable path if launch issues occur.",
            )

        return self._doctor_check(
            name="CODESYS binary",
            status="PASS",
            detail="Binary exists: {0}".format(codesys_path),
            suggestion="No action required.",
        )

    def _check_named_pipe_creation(self) -> dict[str, str]:
        pipe_name = r"\\.\pipe\codesys_api_doctor_test_{0}".format(uuid.uuid4().hex)
        handle: object | None = None
        try:
            import win32pipe  # type: ignore[import-not-found]
        except Exception as exc:
            return self._doctor_check(
                name="Named pipe creation",
                status="FAIL",
                detail="Cannot import win32pipe: {0}".format(exc),
                suggestion="Install dependency: pip install pywin32.",
            )

        try:
            handle = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                4096,
                4096,
                0,
                None,
            )
        except Exception as exc:
            return self._doctor_check(
                name="Named pipe creation",
                status="FAIL",
                detail="Failed to create named pipe '{0}': {1}".format(pipe_name, exc),
                suggestion="Check administrator privileges or Windows pipe permissions.",
            )
        finally:
            if handle is not None:
                close_method = getattr(handle, "Close", None)
                if callable(close_method):
                    close_method()
                else:
                    try:
                        import win32file  # type: ignore[import-not-found]

                        win32file.CloseHandle(handle)
                    except Exception:
                        pass

        return self._doctor_check(
            name="Named pipe creation",
            status="PASS",
            detail="Successfully created probe pipe: {0}".format(pipe_name),
            suggestion="No action required.",
        )

    def _doctor_port(self) -> tuple[int | None, str | None]:
        raw_value = os.environ.get("CODESYS_API_SERVER_PORT", "8080")
        try:
            return int(raw_value), None
        except ValueError:
            return None, raw_value

    def _check_port_availability(self) -> dict[str, str]:
        port, raw_port = self._doctor_port()
        if port is None:
            return self._doctor_check(
                name="HTTP port availability",
                status="FAIL",
                detail="Invalid CODESYS_API_SERVER_PORT value: {0}".format(raw_port),
                suggestion="Set CODESYS_API_SERVER_PORT to a valid integer port.",
            )

        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            test_socket.bind(("127.0.0.1", port))
        except Exception as exc:
            return self._doctor_check(
                name="HTTP port availability",
                status="FAIL",
                detail="Port {0} is unavailable: {1}".format(port, exc),
                suggestion="Kill the process using port {0} or change the API port configuration.".format(
                    port
                ),
            )
        finally:
            try:
                test_socket.close()
            except OSError:
                self.logger.warning("Failed to close doctor port probe socket")

        return self._doctor_check(
            name="HTTP port availability",
            status="PASS",
            detail="Port {0} is available.".format(port),
            suggestion="No action required.",
        )

    def _check_server_connectivity(self) -> dict[str, str]:
        port, _ = self._doctor_port()
        if port is None:
            port = 8080
        probe_url = "http://127.0.0.1:{0}/api/v1/system/info".format(port)
        try:
            with urllib.request.urlopen(probe_url, timeout=1.0) as response:
                status_code = getattr(response, "status", 200)
                if isinstance(status_code, int) and status_code >= 400:
                    return self._doctor_check(
                        name="Server connectivity",
                        status="WARN",
                        detail="Server probe returned HTTP {0} at {1}".format(status_code, probe_url),
                        suggestion=(
                            "Server is not running. Start codesys-tools-server if REST API access is needed."
                        ),
                    )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return self._doctor_check(
                name="Server connectivity",
                status="WARN",
                detail="Server probe failed at {0}: {1}".format(probe_url, exc),
                suggestion="Server is not running. Start codesys-tools-server if REST API access is needed.",
            )
        except Exception as exc:
            return self._doctor_check(
                name="Server connectivity",
                status="WARN",
                detail="Unexpected connectivity probe failure at {0}: {1}".format(probe_url, exc),
                suggestion="Server is not running. Start codesys-tools-server if REST API access is needed.",
            )

        return self._doctor_check(
            name="Server connectivity",
            status="PASS",
            detail="Server probe succeeded: {0}".format(probe_url),
            suggestion="No action required.",
        )

    def _system_doctor(self, request: ActionRequest) -> ActionResult:
        checks: list[dict[str, str]] = []
        check_functions: list[Callable[[], dict[str, str]]] = [
            self._check_os_windows,
            lambda: self._check_python_dependency("win32api", "Install dependency: pip install pywin32"),
            lambda: self._check_python_dependency("requests", "Install dependency: pip install requests"),
            self._check_codesys_path_env,
            self._check_codesys_profile_env,
            self._check_config_file_validity,
            self._check_codesys_binary,
            self._check_named_pipe_creation,
            self._check_port_availability,
            self._check_server_connectivity,
        ]

        for check_fn in check_functions:
            try:
                checks.append(check_fn())
            except Exception as exc:
                self.logger.exception("System doctor check crashed")
                checks.append(
                    self._doctor_check(
                        name="Doctor internal check failure",
                        status="FAIL",
                        detail="Unexpected check crash: {0}".format(exc),
                        suggestion="Inspect logs and rerun doctor.",
                    )
                )

        fail_count = sum(1 for item in checks if item["status"] == "FAIL")
        warn_count = sum(1 for item in checks if item["status"] == "WARN")

        return ActionResult(
            body={
                "success": True,
                "checks": checks,
                "summary": {
                    "total": len(checks),
                    "failures": fail_count,
                    "warnings": warn_count,
                },
            },
            request_id=request.request_id,
        )

    def _script_execute(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().script_execute:
            return self._unsupported_action(request.action, request.request_id)

        script = request.params.get("script")
        if not isinstance(script, str) or not script:
            return ActionResult(
                body={"success": False, "error": "Missing required parameter: script"},
                status_code=400,
                request_id=request.request_id,
            )

        first_line = script.split("\n")[0]
        self.logger.info(
            "Script execute request: %s",
            first_line[:50] + "..." if len(first_line) > 50 else first_line,
        )
        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        return ActionResult(body=result, request_id=request.request_id)

    def _project_create(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().project_create:
            return self._unsupported_action(request.action, request.request_id)

        params = normalize_project_create_params(request.params, str(self.script_dir), self.timestamp_fn())

        if not self.process_manager.is_running():
            self.logger.warning("CODESYS not running, attempting to start it")
            if not self.process_manager.start():
                return ActionResult(
                    body={"success": False, "error": "Failed to start CODESYS process"},
                    status_code=500,
                    request_id=request.request_id,
                )

        result = self._execute_engine_action(
            action=request.action,
            params=params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _project_open(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().project_open:
            return self._unsupported_action(request.action, request.request_id)

        error = validate_required_params(request.params, ["path"])
        if error is not None:
            return ActionResult(
                body={"success": False, "error": error},
                status_code=400,
                request_id=request.request_id,
            )

        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _project_save(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().project_save:
            return self._unsupported_action(request.action, request.request_id)

        result = self._execute_engine_action(
            action=request.action,
            params={},
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _project_close(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().project_close:
            return self._unsupported_action(request.action, request.request_id)

        result = self._execute_engine_action(
            action=request.action,
            params={},
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _project_list(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().project_list:
            return self._unsupported_action(request.action, request.request_id)

        result = self._execute_engine_action(
            action=request.action,
            params={},
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _project_compile(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().project_compile:
            return self._unsupported_action(request.action, request.request_id)

        self.logger.info("Executing compile with full CODESYS message harvest")
        result = self._execute_engine_action(
            action=request.action,
            params=self._build_compile_params(request.params, safe_message_harvest=False),
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _build_compile_params(
        self,
        params: dict[str, object],
        *,
        safe_message_harvest: bool,
    ) -> dict[str, object]:
        compile_params = dict(params)
        compile_params["_safe_message_harvest"] = safe_message_harvest
        return compile_params

    def _pou_create(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().pou_create:
            return self._unsupported_action(request.action, request.request_id)

        error = validate_required_params(request.params, ["name", "type", "language"])
        if error is not None:
            return ActionResult(
                body={"success": False, "error": error},
                status_code=400,
                request_id=request.request_id,
            )

        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _pou_code(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().pou_code:
            return self._unsupported_action(request.action, request.request_id)

        error = validate_pou_code_params(request.params)
        if error is not None:
            return ActionResult(
                body={"success": False, "error": error},
                status_code=400,
                request_id=request.request_id,
            )

        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _pou_list(self, request: ActionRequest) -> ActionResult:
        if not self.engine_adapter.capabilities().pou_list:
            return self._unsupported_action(request.action, request.request_id)

        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)
