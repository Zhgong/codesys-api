from __future__ import annotations

import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from urllib.error import URLError
from unittest.mock import patch

from codesys_api.action_layer import ActionRequest, ActionService, ActionType
from codesys_api.engine_adapter import EngineCapabilities, ExecutionSpec


class UnusedProcessManager:
    def is_running(self) -> bool:
        raise AssertionError("system.doctor must not touch process manager")

    def start(self) -> bool:
        raise AssertionError("system.doctor must not start process")

    def stop(self) -> bool:
        raise AssertionError("system.doctor must not stop process")

    def get_status(self) -> dict[str, object]:
        raise AssertionError("system.doctor must not query process status")

    def is_no_ui_mode(self) -> bool:
        raise AssertionError("system.doctor must not read noUI mode")

    def set_no_ui_mode(self, no_ui: bool) -> None:
        raise AssertionError("system.doctor must not modify noUI mode")

    def reset_runtime_mode(self) -> None:
        raise AssertionError("system.doctor must not reset runtime mode")


class UnusedScriptExecutor:
    def execute_script(self, script: str, timeout: int = 60) -> dict[str, object]:
        raise AssertionError("system.doctor must not execute scripts")


class UnusedEngineAdapter:
    engine_name = "unused"

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            session_start=False,
            session_status=False,
            script_execute=False,
            project_create=False,
            project_open=False,
            project_save=False,
            project_close=False,
            project_list=False,
            project_compile=False,
            pou_create=False,
            pou_code=False,
            pou_list=False,
        )

    def build_execution(self, action: str, params: dict[str, object]) -> ExecutionSpec:
        raise AssertionError("system.doctor must not build engine scripts")

    def normalize_result(self, action: str, raw_result: dict[str, object]) -> dict[str, object]:
        raise AssertionError("system.doctor must not normalize engine results")


def make_service(script_dir: Path) -> ActionService:
    return ActionService(
        process_manager=UnusedProcessManager(),
        script_executor=UnusedScriptExecutor(),
        engine_adapter=UnusedEngineAdapter(),
        logger=logging.getLogger("doctor-logic-test"),
        now_fn=lambda: 123.0,
        script_dir=script_dir,
    )


class FakeSocket:
    def __init__(self, bound_calls: list[tuple[str, int]]) -> None:
        self.bound_calls = bound_calls

    def bind(self, address: tuple[str, int]) -> None:
        self.bound_calls.append(address)

    def close(self) -> None:
        return None


class FailingBindSocket:
    def bind(self, _address: tuple[str, int]) -> None:
        raise OSError("Address already in use")

    def close(self) -> None:
        return None


class FakeUrlOpenResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> FakeUrlOpenResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


def test_doctor_os_fail(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch("codesys_api.action_layer.sys.platform", "linux"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(tmp_path / "missing.exe"),
            },
            clear=True,
        ):
            result = service.execute(ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={}))

    checks = cast(list[dict[str, str]], result.body["checks"])
    os_check = next(check for check in checks if check["name"] == "Operating system")
    assert os_check["status"] == "FAIL"
    assert "Windows" in os_check["suggestion"]
    assert os_check["suggestion"]
    assert result.body["success"] is True


