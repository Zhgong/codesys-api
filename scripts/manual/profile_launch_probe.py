from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from codesys_api.codesys_process import list_codesys_process_ids, new_codesys_process_ids
from codesys_api.named_pipe_transport import NamedPipeScriptTransport, wait_for_named_pipe_listener


LOCAL_ENV_FILE = REPO_ROOT / ".env.real-codesys.local"
PERSISTENT_SCRIPT = REPO_ROOT / "src" / "codesys_api" / "assets" / "PERSISTENT_SESSION.py"
REQUIRED_ENV_VARS = (
    "CODESYS_API_CODESYS_PATH",
    "CODESYS_API_CODESYS_PROFILE",
    "CODESYS_API_CODESYS_PROFILE_PATH",
)
MODE_CHOICES = ("shell_string", "argv_quoted", "argv_plain", "all")


@dataclass(frozen=True)
class LaunchSpec:
    mode: str
    command: str | list[str]
    shell: bool


@dataclass(frozen=True)
class ProbeResult:
    mode: str
    command_display: str
    shell: bool
    pid: int | None
    pipe_name: str
    process_alive_after_start_wait: bool
    pipe_ready: bool
    initialization_marker_seen: bool
    main_loop_marker_seen: bool
    returncode: int | None
    requested_shutdown: bool
    shutdown_result: dict[str, object] | None
    new_pids_before_cleanup: list[int]
    remaining_new_pids_after_cleanup: list[int]
    stdout_tail: str
    stderr_tail: str


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError("Invalid env line without '=': {0}".format(stripped))
        name, value = stripped.split("=", 1)
        env[name] = value
    return env


def build_probe_env(base_env: Mapping[str, str], file_env: Mapping[str, str], pipe_name: str) -> dict[str, str]:
    merged = dict(base_env)
    for name, value in file_env.items():
        merged[name] = value
    merged["CODESYS_API_TRANSPORT"] = "named_pipe"
    merged["CODESYS_API_PIPE_NAME"] = pipe_name
    return merged


def missing_required_env_vars(env: Mapping[str, str]) -> list[str]:
    return [name for name in REQUIRED_ENV_VARS if not env.get(name)]


def build_success_command(codesys_path: Path, profile_name: str, script_path: Path) -> str:
    return '"{0}" --profile="{1}" --runscript="{2}"'.format(codesys_path, profile_name, script_path)


def build_launch_spec(mode: str, codesys_path: Path, profile_name: str, script_path: Path) -> LaunchSpec:
    if mode == "shell_string":
        return LaunchSpec(
            mode=mode,
            command=build_success_command(codesys_path, profile_name, script_path),
            shell=True,
        )
    if mode == "argv_quoted":
        return LaunchSpec(
            mode=mode,
            command=[
                str(codesys_path),
                '--profile="{0}"'.format(profile_name),
                '--runscript="{0}"'.format(script_path),
            ],
            shell=False,
        )
    if mode == "argv_plain":
        return LaunchSpec(
            mode=mode,
            command=[
                str(codesys_path),
                "--profile={0}".format(profile_name),
                "--runscript={0}".format(script_path),
            ],
            shell=False,
        )
    raise ValueError("Unsupported mode: {0}".format(mode))


def command_display(command: str | list[str]) -> str:
    if isinstance(command, str):
        return command
    return subprocess.list2cmdline(command)


def request_named_pipe_shutdown(pipe_name: str, timeout: int) -> dict[str, object]:
    transport = NamedPipeScriptTransport(pipe_name=pipe_name)
    return transport.execute_script(
        "session.running = False\nresult = {'success': True, 'message': 'Shutdown requested'}\n",
        timeout=timeout,
    )


def kill_process_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )


def wait_for_exit(process: subprocess.Popen[str], timeout_seconds: float) -> None:
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        pass


def read_process_output(process: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=5.0)
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = ""
    return stdout, stderr


def tail_text(text: str, max_lines: int = 20) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def build_probe_pipe_name() -> str:
    return "codesys_profile_probe_{0}".format(uuid.uuid4().hex)


