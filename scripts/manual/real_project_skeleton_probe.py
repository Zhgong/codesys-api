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


# ---------------------------------------------------------------------------
# Step builders — each returns an IronPython 2.7-compatible script string.
# State is carried across steps via the persistent session object.
# ---------------------------------------------------------------------------


def build_create_empty_project_step(project_path: str) -> str:
    escaped = escape_script_string(project_path)
    return """
import scriptengine
import sys
import traceback

try:
    target_path = "{0}"
    if hasattr(session, 'active_project') and session.active_project is not None:
        try:
            session.active_project.close()
        except Exception:
            pass
        session.active_project = None

    project = scriptengine.projects.create(target_path, True)
    if project is None:
        result = {{"success": False, "error": "projects.create returned None", "step": "create_empty_project"}}
    else:
        session.active_project = project
        if not hasattr(session, 'created_pous'):
            session.created_pous = {{}}
        top_level_names = []
        if hasattr(project, 'get_children'):
            for child in project.get_children():
                try:
                    top_level_names.append(str(child.get_name(False)) if hasattr(child, 'get_name') else str(child))
                except Exception:
                    pass
        result = {{
            "success": True,
            "step": "create_empty_project",
            "actual_project_path": project.path if hasattr(project, 'path') else target_path,
            "top_level_names": top_level_names,
            "has_active_application": hasattr(project, 'active_application') and project.active_application is not None,
        }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_empty_project",
    }}
""".format(escaped)


def build_add_device_step(
    device_name: str,
    device_type: int,
    device_id: str,
    device_version: str,
) -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session", "step": "add_device"}}
    else:
        project = session.active_project
        device_name = "{0}"
        device_type = {1}
        device_id = "{2}"
        device_version = "{3}"

        device_obj = project.add(device_name, device_type, device_id, device_version)
        session.skeleton_device = device_obj

        top_level_names = []
        device_names = []
        if hasattr(project, 'get_children'):
            for child in project.get_children():
                try:
                    child_name = str(child.get_name(False)) if hasattr(child, 'get_name') else str(child)
                    top_level_names.append(child_name)
                    if hasattr(child, 'is_device') and child.is_device:
                        device_names.append(child_name)
                except Exception:
                    pass

        result = {{
            "success": len(device_names) > 0,
            "step": "add_device",
            "device_names": device_names,
            "top_level_names": top_level_names,
            "add_returned_none": device_obj is None,
        }}
        if not result["success"]:
            result["error"] = "No device found after project.add()"
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "add_device",
    }}
""".format(
        escape_script_string(device_name),
        device_type,
        escape_script_string(device_id),
        escape_script_string(device_version),
    )


def build_resolve_active_application_step() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session", "step": "resolve_active_application"}
    else:
        project = session.active_project
        app = None

        if hasattr(project, 'active_application') and project.active_application is not None:
            app = project.active_application

        if app is None and hasattr(project, 'get_children'):
            for obj in project.get_children(True):
                try:
                    if hasattr(obj, 'is_application') and obj.is_application:
                        app = obj
                        try:
                            project.active_application = app
                        except Exception:
                            pass
                        break
                except Exception:
                    pass

        if app is None:
            result = {
                "success": False,
                "error": "No application found in project after add_device",
                "step": "resolve_active_application",
            }
        else:
            session.skeleton_app = app
            app_name = str(app.get_name(False)) if hasattr(app, 'get_name') else str(app)
            result = {
                "success": True,
                "step": "resolve_active_application",
                "application_name": app_name,
                "is_active_application": hasattr(app, 'is_active_application') and app.is_active_application,
            }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "resolve_active_application",
    }
"""


def build_create_plc_prg_step(pou_name: str = DEFAULT_POU_NAME) -> str:
    return """
import scriptengine
import sys
import traceback

try:
    if not hasattr(session, 'skeleton_app') or session.skeleton_app is None:
        result = {{"success": False, "error": "No application in session.skeleton_app", "step": "create_plc_prg"}}
    else:
        app = session.skeleton_app
        pou_name = "{0}"
        pou_obj = None

        if hasattr(app, 'create_pou'):
            pou_obj = app.create_pou(
                name=pou_name,
                type=scriptengine.PouType.Program,
                language=scriptengine.ImplementationLanguages.st,
            )
        elif hasattr(app, 'pou_container') and hasattr(app.pou_container, 'create_pou'):
            pou_obj = app.pou_container.create_pou(
                name=pou_name,
                type=scriptengine.PouType.Program,
                language=scriptengine.ImplementationLanguages.st,
            )

        if pou_obj is None:
            result = {{"success": False, "error": "create_pou returned None", "step": "create_plc_prg"}}
        else:
            if not hasattr(session, 'created_pous'):
                session.created_pous = {{}}
            session.created_pous[pou_name] = pou_obj
            session.skeleton_plc_prg = pou_obj
            pou_actual_name = str(pou_obj.get_name(False)) if hasattr(pou_obj, 'get_name') else pou_name
            result = {{
                "success": True,
                "step": "create_plc_prg",
                "pou_name": pou_actual_name,
            }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_plc_prg",
    }}
""".format(escape_script_string(pou_name))


