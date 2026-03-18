from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any
from urllib import error, request

import pytest

from codesys_e2e_policy import (
    LEGACY_TRANSPORT,
    current_codesys_e2e_transport,
    legacy_file_full_track_enabled,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_COMPILE_TIMEOUT = 300


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def call_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    api_key: str = "admin",
    timeout: int = 10,
) -> tuple[int, dict[str, Any]]:
    data: bytes | None = None
    headers = {"Authorization": f"ApiKey {api_key}"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"text": body}
        return exc.code, parsed


def wait_for_server(base_url: str) -> None:
    deadline = time.time() + 20
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            status_code, payload = call_json(base_url, "/api/v1/system/info")
            if status_code == 200 and payload.get("success") is True:
                return
        except Exception as exc:  # pragma: no cover - retry path
            last_error = exc
        time.sleep(0.2)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Real CODESYS server did not become ready in time")


def wait_for_session_state(
    base_url: str,
    *,
    process_running: bool,
    session_active: bool | None = None,
    timeout: int = 40,
) -> None:
    deadline = time.time() + timeout
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        status_code, payload = session_status(base_url)
        last_payload = payload
        if status_code == 200 and payload.get("success") is True:
            status = payload.get("status")
            if isinstance(status, dict):
                process = status.get("process")
                session = status.get("session")
                running = isinstance(process, dict) and process.get("running") is process_running
                if session_active is None:
                    if running:
                        return
                elif isinstance(session, dict) and running and session.get("session_active") is session_active:
                    return
        time.sleep(0.5)

    raise RuntimeError(f"Timed out waiting for session state: {last_payload}")


def stop_session(base_url: str) -> tuple[int, dict[str, Any]]:
    result = call_json(
        base_url,
        "/api/v1/session/stop",
        method="POST",
        payload={},
        timeout=30,
    )
    wait_for_session_state(base_url, process_running=False, timeout=45)
    return result


def start_session(base_url: str) -> tuple[int, dict[str, Any]]:
    result = call_json(
        base_url,
        "/api/v1/session/start",
        method="POST",
        payload={},
        timeout=120,
    )
    if result[0] == 200 and result[1].get("success") is True:
        wait_for_session_state(base_url, process_running=True, session_active=True, timeout=45)
    return result


def session_status(base_url: str) -> tuple[int, dict[str, Any]]:
    return call_json(
        base_url,
        "/api/v1/session/status",
        timeout=30,
    )


def skip_if_legacy_file_full_track_not_enabled() -> None:
    if current_codesys_e2e_transport(os.environ) == LEGACY_TRANSPORT and not legacy_file_full_track_enabled(os.environ):
        pytest.skip(
            "Legacy file transport only runs fast-track E2E by default; "
            "set CODESYS_E2E_FILE_FULL=1 to run slow-track checks"
        )


