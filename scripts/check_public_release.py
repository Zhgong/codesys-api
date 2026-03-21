from __future__ import annotations

import subprocess
import sys
import shutil
import venv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WHEEL_SMOKE_ENV = REPO_ROOT / "build" / "public_release_smoke"
README_PATH = REPO_ROOT / "README.md"
PUBLIC_RELEASE_DOC = REPO_ROOT / "docs" / "PUBLIC_RELEASE.md"
INSTALLATION_GUIDE = REPO_ROOT / "docs" / "INSTALLATION_GUIDE.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def run_step(title: str, command: list[str], *, cwd: Path | None = None) -> None:
    print(f"== {title} ==")
    completed = subprocess.run(command, cwd=cwd or REPO_ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def assert_contains(path: Path, expected: str) -> None:
    content = path.read_text(encoding="utf-8")
    if expected not in content:
        raise SystemExit(f"Missing required text in {path}: {expected}")


def _wheel_path() -> Path:
    wheels = sorted((REPO_ROOT / "dist").glob("codesys_tools-*.whl"))
    if not wheels:
        raise SystemExit(r"No wheel found under dist/. Run python scripts\build_release.py first.")
    return wheels[-1]


def _venv_python() -> Path:
    return WHEEL_SMOKE_ENV / "Scripts" / "python.exe"


def _venv_script(name: str) -> Path:
    return WHEEL_SMOKE_ENV / "Scripts" / name


def _create_clean_venv() -> None:
    if WHEEL_SMOKE_ENV.exists():
        shutil.rmtree(WHEEL_SMOKE_ENV)
    venv.create(WHEEL_SMOKE_ENV, with_pip=True)


def _validate_public_docs() -> None:
    assert_contains(README_PATH, "codesys-tools")
    assert_contains(README_PATH, "Windows-only")
    assert_contains(README_PATH, "experimental")
    assert_contains(README_PATH, "local CODESYS")
    assert_contains(README_PATH, "named_pipe")
    assert_contains(PUBLIC_RELEASE_DOC, r"python scripts\check_public_release.py")
    assert_contains(INSTALLATION_GUIDE, "codesys --help")
    assert_contains(INSTALLATION_GUIDE, "codesys-server --help")
    assert_contains(PYPROJECT_PATH, 'name = "codesys-tools"')
    assert_contains(PYPROJECT_PATH, 'Homepage = "https://github.com/Zhgong/codesys-api"')
    assert_contains(PYPROJECT_PATH, 'Development Status :: 3 - Alpha')


def _validate_installed_assets() -> None:
    probe = (
        "from codesys_api.runtime_paths import packaged_persistent_script, packaged_script_lib_dir; "
        "p = packaged_persistent_script(); "
        "d = packaged_script_lib_dir(); "
        "print(p); print(p.exists()); print(d); print(d.exists())"
    )
    run_step("asset lookup", [str(_venv_python()), "-c", probe])


def main() -> int:
    _validate_public_docs()
    run_step("baseline", [sys.executable, r"scripts\run_baseline.py"])
    run_step("build", [sys.executable, r"scripts\build_release.py"])

    _create_clean_venv()
    run_step("upgrade pip", [str(_venv_python()), "-m", "pip", "install", "--upgrade", "pip"])
    run_step("install wheel", [str(_venv_python()), "-m", "pip", "install", str(_wheel_path())])
    run_step("codesys --help", [str(_venv_script("codesys.exe")), "--help"])
    run_step("codesys-server --help", [str(_venv_script("codesys-server.exe")), "--help"])
    _validate_installed_assets()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