def build_create_task_configuration_step() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'skeleton_app') or session.skeleton_app is None:
        result = {"success": False, "error": "No application in session.skeleton_app", "step": "create_task_configuration"}
    else:
        app = session.skeleton_app
        task_config = None

        if hasattr(app, 'create_task_configuration'):
            task_config = app.create_task_configuration()

        if task_config is None:
            result = {"success": False, "error": "create_task_configuration returned None", "step": "create_task_configuration"}
        else:
            session.skeleton_task_config = task_config
            tc_name = str(task_config.get_name(False)) if hasattr(task_config, 'get_name') else str(task_config)
            result = {
                "success": True,
                "step": "create_task_configuration",
                "task_config_name": tc_name,
            }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_task_configuration",
    }
"""


def build_create_main_task_step(task_name: str = DEFAULT_TASK_NAME) -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'skeleton_task_config') or session.skeleton_task_config is None:
        result = {{"success": False, "error": "No task_config in session.skeleton_task_config", "step": "create_main_task"}}
    else:
        task_config = session.skeleton_task_config
        task_name = "{0}"
        task_obj = None

        if hasattr(task_config, 'create_task'):
            task_obj = task_config.create_task(task_name)

        if task_obj is None:
            result = {{"success": False, "error": "create_task returned None", "step": "create_main_task"}}
        else:
            session.skeleton_main_task = task_obj
            actual_name = str(task_obj.get_name(False)) if hasattr(task_obj, 'get_name') else task_name
            result = {{
                "success": True,
                "step": "create_main_task",
                "task_name": actual_name,
            }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "create_main_task",
    }}
""".format(escape_script_string(task_name))


def build_assign_plc_prg_to_task_step(pou_name: str = DEFAULT_POU_NAME) -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'skeleton_main_task') or session.skeleton_main_task is None:
        result = {{"success": False, "error": "No task in session.skeleton_main_task", "step": "assign_plc_prg_to_task"}}
    else:
        task = session.skeleton_main_task
        pou_name = "{0}"
        assigned = False

        if hasattr(task, 'pous'):
            task_pous = task.pous
            already_assigned = False
            for tp in task_pous:
                try:
                    tp_name = str(tp.get_name(False)) if hasattr(tp, 'get_name') else str(tp)
                    if tp_name == pou_name:
                        already_assigned = True
                        break
                except Exception:
                    pass
            if not already_assigned and hasattr(task_pous, 'add'):
                task_pous.add(pou_name)
                assigned = True
            elif already_assigned:
                assigned = True

        pou_list = []
        if hasattr(task, 'pous'):
            for tp in task.pous:
                try:
                    pou_list.append(str(tp.get_name(False)) if hasattr(tp, 'get_name') else str(tp))
                except Exception:
                    pass

        result = {{
            "success": assigned,
            "step": "assign_plc_prg_to_task",
            "task_pous": pou_list,
        }}
        if not assigned:
            result["error"] = "task.pous.add() not available or assignment failed"
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "assign_plc_prg_to_task",
    }}
""".format(escape_script_string(pou_name))


def build_steps(
    project_path: str,
    device_name: str = DEFAULT_DEVICE_NAME,
    device_type: int = DEFAULT_DEVICE_TYPE,
    device_id: str = DEFAULT_DEVICE_ID,
    device_version: str = DEFAULT_DEVICE_VERSION,
    pou_name: str = DEFAULT_POU_NAME,
    task_name: str = DEFAULT_TASK_NAME,
) -> list[tuple[str, str]]:
    return [
        ("create_empty_project", build_create_empty_project_step(project_path)),
        ("add_device", build_add_device_step(device_name, device_type, device_id, device_version)),
        ("resolve_active_application", build_resolve_active_application_step()),
        ("create_plc_prg", build_create_plc_prg_step(pou_name)),
        ("create_task_configuration", build_create_task_configuration_step()),
        ("create_main_task", build_create_main_task_step(task_name)),
        ("assign_plc_prg_to_task", build_assign_plc_prg_to_task_step(pou_name)),
    ]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prove the full project skeleton primitive chain on real CODESYS.",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--log-lines", type=int, default=120)
    parser.add_argument("--device-name", default=DEFAULT_DEVICE_NAME)
    parser.add_argument("--device-type", type=int, default=DEFAULT_DEVICE_TYPE)
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--device-version", default=DEFAULT_DEVICE_VERSION)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run skeleton probe from sandbox identity '{0}'.".format(identity),
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
        / "codesys_api_skeleton_probe_{0}.project".format(uuid.uuid4().hex)
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

        steps = build_steps(
            project_path,
            device_name=args.device_name,
            device_type=args.device_type,
            device_id=args.device_id,
            device_version=args.device_version,
        )

        for step_name, script in steps:
            started_at = time.perf_counter()
            status_code, payload = common.call_json(
                base_url,
                "/api/v1/script/execute",
                method="POST",
                payload={"script": script},
                timeout=120,
            )
            elapsed = time.perf_counter() - started_at
            import json as _json
            print("[{0:.2f}s] {1}: status={2} success={3}".format(
                elapsed, step_name, status_code, payload.get("success")
            ))
            print(_json.dumps(payload, indent=2, ensure_ascii=False))

            if not (status_code == 200 and payload.get("success") is True):
                print("Skeleton probe stopped at step: {0}".format(step_name))
                print("Server log excerpt:")
                print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
                return 1

        print("Skeleton probe completed — all 7 steps passed.")
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
