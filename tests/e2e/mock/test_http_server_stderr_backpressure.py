from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
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
    *,
    timeout: float = 1.0,
    api_key: str = "admin",
) -> tuple[int, dict[str, Any]]:
    req = request.Request(
        f"{base_url}{path}",
        headers={"Authorization": f"ApiKey {api_key}"},
        method="GET",
    )
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


def wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 10.0
    last_error: Exception | None = None

    while time.time() < deadline:
        if process.poll() is not None:
            break
        try:
            status_code, payload = call_json(base_url, "/api/v1/system/info", timeout=0.5)
            if status_code == 200 and payload.get("success") is True:
                return
        except Exception as exc:  # pragma: no cover - retry path
            last_error = exc
        time.sleep(0.05)

    if process.poll() is not None:
        stderr_text = ""
        if process.stderr is not None:
            stderr_text = process.stderr.read()
        raise RuntimeError(
            f"HTTP server exited before ready (code={process.returncode}). stderr:\n{stderr_text}"
        )
    if last_error is not None:
        raise last_error
    raise RuntimeError("HTTP server did not become ready in time")


@pytest.mark.mock
def test_http_server_stays_responsive_with_piped_stderr(tmp_path: Path) -> None:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    appdata_dir = tmp_path / "appdata"
    appdata_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["APPDATA"] = str(appdata_dir)
    env["CODESYS_API_SERVER_HOST"] = "127.0.0.1"
    env["CODESYS_API_SERVER_PORT"] = str(port)
    env["CODESYS_API_TRANSPORT"] = "named_pipe"
    env["CODESYS_API_PIPE_NAME"] = f"codesys_api_mock_{port}"

    process = subprocess.Popen(
        [sys.executable, "HTTP_SERVER.py"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_for_server(base_url, process)
        for i in range(120):
            status_code, payload = call_json(base_url, "/api/v1/system/info", timeout=0.5)
            assert status_code == 200, f"iteration={i} payload={payload}"
            assert payload.get("success") is True, f"iteration={i} payload={payload}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
