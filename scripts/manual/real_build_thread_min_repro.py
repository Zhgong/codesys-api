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
import real_project_compile_probe as compile_probe


DEFAULT_STEP = "background_build_only_min"
STEP_DESCRIPTIONS = {
    "background_noop": "background script/execute path only; no CODESYS object access",
    "background_resolve_application_only": "resolve session.active_project.active_application only",
    "background_build_only_min": "background-thread minimal app.build() repro",
    "primary_thread_build_only_min": "execute minimal app.build() via system.execute_on_primary_thread(...)",
    "primary_thread_generate_code_only_min": "execute minimal app.generate_code() via system.execute_on_primary_thread(...)",
}


def step_names() -> list[str]:
    return [
        "background_noop",
        "background_resolve_application_only",
        "background_build_only_min",
        "primary_thread_build_only_min",
        "primary_thread_generate_code_only_min",
    ]


def build_background_noop_step() -> str:
    return """
result = {
    "success": True,
    "step": "background_noop",
}
"""


def build_background_resolve_application_only_step() -> str:
    return """
import sys
import traceback

try:
    app = session.active_project.active_application
    result = {
        "success": app is not None,
        "step": "background_resolve_application_only",
        "has_active_application": app is not None,
    }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "background_resolve_application_only",
    }
"""


def build_background_build_only_min_step() -> str:
    return """
import sys
import traceback

try:
    app = session.active_project.active_application
    app.build()
    result = {
        "success": True,
        "step": "background_build_only_min",
    }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "background_build_only_min",
    }
"""


def build_primary_thread_build_only_min_step() -> str:
    return """
import scriptengine
import sys
import traceback

result = {
    "success": False,
    "step": "primary_thread_build_only_min",
}

try:
    system = session.system if hasattr(session, 'system') else None
    if system is None and hasattr(scriptengine, 'system'):
        system = scriptengine.system

    if system is None or not hasattr(system, 'execute_on_primary_thread'):
        result = {
            "success": False,
            "error": "execute_on_primary_thread unavailable",
            "step": "primary_thread_build_only_min",
        }
    else:
        state = {
            "success": False,
            "step": "primary_thread_build_only_min",
        }

        def run_on_primary_thread():
            try:
                app = session.active_project.active_application
                app.build()
                state["success"] = True
            except Exception:
                error_type, error_value, error_traceback = sys.exc_info()
                state["success"] = False
                state["error"] = str(error_value)
                state["traceback"] = traceback.format_exc()

        system.execute_on_primary_thread(run_on_primary_thread, False)
        result = state
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "primary_thread_build_only_min",
    }
"""


def build_primary_thread_generate_code_only_min_step() -> str:
    return """
import scriptengine
import sys
import traceback

result = {
    "success": False,
    "step": "primary_thread_generate_code_only_min",
}

try:
    system = session.system if hasattr(session, 'system') else None
    if system is None and hasattr(scriptengine, 'system'):
        system = scriptengine.system

    if system is None or not hasattr(system, 'execute_on_primary_thread'):
        result = {
            "success": False,
            "error": "execute_on_primary_thread unavailable",
            "step": "primary_thread_generate_code_only_min",
        }
    else:
        state = {
            "success": False,
            "step": "primary_thread_generate_code_only_min",
        }

        def run_on_primary_thread():
            try:
                app = session.active_project.active_application
                app.generate_code()
                state["success"] = True
            except Exception:
                error_type, error_value, error_traceback = sys.exc_info()
                state["success"] = False
                state["error"] = str(error_value)
                state["traceback"] = traceback.format_exc()

        system.execute_on_primary_thread(run_on_primary_thread, False)
        result = state
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "primary_thread_generate_code_only_min",
    }
"""


def build_step_script(step_name: str) -> str:
    if step_name == "background_noop":
        return build_background_noop_step()
    if step_name == "background_resolve_application_only":
        return build_background_resolve_application_only_step()
    if step_name == "background_build_only_min":
        return build_background_build_only_min_step()
    if step_name == "primary_thread_build_only_min":
        return build_primary_thread_build_only_min_step()
    if step_name == "primary_thread_generate_code_only_min":
        return build_primary_thread_generate_code_only_min_step()
    raise ValueError("Unknown step: {0}".format(step_name))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce the CODESYS build threading popup with the smallest "
            "possible script/execute fragments."
        ),
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--step", choices=step_names(), default=DEFAULT_STEP, help="Minimal target step to execute")
    parser.add_argument("--script-timeout", type=int, default=300, help="Timeout seconds for the target script/execute call")
    parser.add_argument("--log-lines", type=int, default=120, help="How many filtered server log lines to print on failure")
    parser.add_argument("--list-steps", action="store_true", help="Print the minimal reproduction steps and exit")
    return parser


def print_reduction_steps() -> None:
    print("Reduction steps:")
    for step_name in step_names():
        print("- {0}: {1}".format(step_name, STEP_DESCRIPTIONS[step_name]))


def print_step_result(name: str, started_at: float, status_code: int, payload: Mapping[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: status={2} success={3}".format(elapsed, name, status_code, payload.get("success")))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def execute_script_step(
    *,
    base_url: str,
    script: str,
    timeout: int,
) -> tuple[int, dict[str, Any]]:
    return common.call_json(
        base_url,
        "/api/v1/script/execute",
        method="POST",
        payload={"script": script},
        timeout=timeout,
    )


def print_timeout(name: str, started_at: float, timeout: int, exc: BaseException) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: timed out after {2}s".format(elapsed, name, timeout))
    print("HTTP timed out; likely blocked by modal UI in CODESYS")
    print("Timeout detail: {0}".format(exc))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_steps:
        print_reduction_steps()
        return 0

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run build thread min repro from sandbox identity '{0}'.".format(identity),
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
    project_path = str(Path(tempfile.gettempdir()) / "codesys_api_build_thread_repro_{0}.project".format(uuid.uuid4().hex))

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        print("Selected step: {0}".format(args.step))
        print("Target project path: {0}".format(project_path))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        started_at = time.perf_counter()
        status_code, payload = common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        print_step_result("session/start", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        started_at = time.perf_counter()
        status_code, payload = execute_script_step(
            base_url=base_url,
            script=compile_probe.build_create_project_with_plc_prg_step(project_path),
            timeout=120,
        )
        print_step_result("create_project_with_plc_prg", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={"path": roundtrip.TARGET_PATH, "implementation": roundtrip.EXPECTED_IMPLEMENTATION},
            timeout=120,
        )
        print_step_result("pou/code", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        started_at = time.perf_counter()
        try:
            status_code, payload = execute_script_step(
                base_url=base_url,
                script=build_step_script(args.step),
                timeout=args.script_timeout,
            )
        except TimeoutError as exc:
            print_timeout(args.step, started_at, args.script_timeout, exc)
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            print("[{0:.2f}s] {1}: request failed".format(elapsed, args.step))
            print("Request detail: {0}".format(exc))
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        print_step_result(args.step, started_at, status_code, payload)
        if status_code == 200 and payload.get("success") is True:
            return 0

        print("Target step failed.")
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
