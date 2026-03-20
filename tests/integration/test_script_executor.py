from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from HTTP_SERVER import ScriptExecutor
from named_pipe_transport import NamedPipeScriptTransport
import session_transport
from session_transport import build_primary_script_transport, build_script_transport


def test_script_executor_delegates_to_transport() -> None:
    calls: list[tuple[str, int]] = []

    class FakeTransport:
        def execute_script(self, script_content: str, timeout: int = 60) -> dict[str, object]:
            calls.append((script_content, timeout))
            return {"success": True, "message": "ok"}

    executor_factory = cast(Any, ScriptExecutor)
    executor = executor_factory(FakeTransport())

    result = executor.execute_script("print('hello')", timeout=2)

    assert calls == [("print('hello')", 2)]
    assert result["success"] is True
    assert result["message"] == "ok"


def test_build_primary_script_transport_creates_named_pipe_transport() -> None:
    transport = build_primary_script_transport(
        pipe_name="codesys_api_test_pipe",
    )

    assert isinstance(transport, NamedPipeScriptTransport)
    assert transport.transport_name == "named_pipe"


def test_build_script_transport_creates_named_pipe_transport(tmp_path: Path) -> None:
    transport = build_script_transport(
        transport_name="named_pipe",
        request_dir=tmp_path / "requests",
        result_dir=tmp_path / "results",
        temp_root=tmp_path / "temp",
        pipe_name="codesys_api_test_pipe",
    )

    assert isinstance(transport, NamedPipeScriptTransport)
    assert transport.transport_name == "named_pipe"


def test_session_transport_keeps_only_primary_facade_exports() -> None:
    assert session_transport.__all__ == [
        "TransportRequest",
        "TransportExecutionContext",
        "build_primary_script_transport",
        "build_script_transport",
    ]
    assert not hasattr(session_transport, "FileScriptTransport")
    assert not hasattr(session_transport, "build_legacy_file_transport")


def test_build_script_transport_rejects_unknown_transport(tmp_path: Path) -> None:
    try:
        build_script_transport(
            transport_name="unknown",
            request_dir=tmp_path / "requests",
            result_dir=tmp_path / "results",
            temp_root=tmp_path / "temp",
            pipe_name="codesys_api_test_pipe",
        )
    except ValueError as exc:
        assert "unsupported transport" in str(exc).lower()
    else:
        raise AssertionError("Expected build_script_transport to reject unknown transport")
