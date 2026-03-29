from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common
import real_pou_code_roundtrip_probe as roundtrip


TARGET_PATH = "Application/PLC_PRG"
SYNTAX_ERROR_IMPLEMENTATION = "IF TRUE THEN\n    x := 1;\n"
PROJECT_CREATE_RETRYABLE_ERRORS = (
    "Controls created on one thread cannot be parented to a control on a different thread.",
    "A primary project is already open at",
)
PROJECT_CREATE_RETRY_ATTEMPTS = 2
PROJECT_CREATE_RETRY_DELAY_SECONDS = 2.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a project with a hard PLC_PRG syntax error and keep the .project for manual IDE verification.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--compile-timeout", type=int, default=300, help="Timeout seconds for /project/compile")
    parser.add_argument("--log-lines", type=int, default=80, help="How many filtered server log lines to print")
    return parser


def print_manual_follow_up(project_path: str) -> None:
    print("Project path for manual IDE verification: {0}".format(project_path))
    print("Syntax-error implementation written to Application/PLC_PRG:")
    print(SYNTAX_ERROR_IMPLEMENTATION)
    print("Manual IDE verification:")
    print("1. Open the project path above in CODESYS IDE.")
    print("2. Compile/build the project manually.")
    print("3. Confirm whether the IDE shows a syntax error for PLC_PRG.")


def is_retryable_project_create_error(status_code: int, payload: dict[str, Any]) -> bool:
    if status_code != 500:
        return False
    error = payload.get("error")
    if not isinstance(error, str):
        return False
    lowered = error.lower()
    return any(marker.lower() in lowered for marker in PROJECT_CREATE_RETRYABLE_ERRORS)


def recover_after_project_create_failure(
    *,
    base_url: str,
    call_json: Callable[..., tuple[int, dict[str, Any]]],
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    try:
        call_json(base_url, "/api/v1/project/close", method="POST", payload={}, timeout=60)
    except Exception:
        pass
    try:
        call_json(base_url, "/api/v1/session/restart", method="POST", payload={}, timeout=180)
    except Exception:
        pass
    sleep_fn(PROJECT_CREATE_RETRY_DELAY_SECONDS)


def active_project_matches(
    *,
    base_url: str,
    expected_project_path: str,
    call_json: Callable[..., tuple[int, dict[str, Any]]],
) -> tuple[bool, int, dict[str, Any]]:
    status_code, payload = call_json(base_url, "/api/v1/session/status", method="GET", timeout=60)
    if status_code != 200 or payload.get("success") is not True:
        return False, status_code, payload
    status = payload.get("status")
    if not isinstance(status, dict):
        return False, status_code, payload
    session = status.get("session")
    if not isinstance(session, dict):
        return False, status_code, payload
    project = session.get("project")
    if not isinstance(project, dict):
        return False, status_code, payload
    actual_path = project.get("path")
    return actual_path == expected_project_path, status_code, payload


def create_project_with_retry(
    *,
    base_url: str,
    project_path: str,
    timeout: int,
    call_json: Callable[..., tuple[int, dict[str, Any]]],
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[int, dict[str, Any], int]:
    last_status_code = 500
    last_payload: dict[str, Any] = {"success": False, "error": "project/create not attempted"}

    for attempt in range(1, PROJECT_CREATE_RETRY_ATTEMPTS + 1):
        status_code, payload = call_json(
            base_url,
            "/api/v1/project/create",
            method="POST",
            payload={"path": project_path},
            timeout=timeout,
        )
        last_status_code = status_code
        last_payload = payload
        if not is_retryable_project_create_error(status_code, payload):
            return status_code, payload, attempt
        if attempt < PROJECT_CREATE_RETRY_ATTEMPTS:
            recover_after_project_create_failure(
                base_url=base_url,
                call_json=call_json,
                sleep_fn=sleep_fn,
            )

    return last_status_code, last_payload, PROJECT_CREATE_RETRY_ATTEMPTS


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run real syntax compile-error probe from sandbox identity '{0}'.".format(identity),
            file=sys.stderr,
        )
        return 2

    if not common.LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(common.LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    file_env = common.load_env_file(common.LOCAL_ENV_FILE)
    port = common.find_free_port()
    probe_env = common.build_probe_env(os.environ, file_env, port)
    missing = common.missing_required_env_vars(probe_env)
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
        cwd=common.REPO_ROOT,
        env=probe_env,
    )

    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_syntax_error_probe_{uuid.uuid4().hex}.project")

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        started_at = time.perf_counter()
        status_code, payload = common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        common.print_step("session/start", started_at, status_code, payload)

        started_at = time.perf_counter()
        status_code, payload, create_attempts = create_project_with_retry(
            base_url=base_url,
            project_path=project_path,
            timeout=120,
            call_json=common.call_json,
        )
        common.print_step("project/create", started_at, status_code, payload)
        if create_attempts > 1:
            print("project/create attempts: {0}".format(create_attempts))
        if not (status_code == 200 and payload.get("success") is True):
            print("project/create did not succeed; stopping before pou/code.")
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        started_at = time.perf_counter()
        active_project_ok, status_code, payload = active_project_matches(
            base_url=base_url,
            expected_project_path=project_path,
            call_json=common.call_json,
        )
        common.print_step("session/status", started_at, status_code, payload)
        if not active_project_ok:
            print("project/create did not leave the requested project as the active session project.")
            print("Session status JSON:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={"path": TARGET_PATH, "implementation": SYNTAX_ERROR_IMPLEMENTATION},
            timeout=120,
        )
        common.print_step("pou/code", started_at, status_code, payload)

        started_at = time.perf_counter()
        readback_status, readback_payload = common.call_json(
            base_url,
            "/api/v1/script/execute",
            method="POST",
            payload={"script": roundtrip.build_readback_script(TARGET_PATH)},
            timeout=120,
        )
        common.print_step("script/execute", started_at, readback_status, readback_payload)
        print("Readback JSON:")
        print(json.dumps(readback_payload, indent=2, ensure_ascii=False))

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/project/save",
            method="POST",
            payload={},
            timeout=120,
        )
        common.print_step("project/save", started_at, status_code, payload)

        started_at = time.perf_counter()
        try:
            status_code, payload = common.call_json(
                base_url,
                "/api/v1/project/compile",
                method="POST",
                payload={"clean_build": False},
                timeout=args.compile_timeout,
            )
        except TimeoutError as exc:
            elapsed = time.perf_counter() - started_at
            print("[{0:.2f}s] project/compile timed out: {1}".format(elapsed, str(exc)))
            print_manual_follow_up(project_path)
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        common.print_step("project/compile", started_at, status_code, payload)
        print("Compile response JSON:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print_manual_follow_up(project_path)

        readback_ok = readback_status == 200 and readback_payload.get("implementation_contains_missing_var") is False
        syntax_error_text_present = SYNTAX_ERROR_IMPLEMENTATION.strip() in str(readback_payload.get("implementation_preview", ""))

        if readback_ok and syntax_error_text_present and common.is_expected_compile_error_response(status_code, payload):
            return 0

        print("Unexpected syntax compile-error outcome.")
        print("Server log excerpt:")
        print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
        return 1
    finally:
        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
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
