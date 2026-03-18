from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from engine_adapter import EngineAdapter
from server_logic import (
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

        if self.process_manager.is_running() and self.process_manager.is_no_ui_mode():
            return self._project_compile_with_ui_fallback(request)

        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

    def _project_compile_with_ui_fallback(self, request: ActionRequest) -> ActionResult:
        session_status = self._execute_engine_action(
            action=ActionType.SESSION_STATUS,
            params={},
            timeout_override=request.timeout,
        )
        status_payload = session_status.get("status")
        project_path = None
        if isinstance(status_payload, dict):
            project = status_payload.get("project")
            if isinstance(project, dict):
                raw_path = project.get("path")
                if isinstance(raw_path, str) and raw_path:
                    project_path = raw_path

        if not project_path:
            return ActionResult(
                body={"success": False, "error": "Cannot recover active project path for noUI compile fallback"},
                status_code=500,
                request_id=request.request_id,
            )

        save_result = self._execute_engine_action(
            action=ActionType.PROJECT_SAVE,
            params={},
            timeout_override=request.timeout,
        )
        if not save_result.get("success", False):
            return ActionResult(body=save_result, status_code=500, request_id=request.request_id)

        close_result = self._execute_engine_action(
            action=ActionType.PROJECT_CLOSE,
            params={},
            timeout_override=request.timeout,
        )
        if not close_result.get("success", False):
            return ActionResult(body=close_result, status_code=500, request_id=request.request_id)

        if not self.process_manager.stop():
            return ActionResult(
                body={"success": False, "error": "Failed to stop CODESYS session for noUI compile fallback"},
                status_code=500,
                request_id=request.request_id,
            )

        self.process_manager.set_no_ui_mode(False)

        if not self.process_manager.start():
            return ActionResult(
                body={"success": False, "error": "Failed to restart CODESYS in UI mode for compile"},
                status_code=500,
                request_id=request.request_id,
            )

        start_result = self._execute_engine_action(
            action=ActionType.SESSION_START,
            params={},
            timeout_override=request.timeout,
        )
        if not start_result.get("success", False):
            return ActionResult(body=start_result, status_code=500, request_id=request.request_id)

        open_result = self._execute_engine_action(
            action=ActionType.PROJECT_OPEN,
            params={"path": project_path},
            timeout_override=request.timeout,
        )
        if not open_result.get("success", False):
            return ActionResult(body=open_result, status_code=500, request_id=request.request_id)

        result = self._execute_engine_action(
            action=request.action,
            params=request.params,
            timeout_override=request.timeout,
        )
        status_code = 200 if result.get("success", False) else 500
        return ActionResult(body=result, status_code=status_code, request_id=request.request_id)

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
