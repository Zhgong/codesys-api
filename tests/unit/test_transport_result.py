from __future__ import annotations

from transport_result import (
    TransportExecutionContext,
    TransportRequest,
    create_transport_execution,
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


def test_create_transport_execution_builds_shared_request_and_deadline() -> None:
    execution = create_transport_execution(
        script="print('hello')",
        timeout_hint=12,
        now_fn=lambda: 123.5,
        request_id_factory=lambda: "req-123",
    )

    assert execution == TransportExecutionContext(
        request=TransportRequest(
            request_id="req-123",
            script="print('hello')",
            timeout_hint=12,
            created_at=123.5,
        ),
        started_at=123.5,
        deadline=135.5,
    )


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


def test_transport_execution_context_builds_timeout_error() -> None:
    execution = create_transport_execution(
        script="print('hello')",
        timeout_hint=12,
        now_fn=lambda: 100.0,
        request_id_factory=lambda: "req-123",
    )

    result = execution.build_timeout_error("file", now_fn=lambda: 112.5)

    assert result["success"] is False
    assert result["transport"] == "file"
    assert result["request_id"] == "req-123"
    assert result["error_stage"] == "timeout"


def test_transport_execution_context_reports_remaining_seconds() -> None:
    execution = create_transport_execution(
        script="print('hello')",
        timeout_hint=12,
        now_fn=lambda: 100.0,
        request_id_factory=lambda: "req-123",
    )

    assert execution.remaining_seconds(lambda: 104.5) == 7.5
    assert execution.remaining_seconds(lambda: 120.0) == 0.0


def test_transport_execution_context_builds_standard_error() -> None:
    execution = create_transport_execution(
        script="print('hello')",
        timeout_hint=12,
        now_fn=lambda: 100.0,
        request_id_factory=lambda: "req-123",
    )

    result = execution.build_error(
        "named_pipe",
        stage="connect",
        error="connect failed",
        retryable=False,
    )

    assert result["success"] is False
    assert result["transport"] == "named_pipe"
    assert result["request_id"] == "req-123"
    assert result["error_stage"] == "connect"
    assert result["retryable"] is False


def test_transport_execution_context_normalizes_success_result() -> None:
    execution = create_transport_execution(
        script="print('hello')",
        timeout_hint=12,
        now_fn=lambda: 100.0,
        request_id_factory=lambda: "req-123",
    )

    result = execution.normalize_result({"success": True, "message": "ok"}, "file")

    assert result["success"] is True
    assert result["transport"] == "file"
    assert result["request_id"] == "req-123"
