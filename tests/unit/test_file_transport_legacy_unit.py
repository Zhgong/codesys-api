from __future__ import annotations

from pathlib import Path

import legacy_file_transport
import pytest
import session_transport
from file_ipc import FileIpcRequestArtifacts
from legacy_file_transport import FileScriptTransport, build_legacy_file_transport
from session_transport import build_script_transport
from transport_result import create_transport_execution


def test_legacy_file_transport_reports_timeout_with_transport_metadata(tmp_path: Path) -> None:
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
    assert "request_id" in result


def test_legacy_file_transport_reports_result_read_failure_with_transport_metadata(
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
        legacy_file_transport,
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
        legacy_file_transport,
        "read_ipc_result",
        lambda _path: (_ for _ in ()).throw(ValueError("invalid result payload")),
    )

    result = transport.execute_script("print('hello')", timeout=1)

    assert result["success"] is False
    assert result["transport"] == "file"
    assert result["error_stage"] == "result_read"
    assert "request_id" in result
    assert "invalid result payload" in str(result["error"]).lower()


def test_legacy_file_transport_waits_for_result_payload_until_it_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_dir = tmp_path / "requests"
    result_dir = tmp_path / "results"
    temp_root = tmp_path / "temp"
    request_dir.mkdir()
    result_dir.mkdir()
    temp_root.mkdir()
    result_path = temp_root / "result.json"

    transport = FileScriptTransport(
        request_dir=request_dir,
        result_dir=result_dir,
        temp_root=temp_root,
        now_fn=lambda: 10.0,
    )
    execution = create_transport_execution(
        script="print('hello')",
        timeout_hint=2,
        now_fn=lambda: 10.0,
        request_id_factory=lambda: "req-123",
    )

    attempts = {"count": 0}

    def fake_exists() -> bool:
        attempts["count"] += 1
        return attempts["count"] >= 2

    monkeypatch.setattr(Path, "exists", lambda self: fake_exists() if self == result_path else False)
    monkeypatch.setattr(legacy_file_transport, "read_ipc_result", lambda _path: {"success": True, "message": "ok"})

    result = transport._wait_for_result_payload(result_path, execution)

    assert attempts["count"] >= 2
    assert result["success"] is True


def test_build_legacy_file_transport_creates_file_transport(tmp_path: Path) -> None:
    transport = build_legacy_file_transport(
        request_dir=tmp_path / "requests",
        result_dir=tmp_path / "results",
        temp_root=tmp_path / "temp",
    )

    assert isinstance(transport, FileScriptTransport)
    assert transport.transport_name == "file"


def test_build_script_transport_routes_file_through_legacy_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    legacy_transport = FileScriptTransport(
        request_dir=tmp_path / "requests",
        result_dir=tmp_path / "results",
        temp_root=tmp_path / "temp",
    )
    called: dict[str, object] = {}

    def fake_build_legacy_file_transport(**kwargs: object) -> FileScriptTransport:
        called.update(kwargs)
        return legacy_transport

    monkeypatch.setattr(
        legacy_file_transport,
        "build_legacy_file_transport",
        fake_build_legacy_file_transport,
    )

    transport = build_script_transport(
        transport_name="file",
        request_dir=tmp_path / "requests",
        result_dir=tmp_path / "results",
        temp_root=tmp_path / "temp",
        pipe_name="unused",
    )

    assert transport is legacy_transport
    assert called["request_dir"] == tmp_path / "requests"
    assert called["result_dir"] == tmp_path / "results"
    assert called["temp_root"] == tmp_path / "temp"
