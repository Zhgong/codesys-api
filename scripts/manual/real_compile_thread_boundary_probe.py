from __future__ import annotations

import argparse
import json
import logging
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

SRC_ROOT = common.REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from codesys_api.ironpython_script_engine import IronPythonScriptEngineAdapter


DEFAULT_CODESYS_PATH = r"C:\Program Files\CODESYS\CODESYS\Common\CODESYS.exe"
DEFAULT_STEP = "full_current_compile_wrapper"
SETUP_ONLY_STEP = "setup_only"
READBACK_ONLY_STEP = "readback_only"
STEP_DESCRIPTIONS = {
    SETUP_ONLY_STEP: "session/start + create project + write MissingVar only",
    READBACK_ONLY_STEP: "setup plus the existing PLC_PRG readback script",
    "build_only": "only application.build()",
    "build_and_generate_only": "application.build() + application.generate_code() only",
    "clear_messages_then_build": "message-category clear loop, then application.build()",
    "build_then_get_messages": "application.build() then system.get_messages()",
    "build_then_get_message_objects": "application.build() then category/object message harvest",
    "full_current_compile_wrapper": "exact current project.compile IronPython wrapper with safe_message_harvest=True",
}


def step_names() -> list[str]:
    return [
        SETUP_ONLY_STEP,
        READBACK_ONLY_STEP,
        "build_only",
        "build_and_generate_only",
        "clear_messages_then_build",
        "build_then_get_messages",
        "build_then_get_message_objects",
        "full_current_compile_wrapper",
    ]


def build_build_only_step() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "build_only"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "build_only"}
    else:
        application = session.active_project.active_application
        print("Calling application.build()...")
        application.build()
        print("application.build() returned")
        result = {"success": True, "step": "build_only"}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "build_only",
    }
"""


def build_build_and_generate_only_step() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "build_and_generate_only"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "build_and_generate_only"}
    else:
        application = session.active_project.active_application
        print("Calling application.build()...")
        application.build()
        print("application.build() returned")
        print("Calling application.generate_code()...")
        application.generate_code()
        print("application.generate_code() returned")
        result = {"success": True, "step": "build_and_generate_only"}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "build_and_generate_only",
    }
"""


def build_clear_messages_then_build_step() -> str:
    return """
import scriptengine
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "clear_messages_then_build"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "clear_messages_then_build"}
    else:
        application = session.active_project.active_application
        system = session.system if hasattr(session, 'system') else None
        if system is None and hasattr(scriptengine, 'system'):
            system = scriptengine.system
        categories = []
        if system is not None and hasattr(system, 'get_message_categories') and hasattr(system, 'clear_messages'):
            categories = list(system.get_message_categories(True))
            for category in categories:
                system.clear_messages(category)
        print("Cleared categories: " + str(len(categories)))
        application.build()
        result = {
            "success": True,
            "step": "clear_messages_then_build",
            "cleared_category_count": len(categories),
        }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "clear_messages_then_build",
    }
"""


def build_build_then_get_messages_step() -> str:
    return """
import scriptengine
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "build_then_get_messages"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "build_then_get_messages"}
    else:
        application = session.active_project.active_application
        system = session.system if hasattr(session, 'system') else None
        if system is None and hasattr(scriptengine, 'system'):
            system = scriptengine.system
        application.build()
        messages = []
        if system is not None and hasattr(system, 'get_messages'):
            messages = list(system.get_messages())
        result = {
            "success": True,
            "step": "build_then_get_messages",
            "message_count": len(messages),
            "contains_missing_var": "MissingVar" in "\\n".join([str(message) for message in messages]),
            "messages": [str(message) for message in messages[:20]],
        }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "build_then_get_messages",
    }
"""


def build_build_then_get_message_objects_step() -> str:
    return """
import scriptengine
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project", "step": "build_then_get_message_objects"}
    elif session.active_project.active_application is None:
        result = {"success": False, "error": "No active application", "step": "build_then_get_message_objects"}
    else:
        application = session.active_project.active_application
        system = session.system if hasattr(session, 'system') else None
        if system is None and hasattr(scriptengine, 'system'):
            system = scriptengine.system
        application.build()
        categories = []
        message_objects = []
        if system is not None and hasattr(system, 'get_message_categories') and hasattr(system, 'get_message_objects'):
            categories = list(system.get_message_categories(True))
            for category in categories:
                for msg_obj in system.get_message_objects(category):
                    message_objects.append(str(msg_obj))
        result = {
            "success": True,
            "step": "build_then_get_message_objects",
            "category_count": len(categories),
            "message_object_count": len(message_objects),
            "contains_missing_var": "MissingVar" in "\\n".join(message_objects),
            "messages": message_objects[:20],
        }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "build_then_get_message_objects",
    }
"""


