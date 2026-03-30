from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from io import BufferedReader
from pathlib import Path
from typing import Any, Callable, Deque, Protocol, cast

from .named_pipe_transport import NamedPipeScriptTransport, wait_for_named_pipe_listener


class ProcessLike(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


PopenFactory = Callable[..., ProcessLike]
SleepFn = Callable[[float], None]
NowFn = Callable[[], float]
PipeReadyFn = Callable[[str, float], bool]
ShutdownRequestFn = Callable[[str, int], dict[str, object]]
TaskkillRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
ProcessIdLister = Callable[[], list[int]]


def default_popen_factory(command: str, **kwargs: Any) -> ProcessLike:
    return cast(ProcessLike, subprocess.Popen(command, **kwargs))


def default_taskkill_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def list_codesys_process_ids() -> list[int]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process -Name CODESYS -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        return []
    ids: list[int] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if stripped and re.fullmatch(r"\d+", stripped):
            ids.append(int(stripped))
    return ids


def new_codesys_process_ids(before_ids: list[int], after_ids: list[int]) -> list[int]:
    known_ids = set(before_ids)
    return [pid for pid in after_ids if pid not in known_ids]


@dataclass(frozen=True)
class ProcessManagerConfig:
    codesys_path: Path
    script_path: Path
    script_lib_dir: Path
    profile_name: str | None = None
    profile_path: Path | None = None
    no_ui: bool = True
    transport_name: str = "named_pipe"
    pipe_name: str | None = None


class CodesysProcessManager:
    def __init__(
        self,
        config: ProcessManagerConfig,
        logger: logging.Logger,
        *,
        popen_factory: PopenFactory = default_popen_factory,
        sleep_fn: SleepFn = time.sleep,
        now_fn: NowFn = time.time,
        startup_timeout: float = 30.0,
        startup_poll_interval: float = 1.0,
        initialization_wait: float = 10.0,
        pipe_ready_timeout: float = 90.0,
        attach_ready_timeout: float = 0.2,
        stop_timeout: float = 10.0,
        stop_poll_interval: float = 0.5,
        post_terminate_wait: float = 2.0,
        log_buffer_capacity: int = 1000,
        pipe_ready_fn: PipeReadyFn = wait_for_named_pipe_listener,
        shutdown_request_fn: ShutdownRequestFn | None = None,
        taskkill_runner: TaskkillRunner = default_taskkill_runner,
        codesys_process_lister: ProcessIdLister = list_codesys_process_ids,
    ) -> None:
        self.config = config
        self.logger = logger
        self.popen_factory = popen_factory
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn
        self.startup_timeout = startup_timeout
        self.startup_poll_interval = startup_poll_interval
        self.initialization_wait = initialization_wait
        self.pipe_ready_timeout = pipe_ready_timeout
        self.attach_ready_timeout = attach_ready_timeout
        self.stop_timeout = stop_timeout
        self.stop_poll_interval = stop_poll_interval
        self.post_terminate_wait = post_terminate_wait
        self.log_buffer_capacity = log_buffer_capacity
        self.pipe_ready_fn = pipe_ready_fn
        self.shutdown_request_fn = shutdown_request_fn or self._request_named_pipe_shutdown
        self.taskkill_runner = taskkill_runner
        self.codesys_process_lister = codesys_process_lister
        self.process: ProcessLike | None = None
        self.running = False
        self.managed_codesys_pids: set[int] = set()
        self.session_ownership = "none"
        self.lock = threading.Lock()
        self.no_ui_override: bool | None = None
        self.log_buffer: Deque[str] = deque(maxlen=log_buffer_capacity)
        self.log_lock = threading.Lock()
        self.output_threads: list[threading.Thread] = []
        self._pipe_probe_suppressed: bool = False

    def start(self) -> bool:
        with self.lock:
            try:
                self._pipe_probe_suppressed = False
                if self._is_local_session_running():
                    self.logger.info("CODESYS process already running")
                    return True
                if self._has_attachable_named_pipe_session():
                    self._mark_attached_session_running()
                    self.logger.info(
                        "Attaching to existing CODESYS named-pipe session: %s",
                        self.config.pipe_name,
                    )
                    self._record_runtime_event(
                        "Attached to existing CODESYS named-pipe session: {0}".format(
                            self.config.pipe_name
                        )
                    )
                    return True

                if not self.config.codesys_path.exists():
                    self.logger.error("CODESYS executable not found at path: %s", self.config.codesys_path)
                    return False

                if not self.config.script_path.exists():
                    self.logger.error("CODESYS script not found at path: %s", self.config.script_path)
                    return False

                profile_error = self._validate_profile_configuration()
                if profile_error is not None:
                    self.logger.error(profile_error)
                    self._record_runtime_event(profile_error)
                    return False

                self.logger.info("Starting CODESYS process with script: %s", self.config.script_path)
                self._record_runtime_event(
                    "Starting CODESYS process with script: {0}".format(self.config.script_path)
                )
                self.managed_codesys_pids.clear()
                before_codesys_pids = self._safe_list_codesys_process_ids()

                try:
                    env = self._build_launch_env()
                    command = self._build_launch_command()
                    self.logger.info("Starting CODESYS with PYTHONPATH: %s", env["PYTHONPATH"])
                    self.logger.info("Starting CODESYS with command: %s", command)
                    self.process = self.popen_factory(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        shell=True,
                    )
                    self._start_output_threads()
                except subprocess.SubprocessError as exc:
                    self.logger.error("SubprocessError starting CODESYS: %s", str(exc))
                    self._record_runtime_event("SubprocessError starting CODESYS: {0}".format(str(exc)))
                    return False
                except FileNotFoundError:
                    self.logger.error(
                        "CODESYS executable not found. Check the path: %s",
                        self.config.codesys_path,
                    )
                    self._record_runtime_event(
                        "CODESYS executable not found. Check the path: {0}".format(self.config.codesys_path)
                    )
                    return False

                if self.startup_timeout > 0 and self.startup_poll_interval > 0:
                    self.sleep_fn(min(self.startup_timeout, self.startup_poll_interval))
                    if not self.is_running():
                        self._log_failed_start()
                        return False

                self.logger.info("CODESYS process has started. Waiting for full initialization...")
                self.logger.info(
                    "Waiting additional %s seconds for full initialization...",
                    self.initialization_wait,
                )
                self.sleep_fn(self.initialization_wait)

                if not self.is_running():
                    self.logger.error("CODESYS process failed to initialize properly")
                    self._record_runtime_event("CODESYS process failed to initialize properly")
                    return False

                if self.config.transport_name == "named_pipe":
                    if not self.config.pipe_name:
                        self.logger.error("Named pipe transport requires a pipe_name")
                        self._record_runtime_event("Named pipe transport requires a pipe_name")
                        return False
                    self.logger.info("Waiting for named pipe listener: %s", self.config.pipe_name)
                    if not self.pipe_ready_fn(self.config.pipe_name, self.pipe_ready_timeout):
                        self.logger.error(
                            "Named pipe listener did not become ready within %.1f seconds",
                            self.pipe_ready_timeout,
                        )
                        self._record_runtime_event(
                            "Named pipe listener did not become ready within {0:.1f} seconds".format(
                                self.pipe_ready_timeout
                            )
                        )
                        return False
                    self.logger.info("Named pipe listener is ready: %s", self.config.pipe_name)
                    self._record_runtime_event(
                        "Named pipe listener is ready: {0}".format(self.config.pipe_name)
                    )

                self._capture_managed_codesys_processes(before_codesys_pids)
                self.running = True
                self.session_ownership = "owned"
                self.logger.info("CODESYS process started and fully initialized")
                self._record_runtime_event("CODESYS process started and fully initialized")
                return True
            except Exception as exc:
                self.session_ownership = "none"
                self.logger.error("Error starting CODESYS process: %s", str(exc))
                self._record_runtime_event("Error starting CODESYS process: {0}".format(str(exc)))
                return False

    def stop(self) -> bool:
        with self.lock:
            local_running = self._is_local_session_running()
            attached_running = False
            if not local_running:
                attached_running = self._has_attachable_named_pipe_session()

            if not local_running and not attached_running:
                self.logger.info("CODESYS process not running")
                return True

            if not local_running and attached_running:
                self._mark_attached_session_running()
                return self._stop_attached_session()

            success = False
            try:
                self.logger.info("Stopping CODESYS process")
                self._record_runtime_event("Stopping CODESYS process")
                if self.config.transport_name == "named_pipe" and self.config.pipe_name:
                    self._request_graceful_shutdown()

                deadline = self.now_fn() + self.stop_timeout
                while self.now_fn() < deadline:
                    if not self.is_running():
                        break
                    self.sleep_fn(self.stop_poll_interval)

                if self._is_shell_process_running():
                    self.logger.info(
                        "Process still running after graceful wait, sending taskkill tree cleanup"
                    )
                    self._taskkill_shell_process_tree()  # kills cmd.exe + ALL descendants /T /F
                    self.sleep_fn(self.post_terminate_wait)

                    if self._is_shell_process_running():
                        self.logger.warning(
                            "Shell launcher still running after taskkill, sending TERMINATE signal"
                        )
                        try:
                            assert self.process is not None
                            self.process.terminate()
                        except Exception as exc:
                            self.logger.warning("Error terminating process: %s", str(exc))
                        self.sleep_fn(self.post_terminate_wait)

                    if self._is_managed_codesys_running():
                        self.logger.warning(
                            "Managed CODESYS IDE processes still running after taskkill, sending managed cleanup"
                        )
                        self._taskkill_managed_codesys_processes()
                        self.sleep_fn(self.post_terminate_wait)

                    if self._is_shell_process_running():
                        self.logger.warning(
                            "Shell launcher still running after all cleanup, sending KILL signal"
                        )
                        try:
                            assert self.process is not None
                            self.process.kill()
                        except Exception as exc:
                            self.logger.error("Error killing process: %s", str(exc))

                if self._is_managed_codesys_running():
                    self.logger.warning("Managed CODESYS IDE processes still running after shell shutdown, sending taskkill cleanup")
                    self._taskkill_managed_codesys_processes()
                    self.sleep_fn(self.post_terminate_wait)

                success = True
                self.logger.info("CODESYS process stopped successfully")
                self._record_runtime_event("CODESYS process stopped successfully")
            except Exception as exc:
                self.logger.error("Error stopping CODESYS process: %s", str(exc))
                self._record_runtime_event("Error stopping CODESYS process: {0}".format(str(exc)))
            finally:
                self.process = None
                self.running = False
                self.managed_codesys_pids.clear()
                self.session_ownership = "none"
                self._pipe_probe_suppressed = True
                self._join_output_threads()
            return success

    def is_running(self) -> bool:
        return self._is_local_session_running() or self._has_attachable_named_pipe_session()

    def get_status(self) -> dict[str, object]:
        if self.is_running():
            return {"state": "running", "timestamp": self.now_fn()}
        return {"state": "unknown", "timestamp": self.now_fn()}

    def get_log_lines(self) -> list[str]:
        with self.log_lock:
            return list(self.log_buffer)

    def is_no_ui_mode(self) -> bool:
        if self.no_ui_override is not None:
            return self.no_ui_override
        return self.config.no_ui

    def set_no_ui_mode(self, no_ui: bool) -> None:
        self.no_ui_override = no_ui

    def reset_runtime_mode(self) -> None:
        self.no_ui_override = None

    def _build_launch_env(self) -> dict[str, str]:
        env = os.environ.copy()
        script_lib = str(self.config.script_lib_dir)
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = script_lib + os.pathsep + env["PYTHONPATH"]
        else:
            env["PYTHONPATH"] = script_lib
        return env

    def _build_launch_args(self) -> list[str]:
        command_parts = [str(self.config.codesys_path)]
        if self.config.profile_name:
            command_parts.append('--profile="{0}"'.format(self.config.profile_name))
        if self.is_no_ui_mode():
            command_parts.append("--noUI")
        command_parts.append('--runscript="{0}"'.format(self.config.script_path))
        return command_parts

    def _build_launch_command(self) -> str:
        command_parts = [f"\"{self.config.codesys_path}\""]
        if self.config.profile_name:
            command_parts.append(f"--profile=\"{self.config.profile_name}\"")
        if self.is_no_ui_mode():
            command_parts.append("--noUI")
        command_parts.append(f"--runscript=\"{self.config.script_path}\"")
        return " ".join(command_parts)

    def _validate_profile_configuration(self) -> str | None:
        if self.config.profile_name is None:
            return (
                "CODESYS profile is not configured. Set CODESYS_API_CODESYS_PROFILE or "
                "CODESYS_API_CODESYS_PROFILE_PATH to avoid interactive profile selection."
            )

        if self.config.profile_path is not None and not self.config.profile_path.exists():
            return f"CODESYS profile file not found at path: {self.config.profile_path}"

        return None

    def _request_graceful_shutdown(self) -> None:
        if not self.config.pipe_name:
            self.logger.warning("Named pipe graceful shutdown requested without a pipe_name")
            self._record_runtime_event("Named pipe graceful shutdown requested without a pipe_name")
            return

        timeout = max(1, int(self.stop_timeout))
        try:
            result = self.shutdown_request_fn(self.config.pipe_name, timeout)
        except Exception as exc:
            self.logger.warning("Graceful named-pipe shutdown request failed: %s", str(exc))
            self._record_runtime_event(
                "Graceful named-pipe shutdown request failed: {0}".format(str(exc))
            )
            return

        if result.get("success") is True:
            self.logger.info("Graceful named-pipe shutdown acknowledged")
            self._record_runtime_event("Graceful named-pipe shutdown acknowledged")
        else:
            self.logger.warning(
                "Graceful named-pipe shutdown request returned failure: %s",
                result.get("error", "unknown error"),
            )
            self._record_runtime_event(
                "Graceful named-pipe shutdown request returned failure: {0}".format(
                    result.get("error", "unknown error")
                )
            )

    def _stop_attached_session(self) -> bool:
        try:
            self.logger.info("Stopping attached CODESYS named-pipe session")
            self._record_runtime_event("Stopping attached CODESYS named-pipe session")
            pre_shutdown_pids = set(self._safe_list_codesys_process_ids())
            if self.config.transport_name == "named_pipe" and self.config.pipe_name:
                self._request_graceful_shutdown()

            waited = 0.0
            pipe_gone = False
            while waited < self.stop_timeout:
                if not self._has_attachable_named_pipe_session():
                    pipe_gone = True
                    break
                self.sleep_fn(self.stop_poll_interval)
                waited += self.stop_poll_interval

            if not pipe_gone:
                pipe_gone = not self._has_attachable_named_pipe_session()

            if pipe_gone:
                orphan_pids = pre_shutdown_pids.intersection(self._safe_list_codesys_process_ids())
                if orphan_pids:
                    self.managed_codesys_pids = orphan_pids
                    self.logger.warning(
                        "Pipe gone but %d CODESYS process(es) still running after attached stop, sending taskkill cleanup",
                        len(orphan_pids),
                    )
                    self._record_runtime_event(
                        "Pipe gone but {0} CODESYS process(es) still running, sending taskkill cleanup".format(
                            len(orphan_pids)
                        )
                    )
                    self._taskkill_managed_codesys_processes()
                    self.sleep_fn(self.post_terminate_wait)
                self.running = False
                self.session_ownership = "none"
                self.managed_codesys_pids.clear()
                self._pipe_probe_suppressed = True
                self.logger.info("Attached CODESYS named-pipe session stopped successfully")
                self._record_runtime_event("Attached CODESYS named-pipe session stopped successfully")
                return True

            self.logger.warning(
                "Attached CODESYS named-pipe session is still reachable after %.1f seconds",
                self.stop_timeout,
            )
            self._record_runtime_event(
                "Attached CODESYS named-pipe session is still reachable after {0:.1f} seconds".format(
                    self.stop_timeout
                )
            )
            return False
        except Exception as exc:
            self.logger.error("Error stopping attached CODESYS session: %s", str(exc))
            self._record_runtime_event("Error stopping attached CODESYS session: {0}".format(str(exc)))
            return False

    def _request_named_pipe_shutdown(self, pipe_name: str, timeout: int) -> dict[str, object]:
        transport = NamedPipeScriptTransport(
            pipe_name=pipe_name,
            now_fn=self.now_fn,
            sleep_fn=self.sleep_fn,
        )
        shutdown_script = (
            "session.running = False\n"
            "result = {'success': True, 'message': 'Shutdown requested'}\n"
        )
        return transport.execute_script(shutdown_script, timeout=timeout)

    def _taskkill_shell_process_tree(self) -> None:
        process = self.process
        if process is None:
            return

        pid = getattr(process, "pid", None)
        if not isinstance(pid, int):
            self.logger.warning("Cannot taskkill process tree because pid is unavailable")
            self._record_runtime_event("Cannot taskkill process tree because pid is unavailable")
            return

        self._taskkill_pid_tree(pid)

    def _taskkill_managed_codesys_processes(self) -> None:
        for pid in sorted(self.managed_codesys_pids):
            self._taskkill_pid_tree(pid)
        self._refresh_managed_codesys_pids()

    def _taskkill_pid_tree(self, pid: int) -> None:
        completed = self.taskkill_runner(["taskkill", "/PID", str(pid), "/T", "/F"])
        if completed.returncode == 0:
            self.logger.info("taskkill process tree cleanup succeeded for pid %s", pid)
            self._record_runtime_event("taskkill process tree cleanup succeeded for pid {0}".format(pid))
            return

        stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown taskkill error"
        self.logger.warning("taskkill process tree cleanup failed for pid %s: %s", pid, stderr)
        self._record_runtime_event(
            "taskkill process tree cleanup failed for pid {0}: {1}".format(pid, stderr)
        )

    def _is_shell_process_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _is_managed_codesys_running(self) -> bool:
        self._refresh_managed_codesys_pids()
        return bool(self.managed_codesys_pids)

    def _is_local_session_running(self) -> bool:
        return self._is_shell_process_running() or self._is_managed_codesys_running()

    def _has_attachable_named_pipe_session(self) -> bool:
        if self.config.transport_name != "named_pipe" or not self.config.pipe_name:
            return False
        if self._pipe_probe_suppressed:
            return False
        try:
            return self.pipe_ready_fn(self.config.pipe_name, self.attach_ready_timeout)
        except Exception as exc:
            self.logger.warning("Unable to probe named pipe listener '%s': %s", self.config.pipe_name, str(exc))
            self._record_runtime_event(
                "Unable to probe named pipe listener '{0}': {1}".format(self.config.pipe_name, str(exc))
            )
            return False

    def _mark_attached_session_running(self) -> None:
        self.process = None
        self.running = True
        self.session_ownership = "attached"
        self.managed_codesys_pids.clear()

    def _capture_managed_codesys_processes(self, before_codesys_pids: list[int]) -> None:
        after_codesys_pids = self._safe_list_codesys_process_ids()
        self.managed_codesys_pids = set(new_codesys_process_ids(before_codesys_pids, after_codesys_pids))
        if self.managed_codesys_pids:
            pid_list = ", ".join(str(pid) for pid in sorted(self.managed_codesys_pids))
            self.logger.info("Tracking managed CODESYS IDE pids: %s", pid_list)
            self._record_runtime_event("Tracking managed CODESYS IDE pids: {0}".format(pid_list))
            return

        self.logger.warning("No new managed CODESYS IDE pids were detected after startup")
        self._record_runtime_event("No new managed CODESYS IDE pids were detected after startup")

    def _refresh_managed_codesys_pids(self) -> None:
        if not self.managed_codesys_pids:
            return
        current_codesys_pids = set(self._safe_list_codesys_process_ids())
        self.managed_codesys_pids.intersection_update(current_codesys_pids)

    def _safe_list_codesys_process_ids(self) -> list[int]:
        try:
            return self.codesys_process_lister()
        except Exception as exc:
            self.logger.warning("Unable to list CODESYS IDE processes: %s", str(exc))
            self._record_runtime_event("Unable to list CODESYS IDE processes: {0}".format(str(exc)))
            return list(self.managed_codesys_pids)

    def _log_failed_start(self) -> None:
        if self.process is None:
            return

        buffered_logs = "".join(self.get_log_lines()) or "No buffered process output"
        self.logger.error("CODESYS process failed to start. Buffered output:\n%s", buffered_logs)
        self._record_runtime_event("CODESYS process failed to start")

    def _start_output_threads(self) -> None:
        self.output_threads = []
        process = self.process
        if process is None:
            return

        stdout_stream = cast(BufferedReader | None, getattr(process, "stdout", None))
        stderr_stream = cast(BufferedReader | None, getattr(process, "stderr", None))

        for name, stream in (("STDOUT", stdout_stream), ("STDERR", stderr_stream)):
            if stream is None:
                continue
            thread = threading.Thread(
                target=self._read_process_stream,
                args=(name, stream),
                daemon=True,
            )
            thread.start()
            self.output_threads.append(thread)

    def _join_output_threads(self) -> None:
        import time as _time
        _t0 = _time.monotonic()
        self.logger.info("_join_output_threads: joining %d threads", len(self.output_threads))
        for i, thread in enumerate(self.output_threads):
            _tj = _time.monotonic()
            thread.join(timeout=1.0)
            _te = _time.monotonic()
            self.logger.info("_join_output_threads: thread %d join took %.3fs, alive=%s", i, _te - _tj, thread.is_alive())
        self.output_threads = []
        self.logger.info("_join_output_threads: done, total=%.3fs", _time.monotonic() - _t0)

    def _read_process_stream(self, source: str, stream: BufferedReader) -> None:
        while True:
            line = stream.readline()
            if line:
                self._append_log_line("{0}: {1}".format(source, self._decode_log_line(line)))
                continue
            process = self.process
            if process is None or process.poll() is not None:
                break
            self.sleep_fn(0.05)

    def _decode_log_line(self, line: bytes) -> str:
        decoded = line.decode("utf-8", errors="replace")
        if decoded.endswith("\n"):
            return decoded
        return decoded + "\n"

    def _append_log_line(self, line: str) -> None:
        with self.log_lock:
            self.log_buffer.append(line)

    def _record_runtime_event(self, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._append_log_line("[{0}] HOST: {1}\n".format(timestamp, message))
