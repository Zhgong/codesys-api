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
import real_cli_compile_error_probe as cli_probe


CLI_TIMEOUTS = {
    ("session", "start"): 180,
    ("session", "stop"): 60,
    ("project", "create"): 180,
    ("project", "close"): 90,
    ("project", "compile"): 300,
    ("pou", "code"): 180,
}


def payload_contains_missing_var(payload: Mapping[str, object]) -> bool:
    return "MissingVar" in json.dumps(payload, ensure_ascii=False)


def extract_error_count(payload: Mapping[str, object]) -> int | None:
    counts = payload.get("message_counts")
    if not isinstance(counts, dict):
        return None
    errors = counts.get("errors")
    return errors if isinstance(errors, int) else None


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


def run_http_path(base_url: str) -> dict[str, object]:
    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_http_matrix_{uuid.uuid4().hex}.project")
    readback_payload: dict[str, Any] = {}
    compile_payload: dict[str, Any] = {}
    try:
        common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        common.call_json(
            base_url,
            "/api/v1/project/create",
            method="POST",
            payload={"path": project_path},
            timeout=120,
        )
        write_status, write_payload = common.call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={"path": roundtrip.TARGET_PATH, "implementation": roundtrip.EXPECTED_IMPLEMENTATION},
            timeout=120,
        )
        readback_status, readback_payload = common.call_json(
            base_url,
            "/api/v1/script/execute",
            method="POST",
            payload={"script": roundtrip.build_readback_script(roundtrip.TARGET_PATH)},
            timeout=120,
        )
        compile_status, compile_payload = common.call_json(
            base_url,
            "/api/v1/project/compile",
            method="POST",
            payload={"clean_build": False},
            timeout=300,
        )
        return {
            "path": "http",
            "write_success": write_status == 200 and write_payload.get("success") is True,
            "readback_contains_missing_var": readback_status == 200
            and readback_payload.get("implementation_contains_missing_var") is True,
            "compile_status_or_exit_code": compile_status,
            "compile_success": compile_payload.get("success"),
            "compile_error_count": extract_error_count(compile_payload),
            "compile_contains_missing_var": payload_contains_missing_var(compile_payload),
        }
    finally:
        try:
            common.call_json(base_url, "/api/v1/project/close", method="POST", payload={}, timeout=60)
        except Exception:
            pass
        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=60)
        except Exception:
            pass


def run_cli_path(base_url: str, cli_env: Mapping[str, str]) -> dict[str, object]:
    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_cli_matrix_{uuid.uuid4().hex}.project")
    implementation_file = Path(tempfile.gettempdir()) / f"codesys_api_cli_matrix_{uuid.uuid4().hex}.txt"
    implementation_file.write_text(roundtrip.EXPECTED_IMPLEMENTATION, encoding="utf-8")
    readback_payload: dict[str, Any] = {}
    compile_payload: dict[str, Any] = {}
    try:
        run_cli_json(cli_env, "session", "start")
        run_cli_json(cli_env, "project", "create", "--path", project_path)
        write_exit_code, write_payload, write_stderr = run_cli_json(
            cli_env,
            "pou",
            "code",
            "--path",
            roundtrip.TARGET_PATH,
            "--implementation-file",
            str(implementation_file),
        )
        readback_status, readback_payload = common.call_json(
            base_url,
            "/api/v1/script/execute",
            method="POST",
            payload={"script": roundtrip.build_readback_script(roundtrip.TARGET_PATH)},
            timeout=120,
        )
        compile_exit_code, compile_payload, compile_stderr = run_cli_json(cli_env, "project", "compile")
        return {
            "path": "cli",
            "write_success": write_exit_code == 0
            and write_payload.get("success") is True
            and cli_probe.is_benign_cli_stderr(write_stderr),
            "readback_contains_missing_var": readback_status == 200
            and readback_payload.get("implementation_contains_missing_var") is True,
            "compile_status_or_exit_code": compile_exit_code,
            "compile_success": compile_payload.get("success"),
            "compile_error_count": extract_error_count(compile_payload),
            "compile_contains_missing_var": payload_contains_missing_var(compile_payload),
            "compile_stderr": compile_stderr,
        }
    finally:
        try:
            run_cli_json(cli_env, "project", "close")
        except Exception:
            pass
        try:
            run_cli_json(cli_env, "session", "stop")
        except Exception:
            pass
        if implementation_file.exists():
            implementation_file.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare HTTP and CLI real compile-error behavior against the same PLC_PRG mutation.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--log-lines", type=int, default=80, help="How many filtered server log lines to print")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run real compile-error matrix from sandbox identity '{0}'.".format(identity),
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
        print("Pipe: {0}".format(probe_env["CODESYS_API_PIPE_NAME"]))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        http_summary = run_http_path(base_url)
        cli_summary = run_cli_path(base_url, probe_env)
        print("HTTP path summary:")
        print(json.dumps(http_summary, indent=2, ensure_ascii=False))
        print("CLI path summary:")
        print(json.dumps(cli_summary, indent=2, ensure_ascii=False))

        if (
            http_summary["readback_contains_missing_var"] is True
            and cli_summary["readback_contains_missing_var"] is True
            and http_summary["compile_success"] is False
            and cli_summary["compile_success"] is False
        ):
            return 0

        print("Unexpected matrix outcome; at least one path did not produce the expected compile error.")
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
