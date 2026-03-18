from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from action_layer import ActionRequest, ActionService, ActionType
from engine_adapter import EngineCapabilities, ExecutionSpec


class FakeProcessManager:
    def __init__(
        self,
        *,
        running: bool,
        start_result: bool = True,
        stop_result: bool = True,
    ) -> None:
        self.running = running
        self.start_result = start_result
        self.stop_result = stop_result
        self.start_calls = 0
        self.stop_calls = 0
        self.no_ui_mode = False
        self.reset_runtime_mode_calls = 0

    def is_running(self) -> bool:
        return self.running

    def start(self) -> bool:
        self.start_calls += 1
        if self.start_result:
            self.running = True
        return self.start_result

    def stop(self) -> bool:
        self.stop_calls += 1
        if self.stop_result:
            self.running = False
        return self.stop_result

    def get_status(self) -> dict[str, object]:
        return {"state": "running", "timestamp": 123.0}

    def is_no_ui_mode(self) -> bool:
        return self.no_ui_mode

    def set_no_ui_mode(self, no_ui: bool) -> None:
        self.no_ui_mode = no_ui

    def reset_runtime_mode(self) -> None:
        self.reset_runtime_mode_calls += 1
        self.no_ui_mode = False


class FakeScriptExecutor:
    def __init__(self, result: dict[str, object] | None = None, results: list[dict[str, object]] | None = None) -> None:
        self.result = result or {"success": True}
        self.results = list(results or [])
        self.calls: list[tuple[str, int]] = []

    def execute_script(self, script: str, timeout: int = 60) -> dict[str, object]:
        self.calls.append((script, timeout))
        if self.results:
            return self.results.pop(0)
        return self.result


class FakeEngineAdapter:
    engine_name = "fake-engine"

    def __init__(self, capabilities: EngineCapabilities | None = None) -> None:
        self._capabilities = capabilities or EngineCapabilities(
            session_start=True,
            session_status=True,
            script_execute=True,
            project_create=True,
            project_open=True,
            project_save=True,
            project_close=True,
            project_list=True,
            project_compile=True,
            pou_create=True,
            pou_code=True,
            pou_list=True,
        )

    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    def build_execution(self, action: str, params: dict[str, object]) -> ExecutionSpec:
        script_map = {
            "session.start": "start-script",
            "session.status": "status-script",
            "project.save": "project-save",
            "project.close": "project-close",
            "project.list": "project-list",
        }
        if action in script_map:
            return ExecutionSpec(script=script_map[action], timeout=30)
        if action == "script.execute":
            return ExecutionSpec(script=str(params["script"]), timeout=60)
        if action == "project.create":
            return ExecutionSpec(script=f"project-create:{params['path']}", timeout=30)
        if action == "project.open":
            return ExecutionSpec(script=f"project-open:{params['path']}", timeout=30)
        if action == "project.compile":
            return ExecutionSpec(script=f"project-compile:{params.get('clean_build', False)}", timeout=120)
        if action == "pou.create":
            return ExecutionSpec(script=f"pou-create:{params['name']}", timeout=30)
        if action == "pou.code":
            return ExecutionSpec(script=f"pou-code:{params['path']}", timeout=30)
        if action == "pou.list":
            return ExecutionSpec(script=f"pou-list:{params.get('parentPath', '')}", timeout=30)
        raise ValueError(f"Unsupported action: {action}")

    def normalize_result(self, action: str, raw_result: dict[str, object]) -> dict[str, object]:
        result = dict(raw_result)
        result.setdefault("normalized_by", action)
        return result


def make_service(
    *,
    running: bool,
    start_result: bool = True,
    stop_result: bool = True,
    capabilities: EngineCapabilities | None = None,
    script_result: dict[str, object],
) -> ActionService:
    executor = FakeScriptExecutor(script_result)
    return ActionService(
        process_manager=FakeProcessManager(
            running=running,
            start_result=start_result,
            stop_result=stop_result,
        ),
        script_executor=executor,
        engine_adapter=FakeEngineAdapter(capabilities),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )


def test_session_start_starts_process_and_returns_script_result() -> None:
    service = make_service(
        running=False,
        script_result={"success": True, "message": "started"},
    )

    result = service.execute(ActionRequest(action=ActionType.SESSION_START, params={}))

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "message": "started",
        "normalized_by": "session.start",
    }


def test_session_start_returns_error_when_process_cannot_start() -> None:
    service = make_service(
        running=False,
        start_result=False,
        script_result={"success": True, "message": "unused"},
    )

    result = service.execute(ActionRequest(action=ActionType.SESSION_START, params={}))

    assert result.status_code == 500
    assert result.body == {"success": False, "error": "Failed to start CODESYS process"}


def test_session_status_builds_response_payload() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "status": {"active": True, "project_open": False}},
    )

    result = service.execute(ActionRequest(action=ActionType.SESSION_STATUS, params={}))
    status = cast(dict[str, Any], result.body["status"])
    process = cast(dict[str, Any], status["process"])
    session = cast(dict[str, Any], status["session"])

    assert result.status_code == 200
    assert result.body["success"] is True
    assert process["state"] == "running"
    assert session["active"] is True


