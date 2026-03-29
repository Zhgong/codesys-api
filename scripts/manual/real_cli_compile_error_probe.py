from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common
import real_pou_code_roundtrip_probe as roundtrip
import real_syntax_compile_error_probe as syntax_probe


CLI_TIMEOUTS = {
    ("session", "start"): 180,
    ("session", "stop"): 60,
    ("project", "create"): 180,
    ("project", "close"): 90,
    ("project", "compile"): 300,
    ("pou", "code"): 180,
}

PROJECT_CREATE_RETRYABLE_ERRORS = syntax_probe.PROJECT_CREATE_RETRYABLE_ERRORS
PROJECT_CREATE_RETRY_ATTEMPTS = syntax_probe.PROJECT_CREATE_RETRY_ATTEMPTS


def run_cli_json(env: Mapping[str, str], *args: str) -> tuple[int, dict[str, Any], str]:
    timeout = CLI_TIMEOUTS.get((args[0], args[1]), 120)
    completed = subprocess.run(
        [sys.executable, "codesys_cli.py", "--json", *args],
        cwd=common.REPO_ROOT,
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    stdout = completed.stdout.strip()
    payload = json.loads(stdout) if stdout else {}
    return completed.returncode, payload, completed.stderr.strip()


def is_benign_cli_stderr(stderr: str) -> bool:
    if not stderr:
        return True
    return stderr.strip() == "CODESYS not running, attempting to start it"


def is_expected_compile_error_stderr(stderr: str) -> bool:
    """Accept stderr that matches expected CLI compile-error business-failure output."""
    if not stderr:
        return True
    lowered = stderr.lower()
    return "error" in lowered or "compilation" in lowered


def is_retryable_cli_project_create_error(exit_code: int, payload: Mapping[str, object]) -> bool:
    if exit_code != 1:
        return False
    error = payload.get("error")
    if not isinstance(error, str):
        return False
    lowered = error.lower()
    return any(marker.lower() in lowered for marker in PROJECT_CREATE_RETRYABLE_ERRORS)


def create_project_with_retry(
    *,
    env: Mapping[str, str],
    base_url: str,
    project_path: str,
) -> tuple[int, dict[str, Any], str, int]:
    last_exit_code = 1
    last_payload: dict[str, Any] = {"success": False, "error": "project/create not attempted"}
    last_stderr = ""

    for attempt in range(1, PROJECT_CREATE_RETRY_ATTEMPTS + 1):
        exit_code, payload, stderr = run_cli_json(env, "project", "create", "--path", project_path)
        last_exit_code = exit_code
        last_payload = payload
        last_stderr = stderr
        if not is_retryable_cli_project_create_error(exit_code, payload):
            return exit_code, payload, stderr, attempt
        if attempt < PROJECT_CREATE_RETRY_ATTEMPTS:
            syntax_probe.recover_after_project_create_failure(
                base_url=base_url,
                call_json=common.call_json,
            )

    return last_exit_code, last_payload, last_stderr, PROJECT_CREATE_RETRY_ATTEMPTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the real CLI compile-error scenario without failing on benign startup stderr.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--log-lines", type=int, default=80, help="How many filtered server log lines to print")
    return parser


def print_cli_step(name: str, started_at: float, exit_code: int, payload: Mapping[str, object], stderr: str) -> None:
    elapsed = time.perf_counter() - started_at
    print(
        "[{0:.2f}s] {1}: exit_code={2} success={3} stderr={4}".format(
            elapsed,
            name,
            exit_code,
            payload.get("success"),
            repr(stderr),
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run real CLI compile-error probe from sandbox identity '{0}'.".format(identity),
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

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_cli_probe_{uuid.uuid4().hex}.project")
        implementation_file = Path(tempfile.gettempdir()) / f"codesys_api_cli_probe_{uuid.uuid4().hex}.txt"
        implementation_file.write_text(roundtrip.EXPECTED_IMPLEMENTATION, encoding="utf-8")

        try:
            started_at = time.perf_counter()
            exit_code, session_payload, session_stderr = run_cli_json(probe_env, "session", "start")
            print_cli_step("cli session/start", started_at, exit_code, session_payload, session_stderr)

            started_at = time.perf_counter()
            exit_code, create_payload, create_stderr, create_attempts = create_project_with_retry(
                env=probe_env,
                base_url=base_url,
                project_path=project_path,
            )
            print_cli_step("cli project/create", started_at, exit_code, create_payload, create_stderr)
            if create_attempts > 1:
                print("cli project/create attempts: {0}".format(create_attempts))

            started_at = time.perf_counter()
            exit_code, pou_code_payload, pou_code_stderr = run_cli_json(
                probe_env,
                "pou",
                "code",
                "--path",
                roundtrip.TARGET_PATH,
                "--implementation-file",
                str(implementation_file),
            )
            print_cli_step("cli pou/code", started_at, exit_code, pou_code_payload, pou_code_stderr)

            started_at = time.perf_counter()
            readback_status, readback_payload = common.call_json(
                base_url,
                "/api/v1/script/execute",
                method="POST",
                payload={"script": roundtrip.build_readback_script(roundtrip.TARGET_PATH)},
                timeout=120,
            )
            common.print_step("http script/execute", started_at, readback_status, readback_payload)
            print("CLI readback JSON:")
            print(json.dumps(readback_payload, indent=2, ensure_ascii=False))

            started_at = time.perf_counter()
            exit_code, compile_payload, compile_stderr = run_cli_json(probe_env, "project", "compile")
            print_cli_step("cli project/compile", started_at, exit_code, compile_payload, compile_stderr)
            print("CLI compile JSON:")
            print(json.dumps(compile_payload, indent=2, ensure_ascii=False))

            stderr_ok = (
                is_benign_cli_stderr(session_stderr)
                and create_stderr == ""
                and pou_code_stderr == ""
                and is_expected_compile_error_stderr(compile_stderr)
            )
            readback_ok = readback_status == 200 and readback_payload.get("implementation_contains_missing_var") is True
            compile_failed = exit_code == 1 and compile_payload.get("success") is False
            compile_has_errors = isinstance(compile_payload.get("message_counts"), dict) and compile_payload["message_counts"].get("errors", 0) > 0

            if readback_ok and compile_failed and compile_has_errors and stderr_ok:
                return 0

            print("Unexpected CLI compile-error outcome.")
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1
        finally:
            try:
                run_cli_json(probe_env, "project", "close")
            except Exception:
                pass
            try:
                run_cli_json(probe_env, "session", "stop")
            except Exception:
                pass
            if implementation_file.exists():
                implementation_file.unlink()
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
