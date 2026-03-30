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


DESIRED_DEVICE_NAME = "CODESYS Control Win V3 x64"
DESIRED_DEVICE_TYPE = 4096
DESIRED_DEVICE_ID = "0000 0004"
DESIRED_DEVICE_VERSION = "3.5.20.50"
DESIRED_PROGRAM_NAME = "PLC_PRG"
DESIRED_TASK_NAME = "MainTask"


def escape_script_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def derive_template_path(codesys_path: str) -> str:
    codesys_dir = os.path.dirname(codesys_path)
    if "Common" in codesys_dir:
        codesys_dir = os.path.dirname(codesys_dir)
    return os.path.join(codesys_dir, "Templates", "Standard.project")


def build_open_template_step(project_path: str, template_path: str) -> str:
    escaped_project_path = escape_script_string(project_path)
    escaped_template_path = escape_script_string(template_path)
    return """
import scriptengine
import json
import os
import sys
import traceback

try:
    target_path = "{0}"
    template_path = "{1}"
    if hasattr(session, 'active_project') and session.active_project is not None:
        try:
            if hasattr(session.active_project, 'close'):
                session.active_project.close()
        except Exception:
            pass
        session.active_project = None

    project = scriptengine.projects.open(template_path)
    if project is None:
        result = {{"success": False, "error": "Failed to open template", "step": "open_template"}}
    elif not hasattr(project, 'save_as'):
        result = {{"success": False, "error": "Project has no save_as method", "step": "open_template"}}
    else:
        project.save_as(target_path)
        session.active_project = project
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
        result = {{
            "success": True,
            "step": "open_template",
            "project_path": project.path if hasattr(project, 'path') else target_path,
            "top_level_names": top_level_names,
        }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "open_template",
    }}
""".format(escaped_project_path, escaped_template_path)


def build_replace_device_step() -> str:
    return """
import scriptengine
import json
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session", "step": "replace_device"}
    else:
        project = session.active_project
        desired_device_name = "%s"
        desired_device_type = %d
        desired_device_id = "%s"
        desired_device_version = "%s"
        existing_devices = []
        desired_device_found = False
        if hasattr(project, 'get_children'):
            for child in project.get_children():
                try:
                    if hasattr(child, 'is_device') and child.is_device:
                        child_name = child.get_name(False) if hasattr(child, 'get_name') else str(child)
                        existing_devices.append(str(child_name))
                        if str(child_name) == desired_device_name:
                            desired_device_found = True
                except Exception:
                    pass
        removed_devices = []
        if not desired_device_found:
            if hasattr(project, 'get_children'):
                for child in project.get_children():
                    try:
                        if hasattr(child, 'is_device') and child.is_device and hasattr(child, 'remove'):
                            child_name = child.get_name(False) if hasattr(child, 'get_name') else str(child)
                            removed_devices.append(str(child_name))
                            child.remove()
                    except Exception:
                        pass
            if hasattr(project, 'add'):
                project.add(desired_device_name, desired_device_type, desired_device_id, desired_device_version)
            else:
                raise Exception("Project object does not support adding devices")
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
        result = {
            "success": True,
            "step": "replace_device",
            "desired_device_found_before": desired_device_found,
            "existing_devices_before": existing_devices,
            "removed_devices": removed_devices,
            "top_level_names_after": top_level_names,
        }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "replace_device",
    }
""" % (
        DESIRED_DEVICE_NAME,
        DESIRED_DEVICE_TYPE,
        DESIRED_DEVICE_ID,
        DESIRED_DEVICE_VERSION,
    )


def build_resolve_application_step() -> str:
    return """
import json
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session", "step": "resolve_application"}
    else:
        project = session.active_project
        desired_device_name = "%s"
        desired_application = None
        application_candidates = []
        if hasattr(project, 'get_children'):
            for obj in project.get_children(True):
                try:
                    if hasattr(obj, 'is_application') and obj.is_application:
                        parent_name = ""
                        if hasattr(obj, 'parent') and obj.parent is not None and hasattr(obj.parent, 'get_name'):
                            parent_name = str(obj.parent.get_name(False))
                        application_candidates.append(parent_name)
                        if parent_name == desired_device_name or desired_application is None:
                            desired_application = obj
                except Exception:
                    pass
        if desired_application is None:
            result = {
                "success": False,
                "error": "No application found under desired device",
                "step": "resolve_application",
                "application_candidates": application_candidates,
            }
        else:
            if hasattr(project, 'active_application'):
                project.active_application = desired_application
            result = {
                "success": True,
                "step": "resolve_application",
                "application_name": str(desired_application.get_name(False)) if hasattr(desired_application, 'get_name') else str(desired_application),
                "application_candidates": application_candidates,
            }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "resolve_application",
    }
""" % DESIRED_DEVICE_NAME


