from __future__ import annotations

import json
from pathlib import Path

import named_pipe_transport
import pytest
import session_transport
from file_ipc import FileIpcRequestArtifacts
from named_pipe_transport import (
    NamedPipeScriptTransport,
    build_pipe_path,
    decode_pipe_message,
    encode_pipe_message,
)
from session_transport import FileScriptTransport


def test_encode_pipe_message_round_trips_json_payload() -> None:
    payload = {"request_id": "req-1", "script": "print('hi')", "timeout_hint": 30}

    encoded = encode_pipe_message(payload)
    decoded = decode_pipe_message(encoded[4:])

    assert len(encoded) > 4
    assert decoded == payload


def test_named_pipe_transport_builds_request_and_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_connect(self: NamedPipeScriptTransport, timeout: int) -> object:
        captured["timeout"] = timeout
        return object()

    def fake_write(_handle: object, payload: dict[str, object]) -> None:
        captured["payload"] = payload

    def fake_read(_handle: object) -> dict[str, object]:
        request_payload = captured["payload"]
        assert isinstance(request_payload, dict)
        return {
            "request_id": request_payload["request_id"],
            "success": True,
            "message": "ok",
        }

    monkeypatch.setattr(NamedPipeScriptTransport, "_connect", fake_connect)
    monkeypatch.setattr(named_pipe_transport, "write_pipe_payload", fake_write)
    monkeypatch.setattr(named_pipe_transport, "read_pipe_payload", fake_read)
    monkeypatch.setattr(named_pipe_transport, "close_pipe_handle", lambda _handle: None)

    transport = NamedPipeScriptTransport(pipe_name="codesys_api_test_pipe")
    result = transport.execute_script("print('hello')", timeout=2)

    assert captured["timeout"] == 1
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["script"] == "print('hello')"
    assert payload["timeout_hint"] == 2
    assert result["success"] is True
    assert result["message"] == "ok"


def test_named_pipe_transport_retries_transient_write_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"connect": 0, "write": 0}
    captured: dict[str, object] = {}

    def fake_connect(self: NamedPipeScriptTransport, timeout: int) -> object:
        calls["connect"] += 1
        return object()

    def fake_write(_handle: object, payload: dict[str, object]) -> None:
        calls["write"] += 1
        captured["payload"] = payload
        if calls["write"] == 1:
            raise OSError(6, "WriteFile failed")

    def fake_read(_handle: object) -> dict[str, object]:
        request_payload = captured["payload"]
        assert isinstance(request_payload, dict)
        return {
            "request_id": request_payload["request_id"],
            "success": True,
            "message": "ok",
        }

    monkeypatch.setattr(NamedPipeScriptTransport, "_connect", fake_connect)
    monkeypatch.setattr(named_pipe_transport, "write_pipe_payload", fake_write)
    monkeypatch.setattr(named_pipe_transport, "read_pipe_payload", fake_read)
    monkeypatch.setattr(named_pipe_transport, "close_pipe_handle", lambda _handle: None)

    transport = NamedPipeScriptTransport(pipe_name="codesys_api_test_pipe")
    result = transport.execute_script("print('hello')", timeout=2)

    assert calls["connect"] == 2
    assert calls["write"] == 2
    assert result["success"] is True


def test_named_pipe_transport_reports_connect_failure_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_connect(self: NamedPipeScriptTransport, timeout: int) -> object:
        raise OSError(2, "CreateFileW failed while connecting to named pipe")

    monkeypatch.setattr(NamedPipeScriptTransport, "_connect", fake_connect)

    transport = NamedPipeScriptTransport(pipe_name="codesys_api_test_pipe")
    result = transport.execute_script("print('hello')", timeout=2)

    assert result["success"] is False
    assert result["transport"] == "named_pipe"
    assert result["error_stage"] == "connect"
    assert "connecting to named pipe" in str(result["error"]).lower()


def test_named_pipe_transport_reports_response_mismatch_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(NamedPipeScriptTransport, "_connect", lambda self, timeout: object())
    monkeypatch.setattr(named_pipe_transport, "write_pipe_payload", lambda _handle, payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        named_pipe_transport,
        "read_pipe_payload",
        lambda _handle: {"request_id": "wrong-id", "success": True},
    )
    monkeypatch.setattr(named_pipe_transport, "close_pipe_handle", lambda _handle: None)

    transport = NamedPipeScriptTransport(pipe_name="codesys_api_test_pipe")
    result = transport.execute_script("print('hello')", timeout=2)

    assert result["success"] is False
    assert result["transport"] == "named_pipe"
    assert result["error_stage"] == "response_mismatch"
    assert "request_id mismatch" in str(result["error"]).lower()


def test_file_transport_reports_timeout_with_transport_metadata(tmp_path: Path) -> None:
    request_dir = tmp_path / "requests"
    result_dir = tmp_path / "results"
    temp_root = tmp_path / "temp"
    request_dir.mkdir()
    result_dir.mkdir()
    temp_root.mkdir()

    transport = FileScriptTransport(
        request_dir=request_dir,
        result_dir=result_dir,
        temp_root=temp_root,
    )

    result = transport.execute_script("print('hello')", timeout=0)

    assert result["success"] is False
    assert result["transport"] == "file"
    assert result["error_stage"] == "timeout"
    assert result["timeout"] is True


def test_file_transport_reports_result_read_failure_with_transport_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_dir = tmp_path / "requests"
    result_dir = tmp_path / "results"
    temp_root = tmp_path / "temp"
    request_dir.mkdir()
    result_dir.mkdir()
    temp_root.mkdir()

    transport = FileScriptTransport(
        request_dir=request_dir,
        result_dir=result_dir,
        temp_root=temp_root,
    )

    request_id = "req-123"
    request_work_dir = temp_root / "codesys_req_req-123"
    request_work_dir.mkdir()
    script_path = request_work_dir / "script.py"
    result_path = request_work_dir / "result.json"
    request_path = request_dir / "req-123.request"
    script_path.write_text("print('hello')", encoding="utf-8")
    result_path.write_text("{}", encoding="utf-8")
    request_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        session_transport,
        "create_ipc_request",
        lambda **_kwargs: FileIpcRequestArtifacts(
            request_id=request_id,
            request_dir=request_work_dir,
            script_path=script_path,
            result_path=result_path,
            request_path=request_path,
        ),
    )
    monkeypatch.setattr(
        session_transport,
        "read_ipc_result",
        lambda _path: (_ for _ in ()).throw(ValueError("invalid result payload")),
    )

    result = transport.execute_script("print('hello')", timeout=1)

    assert result["success"] is False
    assert result["transport"] == "file"
    assert result["error_stage"] == "result_read"
    assert "invalid result payload" in str(result["error"]).lower()
