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
from profile_launch_probe import kill_process_tree
from real_project_create_raw_probe import escape_script_string

SRC_ROOT = common.REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from codesys_api.codesys_process import list_codesys_process_ids, new_codesys_process_ids
from codesys_api.server_config import load_server_config


DEFAULT_DEVICE_NAME = "CODESYS Control Win V3 x64"
DEFAULT_DEVICE_TYPE = 4096
DEFAULT_DEVICE_ID = "0000 0004"
DEFAULT_DEVICE_VERSION = "3.5.20.50"
DEFAULT_POU_NAME = "PLC_PRG"
DEFAULT_TASK_NAME = "MainTask"
MODE_CHOICES = (
    "create_and_build_clean",
    "create_and_build_error",
    "create_build_generate",
)
MODE_DESCRIPTIONS = {
    "create_and_build_clean": "create a clean project, then call app.build() only",
    "create_and_build_error": "create a project, inject MissingVar := TRUE;, then call app.build()",
    "create_build_generate": "create a clean project, call app.build(), then app.generate_code()",
}


def mode_names() -> list[str]:
    return list(MODE_CHOICES)


def build_mode_settings(mode: str) -> dict[str, object]:
    if mode == "create_and_build_clean":
        return {
            "mode": mode,
            "implementation_text": "",
            "run_generate_code": False,
        }
    if mode == "create_and_build_error":
        return {
            "mode": mode,
            "implementation_text": "MissingVar := TRUE;",
            "run_generate_code": False,
        }
    if mode == "create_build_generate":
        return {
            "mode": mode,
            "implementation_text": "",
            "run_generate_code": True,
        }
    raise ValueError("Unsupported mode: {0}".format(mode))


def build_probe_env(base_env: Mapping[str, str], file_env: Mapping[str, str]) -> dict[str, str]:
    merged = dict(base_env)
    for name, value in file_env.items():
        merged[name] = value
    return merged


def build_launch_command(codesys_path: Path, profile_name: str, script_path: Path, *, no_ui: bool = False) -> str:
    command = '"{0}" --profile="{1}"'.format(codesys_path, profile_name)
    if no_ui:
        command += " --noUI"
    command += ' --runscript="{0}"'.format(script_path)
    return command


def build_generated_script(project_path: str, result_path: str, mode: str) -> str:
    settings = build_mode_settings(mode)
    implementation_text = str(settings["implementation_text"])
    run_generate_code = bool(settings["run_generate_code"])
    generate_code_block = ""
    if run_generate_code:
        generate_code_block = """
    app.generate_code()
    result["generate_code_returned"] = True
    result["step_reached"] = "generate_code_returned"
"""
    return """
import json
import os
import scriptengine
import sys
import traceback

RESULT_PATH = "{result_path}"
PROJECT_PATH = "{project_path}"
MODE = "{mode}"
IMPLEMENTATION_TEXT = "{implementation_text}"
RUN_GENERATE_CODE = {run_generate_code}


def write_result(payload):
    handle = open(RESULT_PATH, "w")
    try:
        handle.write(json.dumps(payload))
    finally:
        handle.close()


result = {{
    "success": False,
    "mode": MODE,
    "step_reached": "start",
    "project_path": PROJECT_PATH,
    "build_returned": False,
    "generate_code_returned": False,
    "message_count": 0,
    "messages": [],
    "contains_missing_var": False,
    "message_source": "none",
}}

try:
    project = scriptengine.projects.create(PROJECT_PATH, True)
    if project is None:
        raise Exception("projects.create returned None")
    result["step_reached"] = "project_created"

    project.add("{device_name}", {device_type}, "{device_id}", "{device_version}")
    result["step_reached"] = "device_added"

    app = project.active_application
    if app is None:
        raise Exception("No active application after add")
    result["step_reached"] = "application_resolved"

    pou = app.create_pou(
        name="{pou_name}",
        type=scriptengine.PouType.Program,
        language=scriptengine.ImplementationLanguages.st
    )
    if pou is None:
        raise Exception("create_pou returned None")
    result["step_reached"] = "pou_created"

    task_config = app.create_task_configuration()
    task = task_config.create_task("{task_name}")
    task.pous.add("{pou_name}")
    result["step_reached"] = "task_linked"

    pou.textual_implementation.replace(new_text=IMPLEMENTATION_TEXT)
    result["step_reached"] = "implementation_written"

    app.build()
    result["build_returned"] = True
    result["step_reached"] = "build_returned"

{generate_code_block}

    system = scriptengine.system if hasattr(scriptengine, "system") else None
    compilation_messages = []
    if system is not None and hasattr(system, "get_messages"):
        try:
            for message_text in system.get_messages():
                compilation_messages.append(str(message_text))
        except Exception:
            pass
        if compilation_messages:
            result["message_source"] = "get_messages"

    if (
        not compilation_messages
        and system is not None
        and hasattr(system, "get_message_categories")
        and hasattr(system, "get_message_objects")
    ):
        try:
            for category in system.get_message_categories(True):
                try:
                    for message_object in system.get_message_objects(category):
                        compilation_messages.append(str(message_object))
                except Exception:
                    pass
        except Exception:
            pass
        if compilation_messages:
            result["message_source"] = "get_message_objects"

    joined_messages = "\\n".join(compilation_messages)
    result["messages"] = compilation_messages[:50]
    result["message_count"] = len(compilation_messages)
    result["contains_missing_var"] = "missingvar" in joined_messages.lower()

    result["success"] = True
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result["success"] = False
    result["error"] = str(error_value)
    result["traceback"] = traceback.format_exc()

write_result(result)
""".format(
        result_path=escape_script_string(result_path),
        project_path=escape_script_string(project_path),
        mode=escape_script_string(mode),
        implementation_text=escape_script_string(implementation_text),
        run_generate_code="True" if run_generate_code else "False",
        generate_code_block=generate_code_block,
        device_name=escape_script_string(DEFAULT_DEVICE_NAME),
        device_type=DEFAULT_DEVICE_TYPE,
        device_id=escape_script_string(DEFAULT_DEVICE_ID),
        device_version=escape_script_string(DEFAULT_DEVICE_VERSION),
        pou_name=escape_script_string(DEFAULT_POU_NAME),
        task_name=escape_script_string(DEFAULT_TASK_NAME),
    )


