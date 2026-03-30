from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common
from real_project_create_raw_probe import escape_script_string


DEFAULT_DEVICE_NAME = "CODESYS Control Win V3 x64"
DEFAULT_DEVICE_TYPE = 4096
DEFAULT_DEVICE_ID = "0000 0004"
DEFAULT_DEVICE_VERSION = "3.5.20.50"
DEFAULT_POU_NAME = "PLC_PRG"
DEFAULT_TASK_NAME = "MainTask"
SYNTAX_ERROR_CODE = "MissingVar := TRUE;"


# ---------------------------------------------------------------------------
# Step builders
# ---------------------------------------------------------------------------


def build_create_project_with_plc_prg_step(
    project_path: str,
    device_name: str = DEFAULT_DEVICE_NAME,
    device_type: int = DEFAULT_DEVICE_TYPE,
    device_id: str = DEFAULT_DEVICE_ID,
    device_version: str = DEFAULT_DEVICE_VERSION,
    pou_name: str = DEFAULT_POU_NAME,
    task_name: str = DEFAULT_TASK_NAME,
) -> str:
    """Full proven skeleton in one script/execute call."""
    return """
import scriptengine
import sys
import traceback

try:
    if hasattr(session, 'active_project') and session.active_project is not None:
        try:
            session.active_project.close()
        except Exception:
            pass
        session.active_project = None

    project = scriptengine.projects.create("{project_path}", True)
    if project is None:
        raise Exception("projects.create returned None")

    project.add("{device_name}", {device_type}, "{device_id}", "{device_version}")

    app = project.active_application
    if app is None:
        raise Exception("No active application after add_device")

    existing_program = app.create_pou(name="{pou_name}", type=scriptengine.PouType.Program, language=scriptengine.ImplementationLanguages.st)
    task_config = app.create_task_configuration()
    existing_task = task_config.create_task("{task_name}")
    existing_task.pous.add("{pou_name}")

    session.active_project = project
    if not hasattr(session, 'created_pous'):
        session.created_pous = {{}}
    session.created_pous["{pou_name}"] = existing_program

    result = {{
        "success": True,
        "step": "create_project_with_plc_prg",
        "project_path": project.path if hasattr(project, 'path') else "",
        "has_active_application": project.active_application is not None,
        "pou_created": existing_program is not None,
    }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_project_with_plc_prg",
    }}
""".format(
        project_path=escape_script_string(project_path),
        device_name=escape_script_string(device_name),
        device_type=device_type,
        device_id=escape_script_string(device_id),
        device_version=escape_script_string(device_version),
        pou_name=escape_script_string(pou_name),
        task_name=escape_script_string(task_name),
    )


def build_build_step() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "build"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "build"}
    else:
        application = session.active_project.active_application
        print("Calling application.build()...")
        application.build()
        print("application.build() returned")
        result = {"success": True, "step": "build"}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "build",
    }
"""


def build_generate_code_step() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "generate_code"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "generate_code"}
    else:
        application = session.active_project.active_application
        print("Calling application.generate_code()...")
        application.generate_code()
        print("application.generate_code() returned")
        result = {"success": True, "step": "generate_code"}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "generate_code",
    }
"""


def build_steps(
    project_path: str,
    device_name: str = DEFAULT_DEVICE_NAME,
    device_type: int = DEFAULT_DEVICE_TYPE,
    device_id: str = DEFAULT_DEVICE_ID,
    device_version: str = DEFAULT_DEVICE_VERSION,
) -> list[tuple[str, str]]:
    return [
        (
            "create_project_with_plc_prg",
            build_create_project_with_plc_prg_step(
                project_path,
                device_name=device_name,
                device_type=device_type,
                device_id=device_id,
                device_version=device_version,
            ),
        ),
        ("build", build_build_step()),
        ("generate_code", build_generate_code_step()),
    ]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe application.build() and application.generate_code() "
            "directly via script/execute against real CODESYS."
        ),
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--log-lines", type=int, default=120)
    parser.add_argument("--script-timeout", type=int, default=120,
                        help="Timeout seconds for each script/execute call")
    parser.add_argument("--device-name", default=DEFAULT_DEVICE_NAME)
    parser.add_argument("--device-type", type=int, default=DEFAULT_DEVICE_TYPE)
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--device-version", default=DEFAULT_DEVICE_VERSION)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    import json as _json

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run compile probe from sandbox identity '{0}'.".format(identity),
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

    project_path = str(
        Path(tempfile.gettempdir())
        / "codesys_api_compile_probe_{0}.project".format(uuid.uuid4().hex)
    )

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        print("Target project path: {0}".format(project_path))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120
        )
        common.print_step("session/start", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("session/start failed; stopping.")
            return 1

        # --- Step 1: create project skeleton via script/execute ---
        step_name = "create_project_with_plc_prg"
        script = build_create_project_with_plc_prg_step(
            project_path,
            device_name=args.device_name,
            device_type=args.device_type,
            device_id=args.device_id,
            device_version=args.device_version,
        )
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/script/execute", method="POST",
            payload={"script": script}, timeout=args.script_timeout,
        )
        elapsed = time.perf_counter() - started_at
        print("[{0:.2f}s] {1}: status={2} success={3}".format(
            elapsed, step_name, status_code, payload.get("success")))
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
        if not (status_code == 200 and payload.get("success") is True):
            print("Compile probe stopped at step: {0}".format(step_name))
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        # --- Step 2: write syntax error to PLC_PRG via pou/code ---
        step_name = "write_syntax_error"
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/pou/code", method="POST",
            payload={"path": "Application/PLC_PRG", "implementation": SYNTAX_ERROR_CODE},
            timeout=60,
        )
        elapsed = time.perf_counter() - started_at
        print("[{0:.2f}s] {1}: status={2} success={3}".format(
            elapsed, step_name, status_code, payload.get("success")))
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
        if not (status_code == 200 and payload.get("success") is True):
            print("Compile probe stopped at step: {0}".format(step_name))
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        # --- Steps 3 & 4: build + generate_code via script/execute ---
        for step_name, script in [("build", build_build_step()), ("generate_code", build_generate_code_step())]:
            started_at = time.perf_counter()
            status_code, payload = common.call_json(
                base_url, "/api/v1/script/execute", method="POST",
                payload={"script": script}, timeout=args.script_timeout,
            )
            elapsed = time.perf_counter() - started_at
            print("[{0:.2f}s] {1}: status={2} success={3}".format(
                elapsed, step_name, status_code, payload.get("success")))
            print(_json.dumps(payload, indent=2, ensure_ascii=False))
            if not (status_code == 200 and payload.get("success") is True):
                print("Compile probe stopped at step: {0}".format(step_name))
                print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
                return 1

        print("Compile probe completed — all steps passed.")
        return 0
    finally:
        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass
        if server_process.poll() is None:
            try:
                server_process.terminate()
                server_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
