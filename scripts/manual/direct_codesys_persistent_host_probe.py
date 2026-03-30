from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path


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
from codesys_api.named_pipe_transport import NamedPipeScriptTransport, wait_for_named_pipe_listener
from codesys_api.server_config import load_server_config


DEFAULT_DEVICE_NAME = "CODESYS Control Win V3 x64"
DEFAULT_DEVICE_TYPE = 4096
DEFAULT_DEVICE_ID = "0000 0004"
DEFAULT_DEVICE_VERSION = "3.5.20.50"
DEFAULT_POU_NAME = "PLC_PRG"
DEFAULT_TASK_NAME = "MainTask"
MODE_CHOICES = ("single_request_full_build", "two_request_session_flow")
EXEC_MODE_CHOICES = ("background", "primary")
MODE_DESCRIPTIONS = {
    "single_request_full_build": "one request does create/write/build/message harvest inside the session host",
    "two_request_session_flow": "first request creates+writes, second request builds+harvests messages from the kept session",
}


def mode_names() -> list[str]:
    return list(MODE_CHOICES)


def build_probe_env(
    base_env: Mapping[str, str],
    file_env: Mapping[str, str],
    *,
    pipe_name: str,
    exec_mode: str,
) -> dict[str, str]:
    merged = dict(base_env)
    for name, value in file_env.items():
        merged[name] = value
    merged["CODESYS_API_PIPE_NAME"] = pipe_name
    merged["CODESYS_DIRECT_SESSION_EXEC_MODE"] = exec_mode
    return merged


def build_launch_command(codesys_path: Path, profile_name: str, script_path: Path, *, no_ui: bool = False) -> str:
    command = '"{0}" --profile="{1}"'.format(codesys_path, profile_name)
    if no_ui:
        command += " --noUI"
    command += ' --runscript="{0}"'.format(script_path)
    return command


