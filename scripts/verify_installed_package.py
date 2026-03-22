from __future__ import annotations

import argparse
import shutil
import subprocess
import venv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_ENV = REPO_ROOT / "build" / "published_package_verify"
PACKAGE_NAME = "codesys-tools"
TESTPYPI_INDEX = "https://test.pypi.org/simple/"
PYPI_INDEX = "https://pypi.org/simple/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install and verify a published or local codesys-tools package in a clean virtual environment.",
    )
    parser.add_argument("--target", choices=["wheel", "testpypi", "pypi"], required=True)
    parser.add_argument("--version", help="Published package version to install from TestPyPI or PyPI.")
    parser.add_argument("--wheel-path", help="Local wheel path to install when --target=wheel.")
    return parser


def run_step(title: str, command: list[str], *, cwd: Path | None = None) -> None:
    print(f"== {title} ==")
    completed = subprocess.run(command, cwd=cwd or REPO_ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _venv_python() -> Path:
    return VERIFY_ENV / "Scripts" / "python.exe"


def _venv_script(name: str) -> Path:
    return VERIFY_ENV / "Scripts" / name


def _create_clean_venv() -> None:
    if VERIFY_ENV.exists():
        shutil.rmtree(VERIFY_ENV)
    venv.create(VERIFY_ENV, with_pip=True)


def _install_command(args: argparse.Namespace) -> list[str]:
    if args.target == "wheel":
        if not args.wheel_path:
            raise SystemExit("--wheel-path is required when --target=wheel")
        return [
            str(_venv_python()),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            args.wheel_path,
        ]

    if not args.version:
        raise SystemExit("--version is required when verifying a published package")

    requirement = f"{PACKAGE_NAME}=={args.version}"
    command = [str(_venv_python()), "-m", "pip", "install", "--no-cache-dir"]
    if args.target == "testpypi":
        command.extend(
            [
                "-i",
                TESTPYPI_INDEX,
                "--extra-index-url",
                PYPI_INDEX,
                requirement,
            ]
        )
        return command

    command.append(requirement)
    return command


def _validate_installed_assets() -> None:
    probe = (
        "from codesys_api.runtime_paths import packaged_persistent_script, packaged_script_lib_dir; "
        "p = packaged_persistent_script(); "
        "d = packaged_script_lib_dir(); "
        "print(p); print(p.exists()); print(d); print(d.exists())"
    )
    run_step("asset lookup", [str(_venv_python()), "-c", probe])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _create_clean_venv()
    run_step("upgrade pip", [str(_venv_python()), "-m", "pip", "install", "--upgrade", "pip"])
    run_step("install package", _install_command(args))
    run_step("codesys-tools --help", [str(_venv_script("codesys-tools.exe")), "--help"])
    run_step("codesys-tools-server --help", [str(_venv_script("codesys-tools-server.exe")), "--help"])
    _validate_installed_assets()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