def build_full_current_compile_wrapper_step(codesys_path: str = DEFAULT_CODESYS_PATH) -> str:
    adapter = IronPythonScriptEngineAdapter(
        codesys_path=Path(codesys_path),
        logger=logging.getLogger("real-compile-thread-boundary-probe"),
    )
    return adapter.build_execution(
        "project.compile",
        {"clean_build": False, "_safe_message_harvest": True},
    ).script


def build_step_script(step_name: str, *, codesys_path: str) -> str | None:
    if step_name == SETUP_ONLY_STEP:
        return None
    if step_name == READBACK_ONLY_STEP:
        return roundtrip.build_readback_script(roundtrip.TARGET_PATH)
    if step_name == "build_only":
        return build_build_only_step()
    if step_name == "build_and_generate_only":
        return build_build_and_generate_only_step()
    if step_name == "clear_messages_then_build":
        return build_clear_messages_then_build_step()
    if step_name == "build_then_get_messages":
        return build_build_then_get_messages_step()
    if step_name == "build_then_get_message_objects":
        return build_build_then_get_message_objects_step()
    if step_name == "full_current_compile_wrapper":
        return build_full_current_compile_wrapper_step(codesys_path)
    raise ValueError("Unknown step: {0}".format(step_name))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce the real compile threading failure down to the smallest "
            "CODESYS script/execute step that reproduces it."
        ),
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--step", choices=step_names(), default=DEFAULT_STEP, help="Reduction step to execute")
    parser.add_argument(
        "--include-readback",
        action="store_true",
        help="Mirror the recent failing sequence more closely by running PLC_PRG readback before the target step",
    )
    parser.add_argument("--script-timeout", type=int, default=300, help="Timeout seconds for the target script/execute call")
    parser.add_argument("--log-lines", type=int, default=120, help="How many filtered server log lines to print on failure")
    parser.add_argument("--list-steps", action="store_true", help="Print the reduction steps and exit")
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
    step_name: str,
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


def run_setup(base_url: str, project_path: str) -> tuple[int, dict[str, Any]]:
    status_code, payload = common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
    if not (status_code == 200 and payload.get("success") is True):
        return status_code, payload

    status_code, payload = execute_script_step(
        base_url=base_url,
        step_name="create_project_with_plc_prg",
        script=compile_probe.build_create_project_with_plc_prg_step(project_path),
        timeout=120,
    )
    if not (status_code == 200 and payload.get("success") is True):
        return status_code, payload

    return common.call_json(
        base_url,
        "/api/v1/pou/code",
        method="POST",
        payload={"path": roundtrip.TARGET_PATH, "implementation": roundtrip.EXPECTED_IMPLEMENTATION},
        timeout=120,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_steps:
        print_reduction_steps()
        return 0

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run compile thread-boundary probe from sandbox identity '{0}'.".format(identity),
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
    project_path = str(Path(tempfile.gettempdir()) / "codesys_api_thread_probe_{0}.project".format(uuid.uuid4().hex))

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        print("Selected step: {0}".format(args.step))
        print("Include readback: {0}".format(args.include_readback))
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
            step_name="create_project_with_plc_prg",
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

        if args.include_readback or args.step == READBACK_ONLY_STEP:
            started_at = time.perf_counter()
            status_code, payload = execute_script_step(
                base_url=base_url,
                step_name=READBACK_ONLY_STEP,
                script=roundtrip.build_readback_script(roundtrip.TARGET_PATH),
                timeout=120,
            )
            print_step_result("readback", started_at, status_code, payload)
            if not (status_code == 200 and payload.get("success") is True):
                print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
                return 1

        script = build_step_script(args.step, codesys_path=probe_env.get("CODESYS_API_CODESYS_PATH", DEFAULT_CODESYS_PATH))
        if script is None:
            print("Setup completed; no target script executed.")
            return 0

        started_at = time.perf_counter()
        status_code, payload = execute_script_step(
            base_url=base_url,
            step_name=args.step,
            script=script,
            timeout=args.script_timeout,
        )
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
