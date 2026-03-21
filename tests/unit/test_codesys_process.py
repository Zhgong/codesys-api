from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from codesys_api.codesys_process import CodesysProcessManager, ProcessManagerConfig


class FakeProcess:
    def __init__(
        self,
        poll_results: list[int | None] | None = None,
        *,
        stdout_lines: list[bytes] | None = None,
        stderr_lines: list[bytes] | None = None,
    ) -> None:
        self.poll_results = poll_results or [None]
        self.poll_index = 0
        self.terminate_called = False
        self.kill_called = False
        self.stdout = FakeStream(stdout_lines or [])
        self.stderr = FakeStream(stderr_lines or [])

    def poll(self) -> int | None:
        if self.poll_index < len(self.poll_results):
            result = self.poll_results[self.poll_index]
            self.poll_index += 1
            return result
        return self.poll_results[-1]

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        return (b"", b"")

    def terminate(self) -> None:
        self.terminate_called = True

    def kill(self) -> None:
        self.kill_called = True


class FakeStream:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = list(lines)

    def readline(self) -> bytes:
        if self.lines:
            return self.lines.pop(0)
        return b""


class FakePopenFactory:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.called = False
        self.command: str | None = None
        self.kwargs: dict[str, Any] | None = None

    def __call__(self, command: str, **kwargs: Any) -> FakeProcess:
        self.called = True
        self.command = command
        self.kwargs = kwargs
        return self.process


def make_config(tmp_path: Path) -> ProcessManagerConfig:
    return ProcessManagerConfig(
        codesys_path=tmp_path / "CODESYS.exe",
        script_path=tmp_path / "PERSISTENT_SESSION.py",
        script_lib_dir=tmp_path / "ScriptLib",
        profile_name="CODESYS V3.5 SP20 Patch 5",
        profile_path=tmp_path / "Profiles" / "CODESYS V3.5 SP20 Patch 5.profile.xml",
        transport_name="named_pipe",
        pipe_name="codesys_api_test_pipe",
    )


def test_start_returns_false_when_codesys_executable_is_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.script_path.write_text("# script", encoding="utf-8")
    assert config.profile_path is not None
    config.profile_path.parent.mkdir(parents=True, exist_ok=True)
    config.profile_path.write_text("<Profile />", encoding="utf-8")
    config.script_lib_dir.mkdir()
    popen_factory = FakePopenFactory(FakeProcess())
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        popen_factory=popen_factory,
        sleep_fn=lambda _seconds: None,
        startup_timeout=0.0,
        initialization_wait=0.0,
    )

    assert manager.start() is False
    assert popen_factory.called is False


def test_start_succeeds_after_successful_launch(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.codesys_path.write_text("exe", encoding="utf-8")
    config.script_path.write_text("# script", encoding="utf-8")
    assert config.profile_path is not None
    config.profile_path.parent.mkdir(parents=True, exist_ok=True)
    config.profile_path.write_text("<Profile />", encoding="utf-8")
    config.script_lib_dir.mkdir()
    process = FakeProcess([None, None])
    popen_factory = FakePopenFactory(process)
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        popen_factory=popen_factory,
        sleep_fn=lambda _seconds: None,
        startup_timeout=0.0,
        initialization_wait=0.0,
        pipe_ready_fn=lambda _pipe_name, _timeout: True,
    )

    assert manager.start() is True
    assert manager.is_running() is True


def test_start_waits_for_named_pipe_listener_when_named_pipe_transport_is_enabled(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.codesys_path.write_text("exe", encoding="utf-8")
    config.script_path.write_text("# script", encoding="utf-8")
    assert config.profile_path is not None
    config.profile_path.parent.mkdir(parents=True, exist_ok=True)
    config.profile_path.write_text("<Profile />", encoding="utf-8")
    config.script_lib_dir.mkdir()
    process = FakeProcess([None, None])
    popen_factory = FakePopenFactory(process)
    calls: list[tuple[str, float]] = []

    def record_pipe_ready(pipe_name: str, timeout: float) -> bool:
        calls.append((pipe_name, timeout))
        return True

    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        popen_factory=popen_factory,
        sleep_fn=lambda _seconds: None,
        startup_timeout=0.0,
        initialization_wait=0.0,
        pipe_ready_timeout=5.0,
        pipe_ready_fn=record_pipe_ready,
    )

    assert manager.start() is True
    assert calls == [("codesys_api_test_pipe", 5.0)]


def test_start_returns_false_when_named_pipe_listener_never_becomes_ready(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.codesys_path.write_text("exe", encoding="utf-8")
    config.script_path.write_text("# script", encoding="utf-8")
    assert config.profile_path is not None
    config.profile_path.parent.mkdir(parents=True, exist_ok=True)
    config.profile_path.write_text("<Profile />", encoding="utf-8")
    config.script_lib_dir.mkdir()
    process = FakeProcess([None, None])
    popen_factory = FakePopenFactory(process)
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        popen_factory=popen_factory,
        sleep_fn=lambda _seconds: None,
        startup_timeout=0.0,
        initialization_wait=0.0,
        pipe_ready_timeout=5.0,
        pipe_ready_fn=lambda _pipe_name, _timeout: False,
    )

    assert manager.start() is False


