from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from urllib import error, request

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def call_json(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    api_key: str = "admin",
) -> tuple[int, dict[str, Any]]:
    data: bytes | None = None
    headers = {"Authorization": f"ApiKey {api_key}"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed: dict[str, Any]
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"text": body}
        return exc.code, parsed


def wait_for_server(base_url: str) -> None:
    last_error: Exception | None = None
    deadline = time.time() + 10

    while time.time() < deadline:
        try:
            status_code, payload = call_json(base_url, "/api/v1/system/info")
            if status_code == 200 and payload.get("success") is True:
                return
        except Exception as exc:  # pragma: no cover - retry path
            last_error = exc
        time.sleep(0.1)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Mock server did not become ready in time")


@pytest.fixture(scope="module")
def mock_server() -> Generator[str, None, None]:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["TEST_SERVER_HOST"] = "127.0.0.1"
    env["TEST_SERVER_PORT"] = str(port)
    env["TEST_SERVER_SESSION_START_DELAY"] = "0.01"
    env["TEST_SERVER_SCRIPT_EXECUTE_DELAY"] = "0.01"

    process = subprocess.Popen(
        [sys.executable, "scripts/dev/test_server.py"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_for_server(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.mock
def test_mock_server_rejects_invalid_api_key(mock_server: str) -> None:
    status_code, _payload = call_json(
        mock_server,
        "/api/v1/system/info",
        api_key="invalid",
    )

    assert status_code == 401


@pytest.mark.mock
def test_mock_server_system_info(mock_server: str) -> None:
    status_code, payload = call_json(mock_server, "/api/v1/system/info")

    assert status_code == 200
    assert payload["success"] is True
    assert payload["info"]["test_server"] is True


@pytest.mark.mock
def test_mock_server_session_start(mock_server: str) -> None:
    status_code, payload = call_json(
        mock_server,
        "/api/v1/session/start",
        method="POST",
    )

    assert status_code == 200
    assert payload["success"] is True
    assert payload["message"] == "Session started (test server)"


@pytest.mark.mock
def test_mock_server_script_execute(mock_server: str) -> None:
    status_code, payload = call_json(
        mock_server,
        "/api/v1/script/execute",
        method="POST",
        payload={"script": "print('hello')"},
    )

    assert status_code == 200
    assert payload["success"] is True
    assert payload["result"]["script_length"] == len("print('hello')")
