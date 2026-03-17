from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any, Final, TypedDict, cast


CODE_FIELDS: Final[tuple[str, ...]] = ("code", "declaration", "implementation")
DEFAULT_PROJECT_PREFIX: Final[str] = "CODESYS_Project_"


class ProcessStatusPayload(TypedDict):
    running: bool
    state: str
    timestamp: float


class SessionStatusPayload(TypedDict, total=False):
    active: bool
    session_active: bool
    project_open: bool
    project: dict[str, object]


class StatusPayload(TypedDict):
    process: ProcessStatusPayload
    session: SessionStatusPayload


def build_default_project_path(script_dir: str, timestamp: str) -> str:
    return os.path.join(script_dir, f"{DEFAULT_PROJECT_PREFIX}{timestamp}.project")


def normalize_project_create_params(
    params: Mapping[str, object],
    script_dir: str,
    timestamp: str,
) -> dict[str, object]:
    normalized = dict(params)
    raw_path = normalized.get("path")

    if not isinstance(raw_path, str) or not raw_path.strip():
        normalized["path"] = build_default_project_path(script_dir, timestamp)
    else:
        normalized["path"] = raw_path.replace("/", "\\")

    return normalized


def validate_required_params(params: Mapping[str, object], required_fields: Iterable[str]) -> str | None:
    for field in required_fields:
        if field not in params:
            return f"Missing required parameter: {field}"
    return None


def validate_pou_code_params(params: Mapping[str, object]) -> str | None:
    if "path" not in params:
        return "Missing required parameter: path"

    if not any(field in params for field in CODE_FIELDS):
        return "Missing code parameter: need at least one of 'code', 'declaration', or 'implementation'"

    return None


def build_status_payload(
    process_running: bool,
    process_status: Mapping[str, object],
    session_status_result: Mapping[str, object] | None,
    now: float,
) -> StatusPayload:
    if process_running:
        session_status = _build_running_session_status(process_running, session_status_result)
    else:
        session_status = {
            "active": False,
            "session_active": False,
            "project_open": False,
        }

    state = process_status.get("state")
    timestamp = process_status.get("timestamp")

    process_payload: ProcessStatusPayload = {
        "running": process_running,
        "state": state if isinstance(state, str) else "unknown",
        "timestamp": timestamp if isinstance(timestamp, (int, float)) else now,
    }

    return {
        "process": process_payload,
        "session": session_status,
    }


def _build_running_session_status(
    process_running: bool,
    session_status_result: Mapping[str, object] | None,
) -> SessionStatusPayload:
    if session_status_result is None:
        return _fallback_running_session_status(process_running)

    success = session_status_result.get("success")
    status = session_status_result.get("status")

    if success is True and isinstance(status, dict):
        return cast(SessionStatusPayload, status)

    return _fallback_running_session_status(process_running)


def _fallback_running_session_status(process_running: bool) -> SessionStatusPayload:
    return {
        "active": process_running,
        "session_active": process_running,
        "project_open": False,
    }
