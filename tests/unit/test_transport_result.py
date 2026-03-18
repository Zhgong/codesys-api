from __future__ import annotations

from transport_result import (
    TransportRequest,
    attach_transport_metadata,
    build_timeout_transport_error,
    build_transport_error,
    create_transport_request,
    normalize_transport_result,
)


def test_create_transport_request_builds_stable_envelope() -> None:
    request = create_transport_request(
        script="print('hello')",
        timeout_hint=12,
        now_fn=lambda: 123.5,
        request_id_factory=lambda: "req-123",
    )

    assert request == TransportRequest(
        request_id="req-123",
        script="print('hello')",
        timeout_hint=12,
        created_at=123.5,
    )
    assert request.as_payload() == {
        "request_id": "req-123",
        "script": "print('hello')",
        "timeout_hint": 12,
        "created_at": 123.5,
    }


def test_build_timeout_transport_error_includes_transport_metadata() -> None:
    result = build_timeout_transport_error(
        transport="named_pipe",
        elapsed_seconds=2.5,
        request_id="req-123",
    )

    assert result["success"] is False
    assert result["transport"] == "named_pipe"
    assert result["error_stage"] == "timeout"
    assert result["timeout"] is True
    assert result["request_id"] == "req-123"
    assert "timed out" in str(result["error"]).lower()


def test_build_transport_error_can_include_request_id() -> None:
    result = build_transport_error(
        transport="file",
        stage="request_create",
        error="boom",
        request_id="req-123",
    )

    assert result["success"] is False
    assert result["transport"] == "file"
    assert result["request_id"] == "req-123"


def test_attach_transport_metadata_backfills_request_id() -> None:
    result = attach_transport_metadata(
        {"success": True, "message": "ok"},
        transport="file",
        request_id="req-123",
    )

    assert result["transport"] == "file"
    assert result["request_id"] == "req-123"


def test_normalize_transport_result_preserves_existing_request_id() -> None:
    result = normalize_transport_result(
        {"success": True, "message": "ok", "request_id": "engine-req"},
        transport="named_pipe",
        request_id="outer-req",
    )

    assert result["transport"] == "named_pipe"
    assert result["request_id"] == "engine-req"
