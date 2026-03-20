from __future__ import annotations

import logging
import os
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
    def poll(self) -> int | None: ...

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


PopenFactory = Callable[..., ProcessLike]
SleepFn = Callable[[float], None]
NowFn = Callable[[], float]
PipeReadyFn = Callable[[str, float], bool]
ShutdownRequestFn = Callable[[str, int], dict[str, object]]


def default_popen_factory(command: str, **kwargs: Any) -> ProcessLike:
    return cast(ProcessLike, subprocess.Popen(command, **kwargs))


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
        stop_timeout: float = 10.0,
        stop_poll_interval: float = 0.5,
        post_terminate_wait: float = 2.0,
        log_buffer_capacity: int = 1000,
        pipe_ready_fn: PipeReadyFn = wait_for_named_pipe_listener,
        shutdown_request_fn: ShutdownRequestFn | None = None,
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
        self.stop_timeout = stop_timeout
        self.stop_poll_interval = stop_poll_interval
        self.post_terminate_wait = post_terminate_wait
        self.log_buffer_capacity = log_buffer_capacity
        self.pipe_ready_fn = pipe_ready_fn
        self.shutdown_request_fn = shutdown_request_fn or self._request_named_pipe_shutdown
        self.process: ProcessLike | None = None
        self.running = False
        self.lock = threading.Lock()
        self.no_ui_override: bool | None = None
        self.log_buffer: Deque[str] = deque(maxlen=log_buffer_capacity)
        self.log_lock = threading.Lock()
        self.output_threads: list[threading.Thread] = []

    def start(self) -> bool:
        with self.lock:
            try:
                if self.is_running():
                    self.logger.info("CODESYS process already running")
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

                self.running = True
                self.logger.info("CODESYS process started and fully initialized")
                self._record_runtime_event("CODESYS process started and fully initialized")
                return True
            except Exception as exc:
                self.logger.error("Error starting CODESYS process: %s", str(exc))
                self._record_runtime_event("Error starting CODESYS process: {0}".format(str(exc)))
                return False

    def stop(self) -> bool:
        with self.lock:
            if not self.is_running():
                self.logger.info("CODESYS process not running")
                return True

            try:
                self.logger.info("Stopping CODESYS process")
                self._record_runtime_event("Stopping CODESYS process")
                if self.config.transport_name == "named_pipe" and self.config.pipe_name:
                    self._request_graceful_shutdown()

                waited = 0.0
                while waited < self.stop_timeout:
                    if not self.is_running():
                        break
                    self.sleep_fn(self.stop_poll_interval)
                    waited += self.stop_poll_interval

                if self.is_running():
                    self.logger.info("Process still running after %s seconds, sending TERMINATE signal", waited)
                    try:
                        assert self.process is not None
                        self.process.terminate()
                    except Exception as exc:
                        self.logger.warning("Error terminating process: %s", str(exc))

                    self.sleep_fn(self.post_terminate_wait)

                    if self.is_running():
                        self.logger.warning("Process still running after TERMINATE signal, sending KILL signal")
                        try:
                            assert self.process is not None
                            self.process.kill()
                        except Exception as exc:
                            self.logger.error("Error killing process: %s", str(exc))
                            return False

                self.process = None
                self.running = False
                self._join_output_threads()
                self.logger.info("CODESYS process stopped successfully")
                self._record_runtime_event("CODESYS process stopped successfully")
                return True
            except Exception as exc:
                self.logger.error("Error stopping CODESYS process: %s", str(exc))
                self._record_runtime_event("Error stopping CODESYS process: {0}".format(str(exc)))
                return False

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

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
        for thread in self.output_threads:
            thread.join(timeout=1.0)
        self.output_threads = []

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