def codesys_env() -> dict[str, str]:
    if os.environ.get("CODESYS_E2E_ENABLE") != "1":
        pytest.skip("Set CODESYS_E2E_ENABLE=1 to run real CODESYS E2E tests")

    required = {
        "CODESYS_API_CODESYS_PATH": os.environ.get("CODESYS_API_CODESYS_PATH"),
        "CODESYS_API_CODESYS_PROFILE": os.environ.get("CODESYS_API_CODESYS_PROFILE"),
        "CODESYS_API_CODESYS_PROFILE_PATH": os.environ.get("CODESYS_API_CODESYS_PROFILE_PATH"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"Missing required real CODESYS environment variables: {', '.join(missing)}")

    env = os.environ.copy()
    env["CODESYS_API_SERVER_HOST"] = "127.0.0.1"
    env["CODESYS_API_SERVER_PORT"] = str(find_free_port())
    env["CODESYS_API_CODESYS_NO_UI"] = os.environ.get("CODESYS_E2E_NO_UI", "false")
    env["CODESYS_API_TRANSPORT"] = current_codesys_e2e_transport(os.environ)
    env["CODESYS_API_PIPE_NAME"] = "codesys_api_e2e_{0}".format(env["CODESYS_API_SERVER_PORT"])
    return env


def assert_session_started(base_url: str) -> None:
    status_code, payload = start_session(base_url)
    assert status_code == 200
    assert payload["success"] is True


@pytest.fixture(scope="module")
def real_server() -> Generator[tuple[str, subprocess.Popen[str]], None, None]:
    env = codesys_env()
    base_url = f"http://127.0.0.1:{env['CODESYS_API_SERVER_PORT']}"

    process = subprocess.Popen(
        [sys.executable, "HTTP_SERVER.py"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_for_server(base_url)
        yield base_url, process
    finally:
        try:
            stop_session(base_url)
        except Exception:
            pass
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@pytest.mark.codesys
@pytest.mark.codesys_main
def test_real_codesys_main_flow(real_server: tuple[str, subprocess.Popen[str]]) -> None:
    base_url, _process = real_server
    stop_session(base_url)
    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_e2e_{uuid.uuid4().hex}.project")

    status_code, payload = start_session(base_url)
    assert status_code == 200
    assert payload["success"] is True

    status_code, payload = session_status(base_url)
    assert status_code == 200
    assert payload["success"] is True
    assert payload["status"]["process"]["running"] is True
    assert payload["status"]["session"]["session_active"] is True

    status_code, payload = call_json(
        base_url,
        "/api/v1/project/create",
        method="POST",
        payload={"path": project_path},
        timeout=120,
    )
    assert status_code == 200
    assert payload["success"] is True


@pytest.mark.codesys
@pytest.mark.codesys_slow
def test_real_codesys_restart_keeps_session_usable(real_server: tuple[str, subprocess.Popen[str]]) -> None:
    skip_if_legacy_file_full_track_not_enabled()
    base_url, _process = real_server
    stop_session(base_url)
    assert_session_started(base_url)

    status_code, payload = call_json(
        base_url,
        "/api/v1/session/restart",
        method="POST",
        payload={},
        timeout=150,
    )
    assert status_code == 200
    assert payload["success"] is True

    status_code, payload = session_status(base_url)
    assert status_code == 200
    assert payload["success"] is True
    assert payload["status"]["process"]["running"] is True
    assert payload["status"]["session"]["session_active"] is True


@pytest.mark.codesys
@pytest.mark.codesys_slow
def test_real_codesys_stop_is_repeatable(real_server: tuple[str, subprocess.Popen[str]]) -> None:
    skip_if_legacy_file_full_track_not_enabled()
    base_url, _process = real_server
    assert_session_started(base_url)

    first_status, first_payload = stop_session(base_url)
    second_status, second_payload = stop_session(base_url)

    assert first_status == 200
    assert first_payload["success"] is True
    assert second_status == 200
    assert second_payload["success"] is True


@pytest.mark.codesys
@pytest.mark.codesys_slow
def test_real_codesys_start_is_repeatable(real_server: tuple[str, subprocess.Popen[str]]) -> None:
    skip_if_legacy_file_full_track_not_enabled()
    base_url, _process = real_server
    stop_session(base_url)

    first_status, first_payload = start_session(base_url)
    second_status, second_payload = start_session(base_url)

    assert first_status == 200
    assert first_payload["success"] is True
    assert second_status == 200
    assert second_payload["success"] is True


@pytest.mark.codesys
@pytest.mark.codesys_slow
def test_real_codesys_compile_without_active_project_fails_cleanly(
    real_server: tuple[str, subprocess.Popen[str]],
) -> None:
    skip_if_legacy_file_full_track_not_enabled()
    base_url, _process = real_server
    stop_session(base_url)
    assert_session_started(base_url)
    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_compile_recovery_{uuid.uuid4().hex}.project")

    status_code, payload = call_json(
        base_url,
        "/api/v1/project/compile",
        method="POST",
        payload={"clean_build": False},
        timeout=REAL_COMPILE_TIMEOUT,
    )

    assert status_code == 500
    assert payload["success"] is False
    assert "active project" in str(payload["error"]).lower()

    status_code, payload = call_json(
        base_url,
        "/api/v1/project/create",
        method="POST",
        payload={"path": project_path},
        timeout=120,
    )
    assert status_code == 200
    assert payload["success"] is True

    status_code, payload = call_json(
        base_url,
        "/api/v1/pou/create",
        method="POST",
        payload={"name": "MotorController", "type": "FunctionBlock", "language": "ST"},
        timeout=120,
    )
    assert status_code == 200
    assert payload["success"] is True

    status_code, payload = call_json(
        base_url,
        "/api/v1/pou/code",
        method="POST",
        payload={
            "path": "Application/MotorController",
            "declaration": "FUNCTION_BLOCK MotorController\nVAR_INPUT\n    Enable : BOOL;\nEND_VAR",
            "implementation": "IF Enable THEN\nEND_IF;",
        },
        timeout=120,
    )
    assert status_code == 200
    assert payload["success"] is True

    status_code, payload = call_json(
        base_url,
        "/api/v1/project/compile",
        method="POST",
        payload={"clean_build": False},
        timeout=REAL_COMPILE_TIMEOUT,
    )
    assert status_code == 200
    assert payload["success"] is True
