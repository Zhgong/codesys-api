from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

from codesys_e2e_policy import (
    current_codesys_e2e_transport,
    current_codesys_e2e_transport_is_supported,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_TIMEOUTS = {
    ("session", "start"): 180,
    ("session", "restart"): 180,
    ("session", "status"): 30,
    ("session", "stop"): 60,
    ("project", "create"): 180,
    ("project", "save"): 120,
    ("project", "list"): 60,
    ("project", "close"): 90,
    ("project", "compile"): 300,
    ("pou", "create"): 180,
    ("pou", "list"): 60,
    ("pou", "code"): 180,
}


def codesys_cli_env() -> dict[str, str]:
    if os.environ.get("CODESYS_E2E_ENABLE") != "1":
        pytest.skip("Set CODESYS_E2E_ENABLE=1 to run real CODESYS CLI tests")

    required = {
        "CODESYS_API_CODESYS_PATH": os.environ.get("CODESYS_API_CODESYS_PATH"),
        "CODESYS_API_CODESYS_PROFILE": os.environ.get("CODESYS_API_CODESYS_PROFILE"),
        "CODESYS_API_CODESYS_PROFILE_PATH": os.environ.get("CODESYS_API_CODESYS_PROFILE_PATH"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"Missing required real CODESYS environment variables: {', '.join(missing)}")

    if not current_codesys_e2e_transport_is_supported(os.environ):
        pytest.skip("Only named_pipe real E2E transport is supported in the current host-side runtime")

    env = os.environ.copy()
    env["CODESYS_API_CODESYS_NO_UI"] = os.environ.get("CODESYS_E2E_NO_UI", "false")
    env["CODESYS_API_TRANSPORT"] = current_codesys_e2e_transport(os.environ)
    env["CODESYS_API_PIPE_NAME"] = "codesys_api_cli_e2e_{0}".format(uuid.uuid4().hex)
    return env


def run_cli_json(env: dict[str, str], *args: str) -> tuple[int, dict[str, Any], str]:
    timeout = CLI_TIMEOUTS.get((args[0], args[1]), 120)
    completed = subprocess.run(
        [sys.executable, "codesys_cli.py", "--json", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = completed.stdout.strip()
    payload = json.loads(stdout) if stdout else {}
    return completed.returncode, payload, completed.stderr.strip()


@pytest.mark.codesys
@pytest.mark.codesys_main
def test_real_codesys_cli_main_flow() -> None:
    env = codesys_cli_env()
    project_path = str(Path(tempfile.gettempdir()) / f"codesys_cli_e2e_{uuid.uuid4().hex}.project")

    try:
        exit_code, payload, stderr = run_cli_json(env, "session", "start")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "project", "create", "--path", project_path)
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True
        assert payload["project"]["path"] == project_path

        exit_code, payload, stderr = run_cli_json(
            env,
            "pou",
            "create",
            "--name",
            "MotorController",
            "--type",
            "FunctionBlock",
            "--language",
            "ST",
        )
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "pou", "list")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True
        assert any(str(pou.get("name", "")) == "PLC_PRG" for pou in payload["pous"])
        assert any(str(pou.get("name", "")) == "MotorController" for pou in payload["pous"])

        exit_code, payload, stderr = run_cli_json(env, "project", "save")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "project", "compile")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True
        assert payload["message_counts"]["errors"] == 0
        assert payload["build_type"] == "build+generate_code"

        exit_code, payload, stderr = run_cli_json(env, "project", "close")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "session", "restart")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "project", "list")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True
        assert isinstance(payload["projects"], list)
    finally:
        run_cli_json(env, "project", "close")
        run_cli_json(env, "session", "stop")


@pytest.mark.codesys
@pytest.mark.codesys_slow
def test_real_codesys_cli_compile_detects_project_errors() -> None:
    env = codesys_cli_env()
    project_path = str(Path(tempfile.gettempdir()) / f"codesys_cli_error_{uuid.uuid4().hex}.project")
    implementation_file = Path(tempfile.gettempdir()) / f"codesys_cli_impl_{uuid.uuid4().hex}.txt"
    implementation_file.write_text(
        "MissingVar := TRUE;",
        encoding="utf-8",
    )

    try:
        exit_code, payload, stderr = run_cli_json(env, "session", "start")
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "project", "create", "--path", project_path)
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(
            env,
            "pou",
            "code",
            "--path",
            "Application/PLC_PRG",
            "--implementation-file",
            str(implementation_file),
        )
        assert exit_code == 0
        assert stderr == ""
        assert payload["success"] is True

        exit_code, payload, stderr = run_cli_json(env, "project", "compile")
        assert exit_code == 1
        assert stderr == ""
        assert payload["success"] is False
        assert payload["message_counts"]["errors"] > 0
        assert any("MissingVar" in str(message.get("text", "")) for message in payload["messages"])
    finally:
        run_cli_json(env, "project", "close")
        run_cli_json(env, "session", "stop")
        if implementation_file.exists():
            implementation_file.unlink()