def test_start_returns_false_when_profile_configuration_is_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config = ProcessManagerConfig(
        codesys_path=config.codesys_path,
        script_path=config.script_path,
        script_lib_dir=config.script_lib_dir,
        profile_name=None,
        profile_path=None,
        transport_name=config.transport_name,
        pipe_name=config.pipe_name,
    )
    config.codesys_path.write_text("exe", encoding="utf-8")
    config.script_path.write_text("# script", encoding="utf-8")
    config.script_lib_dir.mkdir()
    popen_factory = FakePopenFactory(FakeProcess())
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        popen_factory=popen_factory,
        sleep_fn=lambda _seconds: None,
        startup_timeout=0.0,
        initialization_wait=0.0,
    )

    assert manager.start() is False
    assert popen_factory.called is False


def test_build_launch_command_includes_profile_and_no_ui(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))

    command = manager._build_launch_command()

    assert "--profile=\"CODESYS V3.5 SP20 Patch 5\"" in command
    assert "--noUI" in command
    assert f"--runscript=\"{config.script_path}\"" in command


def test_build_launch_command_omits_no_ui_when_disabled(tmp_path: Path) -> None:
    base = make_config(tmp_path)
    config = ProcessManagerConfig(
        codesys_path=base.codesys_path,
        script_path=base.script_path,
        script_lib_dir=base.script_lib_dir,
        profile_name=base.profile_name,
        profile_path=base.profile_path,
        no_ui=False,
        transport_name=base.transport_name,
        pipe_name=base.pipe_name,
    )
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))

    command = manager._build_launch_command()

    assert "--noUI" not in command


def test_build_launch_command_uses_runtime_no_ui_override(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))
    manager.set_no_ui_mode(False)

    command = manager._build_launch_command()

    assert "--noUI" not in command


def test_reset_runtime_mode_restores_configured_no_ui_mode(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))
    manager.set_no_ui_mode(False)

    manager.reset_runtime_mode()

    assert manager.is_no_ui_mode() is True
    assert "--noUI" in manager._build_launch_command()


def test_stop_requests_graceful_named_pipe_shutdown_before_fallback(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    process = FakeProcess([None, 0])
    calls: list[tuple[str, int]] = []

    def record_shutdown(pipe_name: str, timeout: int) -> dict[str, object]:
        calls.append((pipe_name, timeout))
        return {"success": True}

    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        sleep_fn=lambda _seconds: None,
        stop_timeout=1.0,
        shutdown_request_fn=record_shutdown,
    )
    manager.process = process
    manager.running = True

    assert manager.stop() is True
    assert calls == [("codesys_api_test_pipe", 1)]
    assert process.terminate_called is False
    assert process.kill_called is False


def test_stop_uses_terminate_and_kill_when_process_stays_running(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    process = FakeProcess([None, None, None, None, None, None])
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        sleep_fn=lambda _seconds: None,
        stop_timeout=0.0,
        post_terminate_wait=0.0,
        shutdown_request_fn=lambda _pipe_name, _timeout: {"success": False, "error": "no response"},
    )
    manager.process = process
    manager.running = True

    assert manager.stop() is True
    assert process.terminate_called is True
    assert process.kill_called is True
    assert manager.process is None


def test_get_status_returns_unknown_when_process_is_not_running(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))

    status = manager.get_status()

    assert status["state"] == "unknown"


def test_get_status_returns_running_when_process_is_running(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))
    manager.process = FakeProcess([None])

    status = manager.get_status()

    assert status["state"] == "running"


def test_start_captures_process_stdout_and_stderr_into_log_buffer(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.codesys_path.write_text("exe", encoding="utf-8")
    config.script_path.write_text("# script", encoding="utf-8")
    assert config.profile_path is not None
    config.profile_path.parent.mkdir(parents=True, exist_ok=True)
    config.profile_path.write_text("<Profile />", encoding="utf-8")
    config.script_lib_dir.mkdir()
    process = FakeProcess(
        ([None] * 20) + [0],
        stdout_lines=[b"[2026-03-20 10:00:00] Initializing\n"],
        stderr_lines=[b"warning line\n"],
    )
    popen_factory = FakePopenFactory(process)
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        popen_factory=popen_factory,
        sleep_fn=lambda _seconds: time.sleep(0.01),
        startup_timeout=0.0,
        initialization_wait=0.0,
        pipe_ready_fn=lambda _pipe_name, _timeout: True,
    )

    assert manager.start() is True
    time.sleep(0.05)

    logs = manager.get_log_lines()

    assert any("STDOUT: [2026-03-20 10:00:00] Initializing" in line for line in logs)
    assert any("STDERR: warning line" in line for line in logs)


def test_log_buffer_discards_oldest_lines_when_capacity_is_reached(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        log_buffer_capacity=2,
    )

    manager._append_log_line("one\n")
    manager._append_log_line("two\n")
    manager._append_log_line("three\n")

    assert manager.get_log_lines() == ["two\n", "three\n"]


def test_stop_joins_output_threads_after_process_shutdown(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    process = FakeProcess([None, 0])
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        sleep_fn=lambda _seconds: None,
        shutdown_request_fn=lambda _pipe_name, _timeout: {"success": True},
    )
    manager.process = process
    manager.running = True
    manager.output_threads = [threading.Thread(target=lambda: None)]
    manager.output_threads[0].start()

    assert manager.stop() is True
    assert manager.output_threads == []
