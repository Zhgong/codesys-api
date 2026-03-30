from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from codesys_api.runtime_paths import default_runtime_log_dir


LOCAL_ENV_FILE = REPO_ROOT / ".env.real-codesys.local"
REQUIRED_ENV_VARS = (
    "CODESYS_API_CODESYS_PATH",
    "CODESYS_API_CODESYS_PROFILE",
    "CODESYS_API_CODESYS_PROFILE_PATH",
)


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError("Invalid env line without '=': {0}".format(stripped))
        name, value = stripped.split("=", 1)
        env[name] = value
    return env


def resolve_windows_identity() -> str:
    completed = subprocess.run(["whoami"], capture_output=True, text=True, check=False)
    identity = completed.stdout.strip()
    if identity:
        return identity
    userdomain = os.environ.get("USERDOMAIN", "")
    username = os.environ.get("USERNAME", "")
    combined = "{0}\\{1}".format(userdomain, username).strip("\\")
    return combined or "unknown"


def is_sandbox_identity(identity: str) -> bool:
    return "codexsandboxoffline" in identity.lower()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_probe_env(base_env: Mapping[str, str], file_env: Mapping[str, str], port: int) -> dict[str, str]:
    env = dict(base_env)
    for name, value in file_env.items():
        if name == "APPDATA":
            continue
        env[name] = value
    env.setdefault("CODESYS_E2E_NO_UI", "0")
    env["CODESYS_API_SERVER_HOST"] = "127.0.0.1"
    env["CODESYS_API_SERVER_PORT"] = str(port)
    env["CODESYS_API_CODESYS_NO_UI"] = env.get("CODESYS_E2E_NO_UI", "0")
    env["CODESYS_API_TRANSPORT"] = "named_pipe"
    env["CODESYS_API_PIPE_NAME"] = "codesys_api_probe_{0}".format(port)
    return env


def missing_required_env_vars(env: Mapping[str, str]) -> list[str]:
    return [name for name in REQUIRED_ENV_VARS if not env.get(name)]


def call_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    timeout: int = 10,
) -> tuple[int, dict[str, Any]]:
    data: bytes | None = None
    headers = {"Authorization": "ApiKey admin"}
    url = f"{base_url}{path}"

    if payload is not None and method.upper() == "GET":
        query = parse.urlencode(payload)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}" if query else url
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            message = body.strip() or str(exc.reason) or "HTTP error"
            return exc.code, {
                "success": False,
                "error": message,
                "http_status": exc.code,
            }


def wait_for_server(base_url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            status_code, payload = call_json(base_url, "/api/v1/system/info", timeout=5)
            if status_code == 200 and payload.get("success") is True:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Probe server did not become ready in time")


def is_expected_compile_error_response(status_code: int, payload: Mapping[str, object]) -> bool:
    if status_code != 500:
        return False
    if payload.get("success") is not False:
        return False
    counts = payload.get("message_counts")
    if not isinstance(counts, dict):
        return False
    errors = counts.get("errors")
    return isinstance(errors, int) and errors > 0


def parse_log_timestamp(line: str) -> datetime | None:
    prefix = line[:23]
    try:
        return datetime.strptime(prefix, "%Y-%m-%d %H:%M:%S,%f")
    except ValueError:
        return None


def read_log_excerpt(env: Mapping[str, str], *, max_lines: int, started_at: float | None = None) -> str:
    log_file = default_runtime_log_dir(env) / "codesys_api_server.log"
    if not log_file.exists():
        return "<missing log file: {0}>".format(log_file)
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if started_at is not None:
        threshold = datetime.fromtimestamp(started_at)
        filtered_lines = [
            line
            for line in lines
            if (timestamp := parse_log_timestamp(line)) is not None and timestamp >= threshold
        ]
        if filtered_lines:
            return "\n".join(filtered_lines[-max_lines:])
    return "\n".join(lines[-max_lines:])


def print_step(name: str, started_at: float, status_code: int, payload: Mapping[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: status={2} success={3}".format(elapsed, name, status_code, payload.get("success")))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the smallest real HTTP compile-error scenario against local CODESYS.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--compile-timeout", type=int, default=300, help="Timeout seconds for /project/compile")
    parser.add_argument("--log-lines", type=int, default=80, help="How many server log lines to print on failure")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = resolve_windows_identity()
    if is_sandbox_identity(identity):
        print(
            "Refusing to run real compile-error probe from sandbox identity '{0}'.".format(identity),
            file=sys.stderr,
        )
        return 2

    if not LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    file_env = load_env_file(LOCAL_ENV_FILE)
    port = find_free_port()
    probe_env = build_probe_env(os.environ, file_env, port)
    missing = missing_required_env_vars(probe_env)
    if missing:
        print(
            "Missing required real CODESYS environment variables: {0}".format(", ".join(missing)),
            file=sys.stderr,
        )
        return 2

    base_url = "http://127.0.0.1:{0}".format(port)
    probe_started_at = time.time()
    server_process = subprocess.Popen(
        [args.python, "HTTP_SERVER.py"],
        cwd=REPO_ROOT,
        env=probe_env,
    )

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        wait_for_server(base_url)

        try:
            call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_compile_error_probe_{uuid.uuid4().hex}.project")

        started_at = time.perf_counter()
        status_code, payload = call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        print_step("session/start", started_at, status_code, payload)

        started_at = time.perf_counter()
        status_code, payload = call_json(
            base_url,
            "/api/v1/project/create",
            method="POST",
            payload={"path": project_path},
            timeout=120,
        )
        print_step("project/create", started_at, status_code, payload)

        started_at = time.perf_counter()
        status_code, payload = call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={
                "path": "Application/PLC_PRG",
                "implementation": "MissingVar := TRUE;",
            },
            timeout=120,
        )
        print_step("pou/code", started_at, status_code, payload)

        started_at = time.perf_counter()
        try:
            status_code, payload = call_json(
                base_url,
                "/api/v1/project/compile",
                method="POST",
                payload={"clean_build": False},
                timeout=args.compile_timeout,
            )
        except TimeoutError as exc:
            elapsed = time.perf_counter() - started_at
            print("[{0:.2f}s] project/compile timed out: {1}".format(elapsed, str(exc)))
            print("Server log excerpt:")
            print(read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        print_step("project/compile", started_at, status_code, payload)
        print("Compile response JSON:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("Contains MissingVar text: {0}".format("MissingVar" in json.dumps(payload, ensure_ascii=False)))

        if is_expected_compile_error_response(status_code, payload):
            return 0

        print("Unexpected compile response; expected HTTP 500 with nonzero error count.")
        print("Server log excerpt:")
        print(read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
        return 1
    finally:
        try:
            call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass
        if server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
