from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, cast

from HTTP_SERVER import ScriptExecutor
from legacy_file_transport import FileScriptTransport, build_legacy_file_transport


def wait_for_request_file(request_dir: Path) -> Path:
    deadline = time.time() + 5
    while time.time() < deadline:
        matches = list(request_dir.glob("*.request"))
        if matches:
            return matches[0]
        time.sleep(0.01)
    raise RuntimeError("Request file was not created in time")


def test_legacy_file_transport_returns_result_from_ipc(tmp_path: Path) -> None:
    request_dir = tmp_path / "requests"
    result_dir = tmp_path / "results"
    request_dir.mkdir()
    result_dir.mkdir()

    executor_factory = cast(Any, ScriptExecutor)
    transport = FileScriptTransport(
        request_dir=request_dir,
        result_dir=result_dir,
        temp_root=tmp_path / "temp",
    )
    transport.temp_root.mkdir()
    executor = executor_factory(transport)

    def responder() -> None:
        request_file = wait_for_request_file(request_dir)
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        result_path = Path(payload["result_path"].replace("\\\\", "\\"))
        result_path.write_text(
            json.dumps({"success": True, "message": "ok"}),
            encoding="utf-8",
        )

    thread = threading.Thread(target=responder, daemon=True)
    thread.start()

    result = executor.execute_script("print('hello')", timeout=2)
    thread.join(timeout=1)

    assert result["success"] is True
    assert result["message"] == "ok"
    assert result["transport"] == "file"
    assert "request_id" in result
    assert list(request_dir.glob("*.request")) == []


def test_legacy_file_transport_returns_timeout_result_when_no_ipc_response_arrives(tmp_path: Path) -> None:
    request_dir = tmp_path / "requests"
    result_dir = tmp_path / "results"
    request_dir.mkdir()
    result_dir.mkdir()

    executor_factory = cast(Any, ScriptExecutor)
    transport = FileScriptTransport(
        request_dir=request_dir,
        result_dir=result_dir,
        temp_root=tmp_path / "temp",
    )
    transport.temp_root.mkdir()
    executor = executor_factory(transport)

    result = executor.execute_script("print('hello')", timeout=0.2)

    assert result["success"] is False
    assert result["timeout"] is True
    assert result["transport"] == "file"
    assert result["error_stage"] == "timeout"
    assert "request_id" in result


def test_build_legacy_file_transport_creates_legacy_file_transport(tmp_path: Path) -> None:
    transport = build_legacy_file_transport(
        request_dir=tmp_path / "requests",
        result_dir=tmp_path / "results",
        temp_root=tmp_path / "temp",
    )

    assert isinstance(transport, FileScriptTransport)
    assert transport.transport_name == "file"

