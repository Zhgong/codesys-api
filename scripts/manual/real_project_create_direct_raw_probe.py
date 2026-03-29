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


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common
from real_project_create_raw_probe import escape_script_string


def build_create_project_only_step(project_path: str) -> str:
    escaped_project_path = escape_script_string(project_path)
    return """
import scriptengine
import json
import sys
import traceback

try:
    target_path = "{0}"
    if hasattr(session, 'active_project') and session.active_project is not None:
        try:
            if hasattr(session.active_project, 'close'):
                session.active_project.close()
        except Exception:
            pass
        session.active_project = None

    project = scriptengine.projects.create(target_path, True)
    if project is None:
        result = {{"success": False, "error": "projects.create returned None", "step": "create_project_only"}}
    else:
        session.active_project = project
        if not hasattr(session, 'created_pous'):
            session.created_pous = {{}}
        top_level_names = []
        if hasattr(project, 'get_children'):
            for child in project.get_children():
                try:
                    if hasattr(child, 'get_name'):
                        top_level_names.append(str(child.get_name(False)))
                    else:
                        top_level_names.append(str(child))
                except Exception:
                    pass
        active_application_name = ""
        has_active_application = False
        if hasattr(project, 'active_application') and project.active_application is not None:
            has_active_application = True
            if hasattr(project.active_application, 'get_name'):
                active_application_name = str(project.active_application.get_name(False))
            else:
                active_application_name = str(project.active_application)
        result = {{
            "success": True,
            "step": "create_project_only",
            "requested_project_path": target_path,
            "actual_project_path": project.path if hasattr(project, 'path') else target_path,
            "project_name": project.name if hasattr(project, 'name') else "",
            "top_level_names": top_level_names,
            "has_active_application": has_active_application,
            "active_application_name": active_application_name,
        }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_project_only",
    }}
""".format(escaped_project_path)


def build_inspect_project_structure_step(expected_project_path: str) -> str:
    escaped_project_path = escape_script_string(expected_project_path)
    return """
import json
import os
import sys
import traceback

try:
    expected_project_path = "{0}"
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session", "step": "inspect_project_structure"}}
    else:
        project = session.active_project
        actual_project_path = project.path if hasattr(project, 'path') else ""
        top_level_names = []
        device_names = []
        application_names = []
        all_object_names = []
        if hasattr(project, 'get_children'):
            for child in project.get_children():
                try:
                    child_name = str(child.get_name(False)) if hasattr(child, 'get_name') else str(child)
                    top_level_names.append(child_name)
                    if hasattr(child, 'is_device') and child.is_device:
                        device_names.append(child_name)
                except Exception:
                    pass
            for obj in project.get_children(True):
                try:
                    obj_name = str(obj.get_name(False)) if hasattr(obj, 'get_name') else str(obj)
                    all_object_names.append(obj_name)
                    if hasattr(obj, 'is_application') and obj.is_application:
                        application_names.append(obj_name)
                except Exception:
                    pass
        active_application_name = ""
        has_active_application = False
        if hasattr(project, 'active_application') and project.active_application is not None:
            has_active_application = True
            if hasattr(project.active_application, 'get_name'):
                active_application_name = str(project.active_application.get_name(False))
            else:
                active_application_name = str(project.active_application)
        result = {{
            "success": actual_project_path == expected_project_path,
            "step": "inspect_project_structure",
            "expected_project_path": expected_project_path,
            "actual_project_path": actual_project_path,
            "top_level_names": top_level_names,
            "device_names": device_names,
            "application_names": application_names,
            "all_object_names": all_object_names,
            "has_active_application": has_active_application,
            "active_application_name": active_application_name,
        }}
        if actual_project_path != expected_project_path:
            result["error"] = "Active project path does not match requested project"
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "inspect_project_structure",
    }}
""".format(escaped_project_path)


def build_steps(project_path: str) -> list[tuple[str, str]]:
    return [
        ("create_project_only", build_create_project_only_step(project_path)),
        ("inspect_project_structure", build_inspect_project_structure_step(project_path)),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debug direct scriptengine.projects.create(...) against local CODESYS.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--log-lines", type=int, default=120, help="How many filtered server log lines to print on failure")
    return parser


def print_step_payload(step_name: str, started_at: float, status_code: int, payload: dict[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: status={2} success={3}".format(elapsed, step_name, status_code, payload.get("success")))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run raw direct project/create probe from sandbox identity '{0}'.".format(identity),
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

    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_direct_create_probe_{uuid.uuid4().hex}.project")

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
        status_code, payload = common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        common.print_step("session/start", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("session/start failed; stopping.")
            return 1

        for step_name, script in build_steps(project_path):
            started_at = time.perf_counter()
            status_code, payload = common.call_json(
                base_url,
                "/api/v1/script/execute",
                method="POST",
                payload={"script": script},
                timeout=120,
            )
            print_step_payload(step_name, started_at, status_code, payload)
            if not (status_code == 200 and payload.get("success") is True):
                print("Raw direct project/create probe stopped at step: {0}".format(step_name))
                print("Server log excerpt:")
                print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
                return 1

        print("Raw direct project/create probe completed successfully.")
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