def build_create_program_step() -> str:
    return """
import scriptengine
import json
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session", "step": "create_program"}
    else:
        project = session.active_project
        if not hasattr(project, 'active_application') or project.active_application is None:
            result = {"success": False, "error": "Project has no active application", "step": "create_program"}
        else:
            app = project.active_application
            desired_program_name = "%s"
            existing_program = None
            children = []
            if hasattr(app, 'get_children'):
                try:
                    children = app.get_children(True)
                except Exception:
                    children = []
            for child in children:
                try:
                    child_name = child.get_name(False) if hasattr(child, 'get_name') else ""
                    if str(child_name) == desired_program_name:
                        existing_program = child
                        break
                except Exception:
                    pass
            created = False
            if existing_program is None:
                created = True
                if hasattr(app, 'create_pou'):
                    existing_program = app.create_pou(
                        name=desired_program_name,
                        type=scriptengine.PouType.Program,
                        language=scriptengine.ImplementationLanguages.st
                    )
                elif hasattr(app, 'pou_container'):
                    existing_program = app.pou_container.create_pou(
                        name=desired_program_name,
                        type=scriptengine.PouType.Program,
                        language=scriptengine.ImplementationLanguages.st
                    )
                else:
                    raise Exception("Application does not support creating PLC_PRG")
            if not hasattr(session, 'created_pous'):
                session.created_pous = {}
            session.created_pous[desired_program_name] = existing_program
            result = {
                "success": True,
                "step": "create_program",
                "created": created,
                "program_name": desired_program_name,
            }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_program",
    }
""" % DESIRED_PROGRAM_NAME


def build_create_task_step() -> str:
    return """
import scriptengine
import json
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session", "step": "create_task"}
    else:
        project = session.active_project
        if not hasattr(project, 'active_application') or project.active_application is None:
            result = {"success": False, "error": "Project has no active application", "step": "create_task"}
        else:
            app = project.active_application
            desired_program_name = "%s"
            desired_task_name = "%s"
            task_config = None
            existing_task = None
            children = []
            if hasattr(app, 'get_children'):
                try:
                    children = app.get_children(True)
                except Exception:
                    children = []
            for child in children:
                try:
                    child_name = child.get_name(False) if hasattr(child, 'get_name') else ""
                    if hasattr(child, 'is_task_configuration') and child.is_task_configuration:
                        task_config = child
                    if hasattr(child, 'is_task') and child.is_task and str(child_name) == desired_task_name:
                        existing_task = child
                except Exception:
                    pass
            task_config_created = False
            task_created = False
            if task_config is None:
                task_config_created = True
                if hasattr(app, 'create_task_configuration'):
                    task_config = app.create_task_configuration()
                else:
                    raise Exception("Application does not support creating task configuration")
            if existing_task is None:
                task_created = True
                if hasattr(task_config, 'create_task'):
                    existing_task = task_config.create_task(desired_task_name)
                else:
                    raise Exception("Task configuration object does not support creating tasks")
            if hasattr(existing_task, 'pous'):
                task_pous = existing_task.pous
                task_has_program = False
                for task_pou in task_pous:
                    try:
                        if str(task_pou) == desired_program_name:
                            task_has_program = True
                            break
                        if hasattr(task_pou, 'get_name') and str(task_pou.get_name(False)) == desired_program_name:
                            task_has_program = True
                            break
                    except Exception:
                        pass
                if not task_has_program and hasattr(task_pous, 'add'):
                    task_pous.add(desired_program_name)
            result = {
                "success": True,
                "step": "create_task",
                "task_config_created": task_config_created,
                "task_created": task_created,
                "task_name": desired_task_name,
            }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_task",
    }
""" % (DESIRED_PROGRAM_NAME, DESIRED_TASK_NAME)


def build_project_status_step(expected_project_path: str) -> str:
    escaped_path = escape_script_string(expected_project_path)
    return """
import json
import os
import sys
import traceback

try:
    expected_project_path = "{0}"
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session", "step": "status"}}
    else:
        project = session.active_project
        actual_path = project.path if hasattr(project, 'path') else ""
        result = {{
            "success": actual_path == expected_project_path,
            "step": "status",
            "expected_project_path": expected_project_path,
            "actual_project_path": actual_path,
            "project_name": project.name if hasattr(project, 'name') else os.path.basename(actual_path),
        }}
        if actual_path != expected_project_path:
            result["error"] = "Active project path does not match requested project"
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "status",
    }}
""".format(escaped_path)


def build_steps(project_path: str, template_path: str) -> list[tuple[str, str]]:
    return [
        ("open_template", build_open_template_step(project_path, template_path)),
        ("replace_device", build_replace_device_step()),
        ("resolve_application", build_resolve_application_step()),
        ("create_program", build_create_program_step()),
        ("create_task", build_create_task_step()),
        ("status", build_project_status_step(project_path)),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debug project/create directly with raw script/execute steps against local CODESYS.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--log-lines", type=int, default=120, help="How many filtered server log lines to print on failure")
    return parser


def print_step_payload(name: str, started_at: float, status_code: int, payload: dict[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: status={2} success={3}".format(elapsed, name, status_code, payload.get("success")))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run raw project/create probe from sandbox identity '{0}'.".format(identity),
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

    project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_raw_create_probe_{uuid.uuid4().hex}.project")
    template_path = derive_template_path(probe_env["CODESYS_API_CODESYS_PATH"])

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        print("Target project path: {0}".format(project_path))
        print("Template path: {0}".format(template_path))
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

        for step_name, script in build_steps(project_path, template_path):
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
                print("Raw project/create probe stopped at step: {0}".format(step_name))
                print("Server log excerpt:")
                print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
                return 1

        print("Raw project/create probe completed successfully.")
        return 0
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
