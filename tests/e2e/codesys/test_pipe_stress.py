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

from codesys_api.codesys_e2e_policy import (
    current_codesys_e2e_transport,
    current_codesys_e2e_transport_is_supported,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
PIPE_STRESS_ITERATIONS = 20
PIPE_STRESS_LIFECYCLE_CYCLES = 8


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

    if not current_codesys_e2e_transport_is_supported(os.environ):
        pytest.skip("Only named_pipe real E2E transport is supported in the current host-side runtime")

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
def test_pipe_stress_repeated_roundtrips(real_server: tuple[str, subprocess.Popen[str]]) -> None:
    """
    Stress test: single session, 20 repeated pou/code pipe round-trips.

    Purpose: characterize the named-pipe hang threshold (per-operation fault).
    - If all 20 iterations pass, the fault needs more ops — increase PIPE_STRESS_ITERATIONS.
    - If it hangs at iteration N, the total pipe-op count before failure is ~N+2.
    """
    base_url, _process = real_server
    stop_session(base_url)
    assert_session_started(base_url)

    project_path = str(
        Path(tempfile.gettempdir()) / f"codesys_api_pipe_stress_{uuid.uuid4().hex}.project"
    )

    status_code, payload = call_json(
        base_url,
        "/api/v1/project/create",
        method="POST",
        payload={"path": project_path},
        timeout=120,
    )
    assert status_code == 200, f"project/create failed: {payload}"
    assert payload["success"] is True

    for i in range(PIPE_STRESS_ITERATIONS):
        implementation = f"stress_var_{i} : INT := {i};"
        status_code, payload = call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={"path": "Application/PLC_PRG", "implementation": implementation},
            timeout=30,
        )
        assert status_code == 200, (
            f"pou/code iteration {i} (pipe op ~{i + 3}): "
            f"got {status_code} — {payload}"
        )
        assert payload.get("success") is True, (
            f"pou/code iteration {i} (pipe op ~{i + 3}): {payload}"
        )


@pytest.mark.codesys
def test_pipe_stress_repeated_lifecycles(real_server: tuple[str, subprocess.Popen[str]]) -> None:
    """
    Stress test: 8 full stop→start→pou/code→stop cycles within one HTTP server lifetime.

    Purpose: characterize whether the fault is per-CODESYS-lifecycle, not per-pipe-op.
    The full http-all suite runs 8 tests each with a stop+start cycle; if the fault occurs
    here but not in test_pipe_stress_repeated_roundtrips, the leak is per-lifecycle.

    Each cycle: stop_session (1 pipe op) → start_session (0 ops) →
                project/create (1 op) → pou/code (1 op) → [loop ends]
    Total pipe ops across 8 cycles: 8 × (1 + 1 + 1) = 24 ops from cycle body,
    plus 1 initial start = 25 total.
    """
    base_url, _process = real_server

    # Ensure clean state before starting cycles
    stop_session(base_url)

    for cycle in range(PIPE_STRESS_LIFECYCLE_CYCLES):
        # start_session: launches a new CODESYS process (0 pipe ops — just waits for pipe ready)
        print(f"\n[lifecycle-stress] cycle {cycle}: starting session", flush=True)
        status_code, payload = start_session(base_url)
        assert status_code == 200, f"cycle {cycle}: start_session got {status_code} — {payload}"
        assert payload["success"] is True, f"cycle {cycle}: start_session: {payload}"

        project_path = str(
            Path(tempfile.gettempdir())
            / f"codesys_api_lifecycle_stress_{cycle}_{uuid.uuid4().hex}.project"
        )

        # project/create: 1 pipe op
        status_code, payload = call_json(
            base_url,
            "/api/v1/project/create",
            method="POST",
            payload={"path": project_path},
            timeout=120,
        )
        assert status_code == 200, f"cycle {cycle}: project/create got {status_code} — {payload}"
        assert payload["success"] is True, f"cycle {cycle}: project/create: {payload}"

        # pou/code: 1 pipe op
        implementation = f"lifecycle_var_{cycle} : INT := {cycle};"
        status_code, payload = call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={"path": "Application/PLC_PRG", "implementation": implementation},
            timeout=30,
        )
        assert status_code == 200, f"cycle {cycle}: pou/code got {status_code} — {payload}"
        assert payload.get("success") is True, f"cycle {cycle}: pou/code: {payload}"

        # stop_session: 1 pipe op (graceful shutdown script) + waits for CODESYS to die
        print(f"\n[lifecycle-stress] cycle {cycle}: stopping session", flush=True)
        stop_session(base_url)
        print(f"[lifecycle-stress] cycle {cycle}: stopped OK", flush=True)