def test_session_stop_returns_success_message() -> None:
    process_manager = FakeProcessManager(running=True)
    process_manager.no_ui_mode = True
    service = ActionService(
        process_manager=process_manager,
        script_executor=FakeScriptExecutor({"success": True}),
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(ActionRequest(action=ActionType.SESSION_STOP, params={}))

    assert result.status_code == 200
    assert result.body == {"success": True, "message": "Session stopped"}
    assert process_manager.no_ui_mode is False
    assert process_manager.reset_runtime_mode_calls == 1


def test_session_restart_reinitializes_session() -> None:
    process_manager = FakeProcessManager(running=True)
    process_manager.no_ui_mode = True
    service = ActionService(
        process_manager=process_manager,
        script_executor=FakeScriptExecutor({"success": True, "message": "restarted"}),
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(ActionRequest(action=ActionType.SESSION_RESTART, params={}))

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "message": "restarted",
        "normalized_by": "session.start",
    }
    assert process_manager.no_ui_mode is False
    assert process_manager.reset_runtime_mode_calls == 1


def test_session_restart_returns_error_when_stop_fails() -> None:
    service = make_service(
        running=True,
        stop_result=False,
        script_result={"success": True, "message": "unused"},
    )

    result = service.execute(ActionRequest(action=ActionType.SESSION_RESTART, params={}))

    assert result.status_code == 500
    assert result.body == {"success": False, "error": "Failed to stop CODESYS session"}


def test_script_execute_requires_script_parameter() -> None:
    service = make_service(
        running=True,
        script_result={"success": True},
    )

    result = service.execute(ActionRequest(action=ActionType.SCRIPT_EXECUTE, params={}))

    assert result.status_code == 400
    assert result.body == {"success": False, "error": "Missing required parameter: script"}


def test_script_execute_runs_supplied_script() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "result": {"value": 1}},
    )

    result = service.execute(
        ActionRequest(action=ActionType.SCRIPT_EXECUTE, params={"script": "print('hi')"})
    )

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "result": {"value": 1},
        "normalized_by": "script.execute",
    }


def test_project_create_adds_default_path_and_starts_process_when_needed() -> None:
    service = make_service(
        running=False,
        script_result={"success": True, "project": {"path": r"C:\repo\CODESYS_Project_20260318_120000.project"}},
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_CREATE, params={}, request_id="req-1")
    )

    assert result.status_code == 200
    assert result.body["success"] is True


def test_project_open_requires_path() -> None:
    service = make_service(
        running=True,
        script_result={"success": True},
    )

    result = service.execute(ActionRequest(action=ActionType.PROJECT_OPEN, params={}))

    assert result.status_code == 400
    assert result.body == {"success": False, "error": "Missing required parameter: path"}


def test_project_compile_uses_longer_timeout() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "message": "compiled"},
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": True})
    )

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "message": "compiled",
        "normalized_by": "project.compile",
    }


def test_project_compile_returns_unsupported_when_engine_lacks_capability() -> None:
    service = make_service(
        running=True,
        capabilities=EngineCapabilities(
            session_start=True,
            session_status=True,
            script_execute=True,
            project_create=True,
            project_open=True,
            project_save=True,
            project_close=True,
            project_list=True,
            project_compile=False,
            pou_create=True,
            pou_code=True,
            pou_list=True,
        ),
        script_result={"success": True, "message": "unused"},
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": True})
    )

    assert result.status_code == 501
    assert result.body == {
        "success": False,
        "error": "Action not supported by engine: project.compile",
        "engine": "fake-engine",
    }


def test_project_compile_restarts_in_ui_mode_when_no_ui_is_active() -> None:
    process_manager = FakeProcessManager(running=True)
    process_manager.no_ui_mode = True
    script_executor = FakeScriptExecutor(
        results=[
            {"success": True, "status": {"project": {"path": r"C:\repo\Demo.project"}}},
            {"success": True, "message": "saved"},
            {"success": True, "message": "closed"},
            {"success": True, "message": "session started"},
            {"success": True, "project": {"path": r"C:\repo\Demo.project"}},
            {"success": True, "message": "compiled"},
        ]
    )
    service = ActionService(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": False})
    )

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "message": "compiled",
        "normalized_by": "project.compile",
    }
    assert process_manager.no_ui_mode is False
    assert process_manager.stop_calls == 1
    assert process_manager.start_calls == 1
    assert [call[0] for call in script_executor.calls] == [
        "status-script",
        "project-save",
        "project-close",
        "start-script",
        r"project-open:C:\repo\Demo.project",
        "project-compile:False",
    ]


def test_project_compile_fallback_fails_when_project_path_cannot_be_recovered() -> None:
    process_manager = FakeProcessManager(running=True)
    process_manager.no_ui_mode = True
    service = ActionService(
        process_manager=process_manager,
        script_executor=FakeScriptExecutor(results=[{"success": True, "status": {}}]),
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": False})
    )

    assert result.status_code == 500
    assert result.body == {
        "success": False,
        "error": "Cannot recover active project path for noUI compile fallback",
    }


