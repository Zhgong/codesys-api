from __future__ import annotations

import json
from pathlib import Path

from file_ipc import (
    FileIpcRequestArtifacts,
    build_timeout_result,
    create_ipc_request,
    determine_poll_interval,
    read_ipc_result,
)


def test_create_ipc_request_writes_script_and_request_files(tmp_path: Path) -> None:
    request_root = tmp_path / "requests"
    temp_root = tmp_path / "temp"
    request_root.mkdir()
    temp_root.mkdir()

    artifacts = create_ipc_request(
        script_content="print('hello')",
        request_id="req-123",
        request_root=request_root,
        temp_root=temp_root,
        timestamp=42.0,
    )

    assert isinstance(artifacts, FileIpcRequestArtifacts)
    assert artifacts.script_path.read_text(encoding="utf-8") == "print('hello')"
    payload = json.loads(artifacts.request_path.read_text(encoding="utf-8"))
    assert payload["request_id"] == "req-123"
    assert payload["timestamp"] == 42.0
    assert payload["script_path"] == str(artifacts.script_path).replace("\\", "\\\\")
    assert payload["result_path"] == str(artifacts.result_path).replace("\\", "\\\\")


def test_read_ipc_result_reads_valid_json(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"success": True, "value": 5}), encoding="utf-8")

    result = read_ipc_result(
        result_path,
        max_retries=2,
        settle_delay_seconds=0.0,
        retry_delay_seconds=0.0,
    )

    assert result == {"success": True, "value": 5}


def test_read_ipc_result_retries_until_json_is_valid(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text("{", encoding="utf-8")
    calls = {"count": 0}

    def fake_sleep(_seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            result_path.write_text(json.dumps({"success": True, "value": 9}), encoding="utf-8")

    result = read_ipc_result(
        result_path,
        max_retries=3,
        settle_delay_seconds=0.0,
        retry_delay_seconds=0.0,
        sleep_fn=fake_sleep,
    )

    assert result == {"success": True, "value": 9}


def test_build_timeout_result_marks_timeout() -> None:
    result = build_timeout_result(12.3456)

    assert result["success"] is False
    assert result["timeout"] is True
    assert "12.35" in str(result["error"])


def test_determine_poll_interval_progression() -> None:
    assert determine_poll_interval(0.1) == 0.1
    assert determine_poll_interval(6.0) == 0.5
    assert determine_poll_interval(31.0) == 1.0