def build_host_script() -> str:
    return """
import json
import os
import scriptengine
import sys
import threading
import time
import traceback
import warnings

NAMED_PIPE_SUPPORT = False
try:
    import clr
    try:
        clr.AddReference("System")
    except Exception:
        pass
    try:
        clr.AddReference("System.Core")
    except Exception:
        pass
    from System import Array, Byte
    from System.IO.Pipes import NamedPipeServerStream, PipeDirection, PipeTransmissionMode, PipeOptions
    from System.Text import Encoding
    NAMED_PIPE_SUPPORT = True
except Exception:
    pass

warnings.filterwarnings("ignore", category=DeprecationWarning)

PIPE_NAME = os.environ.get("CODESYS_API_PIPE_NAME", "codesys_direct_session_probe")
EXEC_MODE = os.environ.get("CODESYS_DIRECT_SESSION_EXEC_MODE", "background").strip().lower()


class MinimalPersistentHost(object):
    def __init__(self):
        self.system = None
        self.active_project = None
        self.created_pous = {}
        self.running = True
        self.init_success = False
        self.request_thread = None

    def initialize(self):
        try:
            self.system = scriptengine.system
            self.init_success = self.system is not None and NAMED_PIPE_SUPPORT
            return self.init_success
        except Exception:
            self.init_success = False
            return False

    def run(self):
        if not self.init_success:
            return False
        if EXEC_MODE == "primary":
            self.process_named_pipe_requests()
            return True
        self.request_thread = threading.Thread(target=self.process_named_pipe_requests)
        self.request_thread.daemon = True
        self.request_thread.start()
        while self.running:
            time.sleep(0.1)
        return True

    def process_named_pipe_requests(self):
        server = None
        request_id = "unknown"
        try:
            server = NamedPipeServerStream(
                PIPE_NAME,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.None
            )
            while self.running:
                try:
                    server.WaitForConnection()
                    request = self.normalize_named_pipe_request(self.read_named_pipe_request(server))
                    request_id = request.get("request_id", "unknown")
                    result = self.execute_script_content(request["script"])
                    result = self.normalize_named_pipe_result(result, request_id)
                    self.write_named_pipe_result(server, result)
                except Exception, request_e:
                    try:
                        if server is not None and server.IsConnected:
                            self.write_named_pipe_result(server, self.build_named_pipe_failure_response(request_id, str(request_e)))
                    except Exception:
                        pass
                finally:
                    request_id = "unknown"
                    try:
                        if server is not None and server.IsConnected:
                            server.Disconnect()
                    except Exception:
                        pass
        finally:
            try:
                if server is not None:
                    if server.IsConnected:
                        server.Disconnect()
                    server.Close()
            except Exception:
                pass

    def read_named_pipe_request(self, server):
        header = self.read_exact_bytes(server, 4)
        message_size = (
            ord(header[0]) |
            (ord(header[1]) << 8) |
            (ord(header[2]) << 16) |
            (ord(header[3]) << 24)
        )
        payload = self.read_exact_bytes(server, message_size)
        request = json.loads(payload)
        if not isinstance(request, dict):
            raise ValueError("Named pipe request payload must be a JSON object")
        return request

    def normalize_named_pipe_request(self, request):
        required_fields = ("request_id", "script", "timeout_hint", "created_at")
        for field_name in required_fields:
            if field_name not in request:
                raise ValueError("Named pipe request missing required field: " + str(field_name))
        return request

    def build_named_pipe_failure_response(self, request_id, error):
        return {
            "success": False,
            "error": error,
            "request_id": request_id,
        }

    def normalize_named_pipe_result(self, result, request_id):
        if isinstance(result, dict):
            normalized = dict(result)
        else:
            normalized = {"success": True, "result": result}
        normalized["request_id"] = request_id
        normalized.setdefault("success", "error" not in normalized)
        return normalized

    def write_named_pipe_result(self, server, result):
        body = json.dumps(result)
        body_bytes = Encoding.UTF8.GetBytes(body)
        size = body_bytes.Length
        header = Array[Byte]([
            size & 0xFF,
            (size >> 8) & 0xFF,
            (size >> 16) & 0xFF,
            (size >> 24) & 0xFF,
        ])
        server.Write(header, 0, 4)
        server.Write(body_bytes, 0, size)
        server.Flush()

    def read_exact_bytes(self, stream, size):
        buffer = Array.CreateInstance(Byte, size)
        offset = 0
        while offset < size:
            count = stream.Read(buffer, offset, size - offset)
            if count == 0:
                raise IOError("Named pipe stream closed before enough data was read")
            offset += count
        return "".join(chr(int(item)) for item in buffer)

    def execute_script_content(self, script_code):
        globals_dict = {
            "session": self,
            "host": self,
            "system": self.system,
            "active_project": self.active_project,
            "json": json,
            "os": os,
            "time": time,
            "scriptengine": scriptengine,
            "traceback": traceback,
            "sys": sys,
        }
        local_vars = {}
        try:
            exec(script_code, globals_dict, local_vars)
            result = local_vars.get("result", {"success": True, "message": "Script executed successfully (no result variable)"})
        except Exception, exec_e:
            result = {
                "success": False,
                "error": str(exec_e),
                "traceback": traceback.format_exc(),
            }
        if isinstance(result, dict):
            result["host_exec_mode"] = EXEC_MODE
            result["host_thread_name"] = threading.currentThread().getName()
        return result


host = MinimalPersistentHost()
if host.initialize():
    host.run()
"""


def build_single_request_full_build_script(project_path: str) -> str:
    return """
import scriptengine
import sys
import traceback

try:
    project = scriptengine.projects.create("{project_path}", True)
    if project is None:
        raise Exception("projects.create returned None")
    session.active_project = project

    project.add("{device_name}", {device_type}, "{device_id}", "{device_version}")
    app = project.active_application
    if app is None:
        raise Exception("No active application after add")

    pou = app.create_pou(
        name="{pou_name}",
        type=scriptengine.PouType.Program,
        language=scriptengine.ImplementationLanguages.st
    )
    session.created_pous["{pou_name}"] = pou

    task_config = app.create_task_configuration()
    task = task_config.create_task("{task_name}")
    task.pous.add("{pou_name}")

    pou.textual_implementation.replace(new_text="MissingVar := TRUE;")
    app.build()

    system = session.system if hasattr(session, "system") else None
    compilation_messages = []
    message_source = "none"
    if system is not None and hasattr(system, "get_messages"):
        try:
            for message_text in system.get_messages():
                compilation_messages.append(str(message_text))
        except Exception:
            pass
        if compilation_messages:
            message_source = "get_messages"
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
            message_source = "get_message_objects"

    joined_messages = "\\n".join(compilation_messages)
    result = {{
        "success": True,
        "step": "single_request_full_build",
        "project_path": project.path if hasattr(project, "path") else "{project_path}",
        "build_returned": True,
        "message_count": len(compilation_messages),
        "messages": compilation_messages[:50],
        "contains_missing_var": "missingvar" in joined_messages.lower(),
        "message_source": message_source,
    }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "single_request_full_build",
    }}
""".format(
        project_path=escape_script_string(project_path),
        device_name=escape_script_string(DEFAULT_DEVICE_NAME),
        device_type=DEFAULT_DEVICE_TYPE,
        device_id=escape_script_string(DEFAULT_DEVICE_ID),
        device_version=escape_script_string(DEFAULT_DEVICE_VERSION),
        pou_name=escape_script_string(DEFAULT_POU_NAME),
        task_name=escape_script_string(DEFAULT_TASK_NAME),
    )


