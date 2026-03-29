from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ENV_FILE = REPO_ROOT / ".env.real-codesys.local"
REQUIRED_ENV_VARS = (
    "CODESYS_API_CODESYS_PATH",
    "CODESYS_API_CODESYS_PROFILE",
    "CODESYS_API_CODESYS_PROFILE_PATH",
)
TARGET_COMMANDS: dict[str, list[str]] = {
    "http-main": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_main_flow",
        "-p",
        "no:cacheprovider",
    ],
    "http-all": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-m",
        "codesys",
        "-p",
        "no:cacheprovider",
    ],
    "http-compile-error": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "http-last8": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_project_create_requires_no_active_project or test_real_codesys_restart_keeps_session_usable or test_real_codesys_stop_is_repeatable or test_real_codesys_start_is_repeatable or test_real_codesys_compile_without_active_project_fails_cleanly or test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "http-last5": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_start_is_repeatable or test_real_codesys_compile_without_active_project_fails_cleanly or test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "http-last6": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_stop_is_repeatable or test_real_codesys_start_is_repeatable or test_real_codesys_compile_without_active_project_fails_cleanly or test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "http-last7": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_restart_keeps_session_usable or test_real_codesys_stop_is_repeatable or test_real_codesys_start_is_repeatable or test_real_codesys_compile_without_active_project_fails_cleanly or test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "http-compile-3": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_compile_without_active_project_fails_cleanly or test_real_codesys_compile_detects_errors or test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "http-compile-detect": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_compile_detects_errors",
        "-p",
        "no:cacheprovider",
    ],
    "http-compile-succeed": [
        "tests/e2e/codesys/test_real_codesys_e2e.py",
        "-k",
        "test_real_codesys_compile_succeeds_with_valid_project",
        "-p",
        "no:cacheprovider",
    ],
    "cli-main": [
        "tests/e2e/codesys/test_real_codesys_cli.py",
        "-k",
        "test_real_codesys_cli_main_flow",
        "-p",
        "no:cacheprovider",
    ],
    "cli-all": [
        "tests/e2e/codesys/test_real_codesys_cli.py",
        "-m",
        "codesys",
        "-p",
        "no:cacheprovider",
    ],
    "cli-compile-error": [
        "tests/e2e/codesys/test_real_codesys_cli.py",
        "-k",
        "test_real_codesys_cli_compile_detects_project_errors",
        "-p",
        "no:cacheprovider",
    ],
    "http-pipe-stress": [
        "tests/e2e/codesys/test_pipe_stress.py",
        "-m",
        "codesys",
        "-p",
        "no:cacheprovider",
    ],
    "http-pipe-stress-roundtrips": [
        "tests/e2e/codesys/test_pipe_stress.py",
        "-k",
        "test_pipe_stress_repeated_roundtrips",
        "-p",
        "no:cacheprovider",
    ],
    "http-pipe-stress-lifecycles": [
        "tests/e2e/codesys/test_pipe_stress.py",
        "-k",
        "test_pipe_stress_repeated_lifecycles",
        "-p",
        "no:cacheprovider",
    ],
}


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


def resolve_windows_identity() -> str:
    try:
        completed = subprocess.run(
            ["whoami"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        completed = None

    if completed is not None:
        identity = completed.stdout.strip()
        if identity:
            return identity

    userdomain = os.environ.get("USERDOMAIN", "")
    username = os.environ.get("USERNAME", "")
    combined = "{0}\\{1}".format(userdomain, username).strip("\\")
    return combined or "unknown"


def is_sandbox_identity(identity: str) -> bool:
    return "codexsandboxoffline" in identity.lower()


def build_runner_env(base_env: Mapping[str, str], file_env: Mapping[str, str]) -> dict[str, str]:
    merged = dict(base_env)
    for name, value in file_env.items():
        if name == "APPDATA":
            continue
        merged[name] = value
    merged.setdefault("CODESYS_E2E_ENABLE", "1")
    # Real E2E defaults to UI mode because noUI compile currently needs a mode-switch fallback
    # that can leave the project locked during runtime restoration.
    merged.setdefault("CODESYS_E2E_NO_UI", "0")
    return merged


def missing_required_env_vars(env: Mapping[str, str]) -> list[str]:
    return [name for name in REQUIRED_ENV_VARS if not env.get(name)]


def build_pytest_command(target: str, python_executable: str) -> list[str]:
    return [python_executable, "-m", "pytest", *TARGET_COMMANDS[target]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run real CODESYS E2E tests from a normal Windows user terminal.",
    )
    parser.add_argument(
        "--target",
        choices=sorted(TARGET_COMMANDS),
        default="http-main",
        help="Named real-CODESYS validation target",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to launch pytest",
    )
    return parser


def _print_context(identity: str, target: str, env: Mapping[str, str], command: Sequence[str]) -> None:
    print("Windows identity: {0}".format(identity))
    print("Target: {0}".format(target))
    for name in REQUIRED_ENV_VARS:
        print("{0}={1}".format(name, env.get(name, "")))
    print("CODESYS_E2E_ENABLE={0}".format(env.get("CODESYS_E2E_ENABLE", "")))
    print("CODESYS_E2E_NO_UI={0}".format(env.get("CODESYS_E2E_NO_UI", "")))
    print("Command: {0}".format(subprocess.list2cmdline(list(command))))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = resolve_windows_identity()
    if is_sandbox_identity(identity):
        print(
            "Refusing to run real CODESYS E2E from sandbox identity '{0}'. "
            "Use a normal Windows user terminal or a non-sandbox elevated runner.".format(identity),
            file=sys.stderr,
        )
        return 2

    if not LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    try:
        file_env = load_env_file(LOCAL_ENV_FILE)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    runner_env = build_runner_env(os.environ, file_env)
    missing = missing_required_env_vars(runner_env)
    if missing:
        print(
            "Missing required real CODESYS environment variables: {0}".format(", ".join(missing)),
            file=sys.stderr,
        )
        return 2

    command = build_pytest_command(args.target, args.python)
    _print_context(identity, args.target, runner_env, command)

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=runner_env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
