from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from file_ipc import build_timeout_result


NowFn = Callable[[], float]
RequestIdFactory = Callable[[], str]


@dataclass(frozen=True)
class TransportRequest:
    request_id: str
    script: str
    timeout_hint: int
    created_at: float

    def as_payload(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "script": self.script,
            "timeout_hint": self.timeout_hint,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class TransportExecutionContext:
    request: TransportRequest
    started_at: float
    deadline: float

    def elapsed_seconds(self, now_fn: NowFn = time.time) -> float:
        return max(0.0, float(now_fn()) - self.started_at)

    def remaining_seconds(self, now_fn: NowFn = time.time) -> float:
        return max(0.0, self.deadline - float(now_fn()))

    def timed_out(self, now_fn: NowFn = time.time) -> bool:
        return self.remaining_seconds(now_fn) <= 0.0

    def build_timeout_error(
        self,
        transport: str,
        *,
        now_fn: NowFn = time.time,
    ) -> dict[str, Any]:
        return build_timeout_transport_error(
            transport=transport,
            elapsed_seconds=self.elapsed_seconds(now_fn),
            request_id=self.request.request_id,
        )


def create_transport_request(
    *,
    script: str,
    timeout_hint: int,
    now_fn: NowFn = time.time,
    request_id_factory: RequestIdFactory | None = None,
) -> TransportRequest:
    if request_id_factory is None:
        request_id_factory = lambda: str(uuid.uuid4())
    return TransportRequest(
        request_id=str(request_id_factory()),
        script=script,
        timeout_hint=timeout_hint,
        created_at=float(now_fn()),
    )


def create_transport_execution(
    *,
    script: str,
    timeout_hint: int,
    now_fn: NowFn = time.time,
    request_id_factory: RequestIdFactory | None = None,
) -> TransportExecutionContext:
    started_at = float(now_fn())
    if request_id_factory is None:
        request_id_factory = lambda: str(uuid.uuid4())
    request = TransportRequest(
        request_id=str(request_id_factory()),
        script=script,
        timeout_hint=timeout_hint,
        created_at=started_at,
    )
    return TransportExecutionContext(
        request=request,
        started_at=started_at,
        deadline=started_at + timeout_hint,
    )


def build_transport_error(
    *,
    transport: str,
    stage: str,
    error: str,
    request_id: str | None = None,
    timeout: bool = False,
    retryable: bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": error,
        "transport": transport,
        "error_stage": stage,
    }
    if request_id is not None:
        result["request_id"] = request_id
    if timeout:
        result["timeout"] = True
    if retryable is not None:
        result["retryable"] = retryable
    return result


def build_timeout_transport_error(
    *,
    transport: str,
    elapsed_seconds: float,
    request_id: str | None = None,
) -> dict[str, Any]:
    timeout_result = build_timeout_result(elapsed_seconds)
    return build_transport_error(
        transport=transport,
        stage="timeout",
        error=str(timeout_result["error"]),
        request_id=request_id,
        timeout=True,
    )


def attach_transport_metadata(
    result: dict[str, object],
    *,
    transport: str,
    request_id: str | None = None,
    stage: str | None = None,
) -> dict[str, object]:
    return normalize_transport_result(
        result,
        transport=transport,
        request_id=request_id,
        stage=stage,
    )


def normalize_transport_result(
    result: dict[str, object],
    *,
    transport: str,
    request_id: str | None = None,
    stage: str | None = None,
) -> dict[str, object]:
    enriched = dict(result)
    enriched.setdefault("transport", transport)
    if request_id is not None:
        enriched.setdefault("request_id", request_id)
    if stage is not None:
        enriched.setdefault("error_stage", stage)
    return enriched