def test_project_compile_fallback_returns_error_when_stop_fails() -> None:
    process_manager = FakeProcessManager(running=True, stop_result=False)
    process_manager.no_ui_mode = True
    script_executor = FakeScriptExecutor(
        results=[
            {"success": True, "status": {"project": {"path": r"C:\repo\Demo.project"}}},
            {"success": True, "message": "saved"},
            {"success": True, "message": "closed"},
        ]
    )
    service = ActionService(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": False})
    )

    assert result.status_code == 500
    assert result.body == {
        "success": False,
        "error": "Failed to stop CODESYS session for noUI compile fallback",
    }


def test_project_compile_fallback_returns_error_when_restart_fails() -> None:
    process_manager = FakeProcessManager(running=True, start_result=False)
    process_manager.no_ui_mode = True
    script_executor = FakeScriptExecutor(
        results=[
            {"success": True, "status": {"project": {"path": r"C:\repo\Demo.project"}}},
            {"success": True, "message": "saved"},
            {"success": True, "message": "closed"},
        ]
    )
    service = ActionService(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": False})
    )

    assert result.status_code == 500
    assert result.body == {
        "success": False,
        "error": "Failed to restart CODESYS in UI mode for compile",
    }


def test_project_compile_fallback_returns_engine_error_when_reopen_fails() -> None:
    process_manager = FakeProcessManager(running=True)
    process_manager.no_ui_mode = True
    script_executor = FakeScriptExecutor(
        results=[
            {"success": True, "status": {"project": {"path": r"C:\repo\Demo.project"}}},
            {"success": True, "message": "saved"},
            {"success": True, "message": "closed"},
            {"success": True, "message": "session started"},
            {"success": False, "error": "open failed"},
        ]
    )
    service = ActionService(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": False})
    )

    assert result.status_code == 500
    assert result.body == {
        "success": False,
        "error": "open failed",
        "normalized_by": "project.open",
    }


def test_project_compile_fallback_returns_engine_error_when_close_fails() -> None:
    process_manager = FakeProcessManager(running=True)
    process_manager.no_ui_mode = True
    script_executor = FakeScriptExecutor(
        results=[
            {"success": True, "status": {"project": {"path": r"C:\repo\Demo.project"}}},
            {"success": True, "message": "saved"},
            {"success": False, "error": "close failed"},
        ]
    )
    service = ActionService(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=FakeEngineAdapter(),
        logger=logging.getLogger("action-layer-test"),
        now_fn=lambda: 999.0,
        script_dir=Path(r"C:\repo"),
        sleep_fn=lambda _seconds: None,
    )

    result = service.execute(
        ActionRequest(action=ActionType.PROJECT_COMPILE, params={"clean_build": False})
    )

    assert result.status_code == 500
    assert result.body == {
        "success": False,
        "error": "close failed",
        "normalized_by": "project.close",
    }


def test_project_save_returns_script_result() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "message": "saved"},
    )

    result = service.execute(ActionRequest(action=ActionType.PROJECT_SAVE, params={}))

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "message": "saved",
        "normalized_by": "project.save",
    }


def test_project_close_returns_script_result() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "message": "closed"},
    )

    result = service.execute(ActionRequest(action=ActionType.PROJECT_CLOSE, params={}))

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "message": "closed",
        "normalized_by": "project.close",
    }


def test_project_list_returns_script_result() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "projects": [{"name": "Demo.project"}]},
    )

    result = service.execute(ActionRequest(action=ActionType.PROJECT_LIST, params={}))

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "projects": [{"name": "Demo.project"}],
        "normalized_by": "project.list",
    }


def test_pou_create_requires_name_type_and_language() -> None:
    service = make_service(running=True, script_result={"success": True})

    result = service.execute(
        ActionRequest(
            action=ActionType.POU_CREATE,
            params={"name": "MotorStarter", "type": "FunctionBlock"},
        )
    )

    assert result.status_code == 400
    assert result.body == {"success": False, "error": "Missing required parameter: language"}


def test_pou_code_uses_existing_validation() -> None:
    service = make_service(running=True, script_result={"success": True})

    result = service.execute(
        ActionRequest(
            action=ActionType.POU_CODE,
            params={"path": "Application/PLC_PRG"},
        )
    )

    assert result.status_code == 400
    assert result.body == {
        "success": False,
        "error": "Missing code parameter: need at least one of 'code', 'declaration', or 'implementation'",
    }


def test_pou_list_returns_script_result() -> None:
    service = make_service(
        running=True,
        script_result={"success": True, "pous": [{"name": "PLC_PRG"}]},
    )

    result = service.execute(
        ActionRequest(action=ActionType.POU_LIST, params={"parentPath": "Application"})
    )

    assert result.status_code == 200
    assert result.body == {
        "success": True,
        "pous": [{"name": "PLC_PRG"}],
        "normalized_by": "pou.list",
    }