def read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def wait_for_result_file(result_path: Path, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_decode_error: Exception | None = None
    while time.time() < deadline:
        if result_path.exists():
            try:
                return read_json_file(result_path)
            except json.JSONDecodeError as exc:
                last_decode_error = exc
        time.sleep(0.2)
    if last_decode_error is not None:
        raise TimeoutError("Timed out waiting for valid JSON result: {0}".format(last_decode_error))
    raise TimeoutError("Timed out waiting for result file: {0}".format(result_path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a direct CODESYS --runscript probe without the current HTTP/session host layer.",
    )
    parser.add_argument("--mode", choices=MODE_CHOICES, default="create_and_build_error")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout seconds for the direct runscript result")
    parser.add_argument("--keep-open", action="store_true", help="Do not kill new CODESYS processes after the result arrives")
    parser.add_argument("--list-modes", action="store_true", help="Print the direct probe modes and exit")
    return parser


def print_modes() -> None:
    print("Direct runscript modes:")
    for mode in mode_names():
        print("- {0}: {1}".format(mode, MODE_DESCRIPTIONS[mode]))


def print_result_summary(payload: Mapping[str, object]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_modes:
        print_modes()
        return 0

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run direct CODESYS runscript probe from sandbox identity '{0}'.".format(identity),
            file=sys.stderr,
        )
        return 2

    if not common.LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(common.LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    file_env = common.load_env_file(common.LOCAL_ENV_FILE)
    merged_env = build_probe_env(os.environ, file_env)
    config = load_server_config(common.REPO_ROOT, merged_env)

    if not config.codesys_path.exists():
        print("CODESYS executable not found: {0}".format(config.codesys_path), file=sys.stderr)
        return 2
    if not config.codesys_profile_name:
        print(
            "CODESYS profile is not configured. Set CODESYS_API_CODESYS_PROFILE or CODESYS_API_CODESYS_PROFILE_PATH.",
            file=sys.stderr,
        )
        return 2
    if config.codesys_profile_path is not None and not config.codesys_profile_path.exists():
        print("CODESYS profile file not found: {0}".format(config.codesys_profile_path), file=sys.stderr)
        return 2

    temp_root = Path(tempfile.gettempdir())
    token = uuid.uuid4().hex
    project_path = temp_root / "codesys_direct_probe_{0}.project".format(token)
    result_path = temp_root / "codesys_direct_probe_{0}.result.json".format(token)
    script_path = temp_root / "codesys_direct_probe_{0}.py".format(token)
    script_path.write_text(
        build_generated_script(str(project_path), str(result_path), args.mode),
        encoding="utf-8",
    )

    before_codesys_pids = list_codesys_process_ids()
    command = build_launch_command(config.codesys_path, config.codesys_profile_name, script_path, no_ui=False)
    process = subprocess.Popen(
        command,
        cwd=common.REPO_ROOT,
        env=merged_env,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    payload: dict[str, Any] | None = None
    exit_code = 0
    try:
        print("Windows identity: {0}".format(identity))
        print("Mode: {0}".format(args.mode))
        print("CODESYS path: {0}".format(config.codesys_path))
        print("CODESYS profile: {0}".format(config.codesys_profile_name))
        print("Generated script path: {0}".format(script_path))
        print("Target project path: {0}".format(project_path))
        print("Result path: {0}".format(result_path))
        print("Launch command: {0}".format(command))

        try:
            payload = wait_for_result_file(result_path, timeout_seconds=float(args.timeout))
            print_result_summary(payload)
            if payload.get("success") is not True:
                exit_code = 1
        except TimeoutError as exc:
            print("Timed out waiting for direct runscript result after {0}s".format(args.timeout), file=sys.stderr)
            print("Timeout detail: {0}".format(exc), file=sys.stderr)
            exit_code = 1
    finally:
        if not args.keep_open:
            if process.poll() is None:
                kill_process_tree(process.pid)
            after_codesys_pids = list_codesys_process_ids()
            for pid in new_codesys_process_ids(before_codesys_pids, after_codesys_pids):
                kill_process_tree(pid)
        try:
            stdout, stderr = process.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = ""
        if stdout.strip():
            print("stdout tail:")
            print("\n".join(stdout.splitlines()[-20:]))
        if stderr.strip():
            print("stderr tail:")
            print("\n".join(stderr.splitlines()[-20:]), file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