def test_system_doctor_runs_full_check_chain_with_required_mocks(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    codesys_exe = tmp_path / "CODESYS.exe"
    codesys_exe.write_text("binary", encoding="utf-8")
    socket_binds: list[tuple[str, int]] = []
    pipe_calls: list[str] = []

    class FakePipeHandle:
        def __init__(self) -> None:
            self.closed = False

        def Close(self) -> None:
            self.closed = True

    fake_handle = FakePipeHandle()

    def fake_create_named_pipe(
        pipe_name: str,
        _open_mode: int,
        _pipe_mode: int,
        _max_instances: int,
        _out_buffer_size: int,
        _in_buffer_size: int,
        _timeout_ms: int,
        _security_attrs: object,
    ) -> FakePipeHandle:
        pipe_calls.append(pipe_name)
        return fake_handle

    fake_win32pipe = SimpleNamespace(
        PIPE_ACCESS_DUPLEX=1,
        PIPE_TYPE_MESSAGE=2,
        PIPE_READMODE_MESSAGE=4,
        PIPE_WAIT=8,
        PIPE_UNLIMITED_INSTANCES=255,
        CreateNamedPipe=fake_create_named_pipe,
    )

    with patch("codesys_api.action_layer.sys.platform", "win32"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(codesys_exe),
                "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP21",
                "CODESYS_API_SERVER_PORT": "8080",
            },
            clear=True,
        ):
            with patch("codesys_api.action_layer.os.access", return_value=True):
                with patch("codesys_api.action_layer.load_server_config", return_value=object()):
                    with patch("codesys_api.action_layer.socket.socket", return_value=FakeSocket(socket_binds)):
                        with patch(
                            "codesys_api.action_layer.urllib.request.urlopen",
                            return_value=FakeUrlOpenResponse(status=200),
                        ):
                            with patch.dict("sys.modules", {"win32pipe": fake_win32pipe}, clear=False):
                                with patch("codesys_api.action_layer.importlib.import_module", return_value=object()):
                                    result = service.execute(
                                        ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={})
                                    )

    checks = cast(list[dict[str, str]], result.body["checks"])
    expected_names = [
        "Operating system",
        "Python dependency: win32api",
        "Python dependency: requests",
        "CODESYS path environment",
        "CODESYS profile environment",
        "Configuration validity",
        "CODESYS binary",
        "Named pipe creation",
        "HTTP port availability",
        "Server connectivity",
    ]
    assert [check["name"] for check in checks] == expected_names
    assert all(check["status"] == "PASS" for check in checks)
    assert result.body["success"] is True
    assert socket_binds == [("127.0.0.1", 8080)]
    assert pipe_calls and pipe_calls[0].startswith(r"\\.\pipe\codesys_api_doctor_test_")
    assert fake_handle.closed is True


def test_doctor_pipe_permission_denied(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    codesys_exe = tmp_path / "CODESYS.exe"
    codesys_exe.write_text("binary", encoding="utf-8")

    def _denied_pipe(*_args: object, **_kwargs: object) -> object:
        raise OSError("Access denied")

    fake_win32pipe = SimpleNamespace(
        PIPE_ACCESS_DUPLEX=1,
        PIPE_TYPE_MESSAGE=2,
        PIPE_READMODE_MESSAGE=4,
        PIPE_WAIT=8,
        PIPE_UNLIMITED_INSTANCES=255,
        CreateNamedPipe=_denied_pipe,
    )

    with patch("codesys_api.action_layer.sys.platform", "win32"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(codesys_exe),
                "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP21",
                "CODESYS_API_SERVER_PORT": "8080",
            },
            clear=True,
        ):
            with patch("codesys_api.action_layer.os.access", return_value=True):
                with patch("codesys_api.action_layer.load_server_config", return_value=object()):
                    with patch("codesys_api.action_layer.socket.socket", return_value=FakeSocket(bound_calls=[])):
                        with patch(
                            "codesys_api.action_layer.urllib.request.urlopen",
                            return_value=FakeUrlOpenResponse(status=200),
                        ):
                            with patch.dict("sys.modules", {"win32pipe": fake_win32pipe}, clear=False):
                                with patch("codesys_api.action_layer.importlib.import_module", return_value=object()):
                                    result = service.execute(
                                        ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={})
                                    )

    checks = cast(list[dict[str, str]], result.body["checks"])
    pipe_check = next(check for check in checks if check["name"] == "Named pipe creation")
    assert pipe_check["status"] == "FAIL"
    assert pipe_check["suggestion"] == "Check administrator privileges or Windows pipe permissions."


def test_doctor_port_collision(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    codesys_exe = tmp_path / "CODESYS.exe"
    codesys_exe.write_text("binary", encoding="utf-8")

    fake_win32pipe = SimpleNamespace(
        PIPE_ACCESS_DUPLEX=1,
        PIPE_TYPE_MESSAGE=2,
        PIPE_READMODE_MESSAGE=4,
        PIPE_WAIT=8,
        PIPE_UNLIMITED_INSTANCES=255,
        CreateNamedPipe=lambda *_args, **_kwargs: SimpleNamespace(Close=lambda: None),
    )

    with patch("codesys_api.action_layer.sys.platform", "win32"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(codesys_exe),
                "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP21",
                "CODESYS_API_SERVER_PORT": "8080",
            },
            clear=True,
        ):
            with patch("codesys_api.action_layer.os.access", return_value=True):
                with patch("codesys_api.action_layer.load_server_config", return_value=object()):
                    with patch("codesys_api.action_layer.socket.socket", return_value=FailingBindSocket()):
                        with patch(
                            "codesys_api.action_layer.urllib.request.urlopen",
                            return_value=FakeUrlOpenResponse(status=200),
                        ):
                            with patch.dict("sys.modules", {"win32pipe": fake_win32pipe}, clear=False):
                                with patch("codesys_api.action_layer.importlib.import_module", return_value=object()):
                                    result = service.execute(
                                        ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={})
                                    )

    checks = cast(list[dict[str, str]], result.body["checks"])
    port_check = next(check for check in checks if check["name"] == "HTTP port availability")
    assert port_check["status"] == "FAIL"
    assert "port 8080" in port_check["suggestion"].lower()