def build_session_create_and_write_script(project_path: str) -> str:
    return """
import scriptengine
import sys
import traceback

try:
    project = scriptengine.projects.create("{project_path}", True)
    if project is None:
        raise Exception("projects.create returned None")
    session.active_project = project

    project.add("{device_name}", {device_type}, "{device_id}", "{device_version}")
    app = project.active_application
    if app is None:
        raise Exception("No active application after add")

    pou = app.create_pou(
        name="{pou_name}",
        type=scriptengine.PouType.Program,
        language=scriptengine.ImplementationLanguages.st
    )
    session.created_pous["{pou_name}"] = pou

    task_config = app.create_task_configuration()
    task = task_config.create_task("{task_name}")
    task.pous.add("{pou_name}")

    pou.textual_implementation.replace(new_text="MissingVar := TRUE;")
    result = {{
        "success": True,
        "step": "session_create_and_write",
        "project_path": project.path if hasattr(project, "path") else "{project_path}",
        "implementation_written": True,
    }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "session_create_and_write",
    }}
""".format(
        project_path=escape_script_string(project_path),
        device_name=escape_script_string(DEFAULT_DEVICE_NAME),
        device_type=DEFAULT_DEVICE_TYPE,
        device_id=escape_script_string(DEFAULT_DEVICE_ID),
        device_version=escape_script_string(DEFAULT_DEVICE_VERSION),
        pou_name=escape_script_string(DEFAULT_POU_NAME),
        task_name=escape_script_string(DEFAULT_TASK_NAME),
    )


def build_session_build_and_messages_script() -> str:
    return """
import sys
import traceback

try:
    if not hasattr(session, "active_project") or session.active_project is None:
        raise Exception("No active project in session")
    app = session.active_project.active_application
    if app is None:
        raise Exception("No active application in session project")

    app.build()

    system = session.system if hasattr(session, "system") else None
    compilation_messages = []
    message_source = "none"
    if system is not None and hasattr(system, "get_messages"):
        try:
            for message_text in system.get_messages():
                compilation_messages.append(str(message_text))
        except Exception:
            pass
        if compilation_messages:
            message_source = "get_messages"
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
            message_source = "get_message_objects"

    joined_messages = "\\n".join(compilation_messages)
    result = {
        "success": True,
        "step": "session_build_and_messages",
        "build_returned": True,
        "message_count": len(compilation_messages),
        "messages": compilation_messages[:50],
        "contains_missing_var": "missingvar" in joined_messages.lower(),
        "message_source": message_source,
    }
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": "session_build_and_messages",
    }
"""


def build_shutdown_script() -> str:
    return """
session.running = False
result = {
    "success": True,
    "step": "shutdown",
}
"""


def tail_text(text: str, max_lines: int = 40) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def execute_transport_script_with_timeout(pipe_name: str, script: str, timeout: int) -> dict[str, object]:
    transport = NamedPipeScriptTransport(pipe_name=pipe_name)
    result_holder: dict[str, dict[str, object]] = {}
    error_holder: dict[str, Exception] = {}

    def worker() -> None:
        try:
            result_holder["result"] = transport.execute_script(script, timeout=timeout)
        except Exception as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=worker, name="named-pipe-client")
    thread.daemon = True
    thread.start()
    thread.join(timeout + 5)
    if thread.is_alive():
        return {
            "success": False,
            "transport": "named_pipe",
            "error_stage": "timeout",
            "timeout": True,
            "error": "Launcher timed out waiting for named pipe response",
        }
    if "error" in error_holder:
        return {
            "success": False,
            "transport": "named_pipe",
            "error_stage": "client",
            "error": str(error_holder["error"]),
        }
    return result_holder["result"]


