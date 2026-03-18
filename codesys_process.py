from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, cast

from named_pipe_transport import wait_for_named_pipe_listener


class ProcessLike(Protocol):
    def poll(self) -> int | None: ...

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


PopenFactory = Callable[..., ProcessLike]
SleepFn = Callable[[float], None]
NowFn = Callable[[], float]
PipeReadyFn = Callable[[str, float], bool]


def default_popen_factory(command: str, **kwargs: Any) -> ProcessLike:
    return cast(ProcessLike, subprocess.Popen(command, **kwargs))


@dataclass(frozen=True)
class ProcessManagerConfig:
    codesys_path: Path
    script_path: Path
    status_file: Path
    termination_signal_file: Path
    log_file: Path
    script_lib_dir: Path
    profile_name: str | None = None
    profile_path: Path | None = None
    no_ui: bool = True
    transport_name: str = "file"
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
        pipe_ready_fn: PipeReadyFn = wait_for_named_pipe_listener,
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
        self.pipe_ready_fn = pipe_ready_fn
        self.process: ProcessLike | None = None
        self.running = False
        self.lock = threading.Lock()
        self.no_ui_override: bool | None = None

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
                    return False

                self.logger.info("Starting CODESYS process with script: %s", self.config.script_path)
                self._reset_runtime_files()
                self.config.log_file.parent.mkdir(parents=True, exist_ok=True)

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
                except subprocess.SubprocessError as exc:
                    self.logger.error("SubprocessError starting CODESYS: %s", str(exc))
                    return False
                except FileNotFoundError:
                    self.logger.error(
                        "CODESYS executable not found. Check the path: %s",
                        self.config.codesys_path,
                    )
                    return False

                waited = 0.0
                while waited < self.startup_timeout:
                    self.sleep_fn(self.startup_poll_interval)
                    waited += self.startup_poll_interval

                    if not self.is_running():
                        self._log_failed_start()
                        return False

                    if self.config.status_file.exists():
                        self.logger.info("Status file detected after %.1f seconds", waited)
                        break

                    self.logger.debug("Waiting for CODESYS initialization... (%.1f seconds elapsed)", waited)

                self.logger.info("CODESYS process has started. Waiting for full initialization...")
                self.logger.info(
                    "Waiting additional %s seconds for full initialization...",
                    self.initialization_wait,
                )
                self.sleep_fn(self.initialization_wait)

                if not self.is_running():
                    self.logger.error("CODESYS process failed to initialize properly")
                    return False

                if not self.config.status_file.exists():
                    self.logger.warning("CODESYS started but didn't create status file. Creating a default one.")
                    self._write_default_status("initialized")

                if self.config.transport_name == "named_pipe":
                    if not self.config.pipe_name:
                        self.logger.error("Named pipe transport requires a pipe_name")
                        return False
                    self.logger.info("Waiting for named pipe listener: %s", self.config.pipe_name)
                    if not self.pipe_ready_fn(self.config.pipe_name, self.pipe_ready_timeout):
                        self.logger.error(
                            "Named pipe listener did not become ready within %.1f seconds",
                            self.pipe_ready_timeout,
                        )
                        return False
                    self.logger.info("Named pipe listener is ready: %s", self.config.pipe_name)

                self.running = True
                self.logger.info("CODESYS process started and fully initialized")
                return True
            except Exception as exc:
                self.logger.error("Error starting CODESYS process: %s", str(exc))
                return False

    def stop(self) -> bool:
        with self.lock:
            if not self.is_running():
                self.logger.info("CODESYS process not running")
                return True

            try:
                self.logger.info("Stopping CODESYS process")
                self._write_termination_signal()

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
                self._remove_termination_signal()
                self.logger.info("CODESYS process stopped successfully")
                return True
            except Exception as exc:
                self.logger.error("Error stopping CODESYS process: %s", str(exc))
                return False

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def get_status(self) -> dict[str, object]:
        try:
            if not self.config.status_file.exists():
                return {"state": "unknown", "timestamp": self.now_fn()}

            payload = json.loads(self.config.status_file.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return cast(dict[str, object], payload)
            raise ValueError("Status payload must be a JSON object")
        except Exception as exc:
            self.logger.error("Error getting CODESYS status: %s", str(exc))
            return {"state": "error", "timestamp": self.now_fn(), "error": str(exc)}

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

    def _reset_runtime_files(self) -> None:
        if self.config.termination_signal_file.exists():
            self.config.termination_signal_file.unlink()

        if self.config.status_file.exists():
            try:
                self.config.status_file.unlink()
                self.logger.info("Removed existing status file")
            except Exception as exc:
                self.logger.warning("Could not remove existing status file: %s", str(exc))

    def _write_default_status(self, state: str) -> None:
        try:
            self.config.status_file.write_text(
                json.dumps({"state": state, "timestamp": self.now_fn()}),
                encoding="utf-8",
            )
        except Exception as exc:
            self.logger.error("Error creating default status file: %s", str(exc))

    def _write_termination_signal(self) -> None:
        try:
            self.config.termination_signal_file.write_text("TERMINATE", encoding="utf-8")
            self.logger.debug("Created termination signal file")
        except Exception as exc:
            self.logger.warning("Could not create termination signal file: %s", str(exc))

    def _remove_termination_signal(self) -> None:
        if not self.config.termination_signal_file.exists():
            return

        try:
            self.config.termination_signal_file.unlink()
        except Exception as exc:
            self.logger.warning("Could not remove termination signal file: %s", str(exc))

    def _log_failed_start(self) -> None:
        if self.process is None:
            return

        try:
            stdout, stderr = self.process.communicate(timeout=1)
            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else "No error output"
            stdout_text = stdout.decode("utf-8", errors="replace") if stdout else "No standard output"
            self.logger.error(
                "CODESYS process failed to start:\nStderr: %s\nStdout: %s",
                stderr_text,
                stdout_text,
            )
        except Exception as exc:
            self.logger.error("Error communicating with failed process: %s", str(exc))
