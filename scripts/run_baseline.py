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
                "'HTTP_SERVER.py','action_layer.py','api_key_store.py','app_runtime.py',"
                "'codesys_cli.py','codesys_e2e_policy.py','codesys_process.py',"
                "'engine_adapter.py','ironpython_script_engine.py','runtime_transport.py',"
                "'script_executor.py','server_config.py','server_logic.py','test_server.py',"
                "'named_pipe_transport.py','transport_result.py',"
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
