from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTEST_BASETEMP = Path(r"C:\Users\vboxuser\Desktop\pytest_manual_root")


def run_step(title: str, command: list[str]) -> None:
    print(f"== {title} ==")
    completed = subprocess.run(command, cwd=REPO_ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    PYTEST_BASETEMP.mkdir(parents=True, exist_ok=True)

    run_step(
        "pytest",
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--basetemp",
            str(PYTEST_BASETEMP),
        ],
    )
    run_step(
        "mypy",
        [
            sys.executable,
            "-m",
            "mypy",
        ],
    )
    run_step(
        "py_compile",
        [
            sys.executable,
            "-c",
            (
                "import py_compile; "
                "files = ["
                "'_repo_bootstrap.py','HTTP_SERVER.py','codesys_cli.py','scripts/dev/test_server.py','scripts/build_release.py',"
                "'src/codesys_api/__init__.py','src/codesys_api/action_layer.py',"
                "'src/codesys_api/api_key_store.py','src/codesys_api/app_runtime.py',"
                "'src/codesys_api/codesys_e2e_policy.py','src/codesys_api/codesys_process.py',"
                "'src/codesys_api/engine_adapter.py','src/codesys_api/ironpython_script_engine.py',"
                "'src/codesys_api/named_pipe_transport.py','src/codesys_api/runtime_transport.py',"
                "'src/codesys_api/script_executor.py','src/codesys_api/server_config.py',"
                "'src/codesys_api/server_logic.py','src/codesys_api/session_transport.py',"
                "'src/codesys_api/transport_result.py',"
                "'tests/e2e/codesys/test_real_codesys_cli.py'"
                "]; "
                "[py_compile.compile(path, doraise=True) for path in files]; "
                "print('py_compile ok')"
            ),
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