def print_step_result(step_name: str, started_at: float, payload: Mapping[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: success={2}".format(elapsed, step_name, payload.get("success")))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a minimal persistent CODESYS session host and compare background vs primary execution.",
    )
    parser.add_argument("--mode", choices=MODE_CHOICES, default="single_request_full_build")
    parser.add_argument("--exec-mode", choices=EXEC_MODE_CHOICES, default="background")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout seconds for host startup and each request")
    parser.add_argument("--keep-open", action="store_true", help="Do not shut down or kill the new CODESYS session")
    parser.add_argument("--list-modes", action="store_true", help="Print the host probe modes and exit")
    return parser


def print_modes() -> None:
    print("Persistent host modes:")
    for mode in mode_names():
        print("- {0}: {1}".format(mode, MODE_DESCRIPTIONS[mode]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_modes:
        print_modes()
        return 0

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run direct persistent host probe from sandbox identity '{0}'.".format(identity),
            file=sys.stderr,
        )
        return 2

    if not common.LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(common.LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    file_env = common.load_env_file(common.LOCAL_ENV_FILE)
    pipe_name = "codesys_direct_host_{0}".format(uuid.uuid4().hex)
    merged_env = build_probe_env(os.environ, file_env, pipe_name=pipe_name, exec_mode=args.exec_mode)
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
    project_path = temp_root / "codesys_persistent_host_probe_{0}.project".format(token)
    host_script_path = temp_root / "codesys_persistent_host_probe_{0}.py".format(token)
    host_script_path.write_text(build_host_script(), encoding="utf-8")

    before_codesys_pids = list_codesys_process_ids()
    command = build_launch_command(config.codesys_path, config.codesys_profile_name, host_script_path, no_ui=False)
    process = subprocess.Popen(
        command,
        cwd=common.REPO_ROOT,
        env=merged_env,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    exit_code = 0
    try:
        print("Windows identity: {0}".format(identity))
        print("Mode: {0}".format(args.mode))
        print("Exec mode: {0}".format(args.exec_mode))
        print("Pipe name: {0}".format(pipe_name))
        print("CODESYS path: {0}".format(config.codesys_path))
        print("CODESYS profile: {0}".format(config.codesys_profile_name))
        print("Host script path: {0}".format(host_script_path))
        print("Target project path: {0}".format(project_path))
        print("Launch command: {0}".format(command))

        if not wait_for_named_pipe_listener(pipe_name, float(args.timeout)):
            print("Timed out waiting for persistent host named pipe listener", file=sys.stderr)
            return 1

        if args.mode == "single_request_full_build":
            started_at = time.perf_counter()
            payload = execute_transport_script_with_timeout(
                pipe_name,
                build_single_request_full_build_script(str(project_path)),
                args.timeout,
            )
            print_step_result("single_request_full_build", started_at, payload)
            if payload.get("success") is not True:
                exit_code = 1
        else:
            started_at = time.perf_counter()
            payload = execute_transport_script_with_timeout(
                pipe_name,
                build_session_create_and_write_script(str(project_path)),
                args.timeout,
            )
            print_step_result("session_create_and_write", started_at, payload)
            if payload.get("success") is not True:
                exit_code = 1
            else:
                started_at = time.perf_counter()
                payload = execute_transport_script_with_timeout(
                    pipe_name,
                    build_session_build_and_messages_script(),
                    args.timeout,
                )
                print_step_result("session_build_and_messages", started_at, payload)
                if payload.get("success") is not True:
                    exit_code = 1
    finally:
        if not args.keep_open:
            shutdown_result = execute_transport_script_with_timeout(pipe_name, build_shutdown_script(), 20)
            if shutdown_result.get("success") is not True:
                print("Shutdown request did not complete cleanly:")
                print(json.dumps(shutdown_result, indent=2, ensure_ascii=False))
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
            print(tail_text(stdout))
        if stderr.strip():
            print("stderr tail:")
            print(tail_text(stderr), file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
