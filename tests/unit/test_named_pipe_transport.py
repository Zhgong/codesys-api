from __future__ import annotations

import json

import named_pipe_transport
import pytest
from named_pipe_transport import (
    NamedPipeScriptTransport,
    build_pipe_path,
    decode_pipe_message,
    encode_pipe_message,
)


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
