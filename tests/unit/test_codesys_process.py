from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from codesys_process import CodesysProcessManager, ProcessManagerConfig


class FakeProcess:
    def __init__(self, poll_results: list[int | None] | None = None) -> None:
        self.poll_results = poll_results or [None]
        self.poll_index = 0
        self.terminate_called = False
        self.kill_called = False

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
        status_file=tmp_path / "session_status.json",
        termination_signal_file=tmp_path / "terminate.signal",
        log_file=tmp_path / "logs" / "session.log",
        script_lib_dir=tmp_path / "ScriptLib",
        profile_name="CODESYS V3.5 SP20 Patch 5",
        profile_path=tmp_path / "Profiles" / "CODESYS V3.5 SP20 Patch 5.profile.xml",
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


def test_start_creates_default_status_file_after_successful_launch(tmp_path: Path) -> None:
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
    )

    assert manager.start() is True
    assert config.status_file.exists() is True
    payload = json.loads(config.status_file.read_text(encoding="utf-8"))
    assert payload["state"] == "initialized"


def test_start_returns_false_when_profile_configuration_is_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config = ProcessManagerConfig(
        codesys_path=config.codesys_path,
        script_path=config.script_path,
        status_file=config.status_file,
        termination_signal_file=config.termination_signal_file,
        log_file=config.log_file,
        script_lib_dir=config.script_lib_dir,
        profile_name=None,
        profile_path=None,
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
        status_file=base.status_file,
        termination_signal_file=base.termination_signal_file,
        log_file=base.log_file,
        script_lib_dir=base.script_lib_dir,
        profile_name=base.profile_name,
        profile_path=base.profile_path,
        no_ui=False,
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


def test_stop_uses_terminate_and_kill_when_process_stays_running(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    process = FakeProcess([None, None, None, None, None, None])
    manager = CodesysProcessManager(
        config,
        logger=logging.getLogger("codesys_process_test"),
        sleep_fn=lambda _seconds: None,
        stop_timeout=0.0,
        post_terminate_wait=0.0,
    )
    manager.process = process
    manager.running = True

    assert manager.stop() is True
    assert process.terminate_called is True
    assert process.kill_called is True
    assert manager.process is None
    assert config.termination_signal_file.exists() is False


def test_get_status_returns_unknown_when_status_file_is_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))

    status = manager.get_status()

    assert status["state"] == "unknown"


def test_get_status_returns_error_when_status_file_is_invalid_json(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.status_file.write_text("{", encoding="utf-8")
    manager = CodesysProcessManager(config, logger=logging.getLogger("codesys_process_test"))

    status = manager.get_status()

    assert status["state"] == "error"
    assert "error" in status