def run_probe_mode(
    mode: str,
    env: Mapping[str, str],
    *,
    start_wait_seconds: float = 10.0,
    pipe_wait_seconds: float = 25.0,
) -> ProbeResult:
    before_process_ids = list_codesys_process_ids()
    launch_spec = build_launch_spec(
        mode,
        Path(str(env["CODESYS_API_CODESYS_PATH"])),
        str(env["CODESYS_API_CODESYS_PROFILE"]),
        PERSISTENT_SCRIPT,
    )
    process = subprocess.Popen(
        launch_spec.command,
        cwd=REPO_ROOT,
        env=dict(env),
        shell=launch_spec.shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pid = process.pid

    time.sleep(start_wait_seconds)
    alive_after_wait = process.poll() is None
    pipe_name = str(env["CODESYS_API_PIPE_NAME"])
    pipe_ready = wait_for_named_pipe_listener(pipe_name, pipe_wait_seconds)
    new_pids = new_codesys_process_ids(before_process_ids, list_codesys_process_ids())

    shutdown_requested = False
    shutdown_result: dict[str, object] | None = None
    if pipe_ready:
        shutdown_requested = True
        try:
            shutdown_result = request_named_pipe_shutdown(pipe_name, timeout=10)
        except Exception as exc:
            shutdown_result = {"success": False, "error": str(exc)}

    wait_for_exit(process, timeout_seconds=10.0)
    if process.poll() is None:
        kill_process_tree(pid)
        wait_for_exit(process, timeout_seconds=5.0)

    for new_pid in new_pids:
        kill_process_tree(new_pid)
    final_process_ids = list_codesys_process_ids()

    stdout, stderr = read_process_output(process)
    combined_output = "{0}\n{1}".format(stdout, stderr)

    return ProbeResult(
        mode=mode,
        command_display=command_display(launch_spec.command),
        shell=launch_spec.shell,
        pid=pid,
        pipe_name=pipe_name,
        process_alive_after_start_wait=alive_after_wait,
        pipe_ready=pipe_ready,
        initialization_marker_seen="Initializing CODESYS session - started" in combined_output,
        main_loop_marker_seen="Entering main loop" in combined_output,
        returncode=process.poll(),
        requested_shutdown=shutdown_requested,
        shutdown_result=shutdown_result,
        new_pids_before_cleanup=new_pids,
        remaining_new_pids_after_cleanup=new_codesys_process_ids(before_process_ids, final_process_ids),
        stdout_tail=tail_text(stdout),
        stderr_tail=tail_text(stderr),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Python launch styles for real CODESYS profile startup.",
    )
    parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default="all",
        help="Launch style to probe",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    file_env = load_env_file(LOCAL_ENV_FILE)
    modes = list(MODE_CHOICES[:-1]) if args.mode == "all" else [args.mode]
    results: list[ProbeResult] = []

    for mode in modes:
        pipe_name = build_probe_pipe_name()
        probe_env = build_probe_env(os.environ, file_env, pipe_name)
        missing = missing_required_env_vars(probe_env)
        if missing:
            print(
                "Missing required real CODESYS environment variables: {0}".format(", ".join(missing)),
                file=sys.stderr,
            )
            return 2
        result = run_probe_mode(mode, probe_env)
        results.append(result)

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            print("Mode: {0}".format(result.mode))
            print("Shell: {0}".format(result.shell))
            print("PID: {0}".format(result.pid))
            print("Pipe: {0}".format(result.pipe_name))
            print("Command: {0}".format(result.command_display))
            print("Alive after start wait: {0}".format(result.process_alive_after_start_wait))
            print("Pipe ready: {0}".format(result.pipe_ready))
            print("Initialization marker seen: {0}".format(result.initialization_marker_seen))
            print("Main loop marker seen: {0}".format(result.main_loop_marker_seen))
            print("Return code: {0}".format(result.returncode))
            print("Requested shutdown: {0}".format(result.requested_shutdown))
            print("Shutdown result: {0}".format(result.shutdown_result))
            print("New PIDs before cleanup: {0}".format(result.new_pids_before_cleanup))
            print("Remaining new PIDs after cleanup: {0}".format(result.remaining_new_pids_after_cleanup))
            print("STDOUT tail:")
            print(result.stdout_tail or "<empty>")
            print("STDERR tail:")
            print(result.stderr_tail or "<empty>")
            print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