def test_doctor_server_offline(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    codesys_exe = tmp_path / "CODESYS.exe"
    codesys_exe.write_text("binary", encoding="utf-8")

    fake_win32pipe = SimpleNamespace(
        PIPE_ACCESS_DUPLEX=1,
        PIPE_TYPE_MESSAGE=2,
        PIPE_READMODE_MESSAGE=4,
        PIPE_WAIT=8,
        PIPE_UNLIMITED_INSTANCES=255,
        CreateNamedPipe=lambda *_args, **_kwargs: SimpleNamespace(Close=lambda: None),
    )

    with patch("codesys_api.action_layer.sys.platform", "win32"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(codesys_exe),
                "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP21",
                "CODESYS_API_SERVER_PORT": "8080",
            },
            clear=True,
        ):
            with patch("codesys_api.action_layer.os.access", return_value=True):
                with patch("codesys_api.action_layer.load_server_config", return_value=object()):
                    with patch(
                        "codesys_api.action_layer.socket.socket",
                        return_value=FakeSocket(bound_calls=[]),
                    ):
                        with patch(
                            "codesys_api.action_layer.urllib.request.urlopen",
                            side_effect=URLError("connection refused"),
                        ):
                            with patch.dict("sys.modules", {"win32pipe": fake_win32pipe}, clear=False):
                                with patch("codesys_api.action_layer.importlib.import_module", return_value=object()):
                                    result = service.execute(
                                        ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={})
                                    )

    checks = cast(list[dict[str, str]], result.body["checks"])
    connectivity_check = next(check for check in checks if check["name"] == "Server connectivity")
    assert connectivity_check["status"] == "WARN"
    assert "codesys-tools-server" in connectivity_check["suggestion"]
    assert result.body["success"] is True


def test_doctor_config_corrupted(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    codesys_exe = tmp_path / "CODESYS.exe"
    codesys_exe.write_text("binary", encoding="utf-8")

    with patch("codesys_api.action_layer.sys.platform", "win32"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(codesys_exe),
                "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP21",
            },
            clear=True,
        ):
            with patch("codesys_api.action_layer.os.access", return_value=True):
                with patch(
                    "codesys_api.action_layer.load_server_config",
                    side_effect=ValueError("bad port value"),
                ):
                    with patch("codesys_api.action_layer.importlib.import_module", return_value=object()):
                        result = service.execute(ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={}))

    checks = cast(list[dict[str, str]], result.body["checks"])
    config_check = next(check for check in checks if check["name"] == "Configuration validity")
    assert config_check["status"] == "FAIL"
    assert "Fix formatting errors in your .env or config file." == config_check["suggestion"]


def test_doctor_execution_permission_fail(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    codesys_exe = tmp_path / "CODESYS.exe"
    codesys_exe.write_text("binary", encoding="utf-8")

    with patch("codesys_api.action_layer.sys.platform", "win32"):
        with patch.dict(
            os.environ,
            {
                "CODESYS_API_CODESYS_PATH": str(codesys_exe),
                "CODESYS_API_CODESYS_PROFILE": "CODESYS V3.5 SP21",
            },
            clear=True,
        ):
            with patch("codesys_api.action_layer.os.access", return_value=False):
                with patch("codesys_api.action_layer.load_server_config", return_value=object()):
                    with patch("codesys_api.action_layer.importlib.import_module", return_value=object()):
                        result = service.execute(ActionRequest(action=ActionType.SYSTEM_DOCTOR, params={}))

    checks = cast(list[dict[str, str]], result.body["checks"])
    binary_check = next(check for check in checks if check["name"] == "CODESYS binary")
    assert binary_check["status"] == "FAIL"
    assert "Grant execution permissions to the current user for CODESYS.exe." == binary_check["suggestion"]
