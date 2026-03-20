from __future__ import annotations

import logging
from typing import Any, cast

from named_pipe_transport import NamedPipeScriptTransport
import session_transport
import runtime_transport
from session_transport import build_primary_script_transport
from script_executor import ScriptExecutor


def test_script_executor_delegates_to_transport() -> None:
    calls: list[tuple[str, int]] = []

    class FakeTransport:
        def execute_script(self, script_content: str, timeout: int = 60) -> dict[str, object]:
            calls.append((script_content, timeout))
            return {"success": True, "message": "ok"}

    executor_factory = cast(Any, ScriptExecutor)
    executor = executor_factory(FakeTransport(), logger=logging.getLogger("script-executor-test"))

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

def test_session_transport_keeps_only_primary_facade_exports() -> None:
    assert session_transport.__all__ == [
        "TransportRequest",
        "TransportExecutionContext",
        "build_primary_script_transport",
    ]


def test_runtime_transport_module_keeps_only_primary_runtime_builder() -> None:
    assert not hasattr(runtime_transport, "build_legacy_file_transport")
