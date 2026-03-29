from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "scripts" / "manual" / "run_real_codesys_e2e.py"


def load_runner_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_real_codesys_e2e", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_env_file_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    module = load_runner_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nCODESYS_API_CODESYS_PATH=C:\\demo\\CODESYS.exe\nCODESYS_E2E_ENABLE=1\n",
        encoding="utf-8",
    )

    result = module.load_env_file(env_file)

    assert result == {
        "CODESYS_API_CODESYS_PATH": r"C:\demo\CODESYS.exe",
        "CODESYS_E2E_ENABLE": "1",
    }


def test_build_runner_env_sets_real_e2e_defaults() -> None:
    module = load_runner_module()

    result = module.build_runner_env(
        {"APPDATA": r"C:\Users\vboxuser\AppData\Roaming"},
        {
            "APPDATA": r"C:\Users\vboxuser\Desktop\Repos\codesys-api\build\appdata_e2e",
            "CODESYS_API_CODESYS_PATH": "demo.exe",
        },
    )

    assert result["CODESYS_API_CODESYS_PATH"] == "demo.exe"
    assert result["APPDATA"] == r"C:\Users\vboxuser\AppData\Roaming"
    assert result["CODESYS_E2E_ENABLE"] == "1"
    assert result["CODESYS_E2E_NO_UI"] == "0"


def test_build_runner_env_preserves_explicit_no_ui_override() -> None:
    module = load_runner_module()

    result = module.build_runner_env(
        {"CODESYS_E2E_NO_UI": "1"},
        {
            "CODESYS_API_CODESYS_PATH": "demo.exe",
        },
    )

    assert result["CODESYS_E2E_NO_UI"] == "1"


def test_build_pytest_command_defaults_to_named_target_shape() -> None:
    module = load_runner_module()

    command = module.build_pytest_command("http-main", "python.exe")

    assert command == [
        "python.exe",
        "-m",
        "pytest",
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_main_flow",
        "-p",
        "no:cacheprovider",
    ]


def test_build_pytest_command_supports_compile_error_targets() -> None:
    module = load_runner_module()

    http_command = module.build_pytest_command("http-compile-error", "python.exe")
    cli_command = module.build_pytest_command("cli-compile-error", "python.exe")

    assert http_command == [
        "python.exe",
        "-m",
        "pytest",
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ]
    assert cli_command == [
        "python.exe",
        "-m",
        "pytest",
        "tests/e2e/codesys/test_real_codesys_cli.py",
        "-k",
        "test_real_codesys_cli_compile_detects_project_errors",
        "-p",
        "no:cacheprovider",
    ]


def test_is_sandbox_identity_detects_codex_sandbox() -> None:
    module = load_runner_module()

    assert module.is_sandbox_identity(r"WIN11\CodexSandboxOffline") is True
    assert module.is_sandbox_identity(r"WIN11\vboxuser") is False


def test_main_rejects_sandbox_identity(monkeypatch: Any, capsys: Any) -> None:
    module = load_runner_module()
    monkeypatch.setattr(module, "resolve_windows_identity", lambda: r"WIN11\CodexSandboxOffline")

    exit_code = module.main([])

    assert exit_code == 2
    assert "Refusing to run real CODESYS E2E from sandbox identity" in capsys.readouterr().err


def test_main_reports_missing_required_env_vars(monkeypatch: Any, capsys: Any, tmp_path: Path) -> None:
    module = load_runner_module()
    env_file = tmp_path / ".env.real-codesys.local"
    env_file.write_text("CODESYS_API_CODESYS_PATH=C:\\demo\\CODESYS.exe\n", encoding="utf-8")
    monkeypatch.setattr(module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.setattr(module, "resolve_windows_identity", lambda: r"WIN11\vboxuser")

    exit_code = module.main([])

    assert exit_code == 2
    assert "Missing required real CODESYS environment variables" in capsys.readouterr().err


def test_main_runs_selected_target(monkeypatch: Any, capsys: Any, tmp_path: Path) -> None:
    module = load_runner_module()
    env_file = tmp_path / ".env.real-codesys.local"
    env_file.write_text(
        "\n".join(
            [
                "CODESYS_API_CODESYS_PATH=C:\\demo\\CODESYS.exe",
                "CODESYS_API_CODESYS_PROFILE=Demo Profile",
                "CODESYS_API_CODESYS_PROFILE_PATH=C:\\demo\\Demo.profile.xml",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.setattr(module, "resolve_windows_identity", lambda: r"WIN11\vboxuser")

    recorded: dict[str, object] = {}

    class Completed:
        returncode = 0

    def fake_run(command: list[str], cwd: Path, env: dict[str, str], check: bool) -> Completed:
        recorded["command"] = command
        recorded["cwd"] = cwd
        recorded["env"] = env
        recorded["check"] = check
        return Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code = module.main(["--target", "cli-main", "--python", "python.exe"])

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert recorded["command"] == [
        "python.exe",
        "-m",
        "pytest",
        "tests/e2e/codesys/test_real_codesys_cli.py",
        "-k",
        "test_real_codesys_cli_main_flow",
        "-p",
        "no:cacheprovider",
    ]
    assert recorded["cwd"] == REPO_ROOT
    assert isinstance(recorded["env"], dict)
    assert recorded["env"]["CODESYS_E2E_ENABLE"] == "1"
    assert recorded["env"]["CODESYS_E2E_NO_UI"] == "0"
    assert "Windows identity: WIN11\\vboxuser" in stdout
    assert "Target: cli-main" in stdout
    assert "CODESYS_E2E_NO_UI=0" in stdout
