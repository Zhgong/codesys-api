from __future__ import annotations

from typing import Any


def build_transport_error(
    *,
    transport: str,
    stage: str,
    error: str,
    timeout: bool = False,
    retryable: bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": error,
        "transport": transport,
        "error_stage": stage,
    }
    if timeout:
        result["timeout"] = True
    if retryable is not None:
        result["retryable"] = retryable
    return result


def attach_transport_metadata(
    result: dict[str, object],
    *,
    transport: str,
    stage: str | None = None,
) -> dict[str, object]:
    enriched = dict(result)
    enriched.setdefault("transport", transport)
    if stage is not None:
        enriched.setdefault("error_stage", stage)
    return enriched
