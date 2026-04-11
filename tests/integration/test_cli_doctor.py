from __future__ import annotations

import io
import json
from typing import cast

from codesys_api.action_layer import ActionRequest, ActionResult, ActionType
from codesys_api.cli_entry import ActionServiceLike, run_cli


class FakeActionService:
    def __init__(self, result: ActionResult) -> None:
        self.result = result
        self.requests: list[ActionRequest] = []

    def execute(self, request: ActionRequest) -> ActionResult:
        self.requests.append(request)
        return self.result


def test_cli_doctor_success_reports_all_checks_to_stdout() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "checks": [
                    {
                        "name": "Python dependency: requests",
                        "status": "PASS",
                        "detail": "Module is importable.",
                        "suggestion": "No action required.",
                    },
                    {
                        "name": "CODESYS binary",
                        "status": "PASS",
                        "detail": "Binary exists.",
                        "suggestion": "No action required.",
                    },
                ],
            }
        )
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["doctor"], action_service=cast(ActionServiceLike, service), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    output = stdout.getvalue()
    assert "[PASS] Python dependency: requests" in output
    assert "[PASS] CODESYS binary" in output
    assert stderr.getvalue() == ""
    assert service.requests[0].action == ActionType.SYSTEM_DOCTOR


def test_cli_doctor_partial_failure_routes_failures_to_stderr_and_returns_exit_1() -> None:
    service = FakeActionService(
        ActionResult(
            body={
                "success": True,
                "checks": [
                    {
                        "name": "Python dependency: requests",
                        "status": "PASS",
                        "detail": "Module is importable.",
                        "suggestion": "No action required.",
                    },
                    {
                        "name": "CODESYS path environment",
                        "status": "FAIL",
                        "detail": "CODESYS_API_CODESYS_PATH is missing.",
                        "suggestion": "Set CODESYS_API_CODESYS_PATH to CODESYS.exe.",
                    },
                    {
                        "name": "CODESYS binary",
                        "status": "WARN",
                        "detail": "Configured file name is unusual.",
                        "suggestion": "Double-check the configured executable path.",
                    },
                ],
            }
        )
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["doctor"], action_service=cast(ActionServiceLike, service), stdout=stdout, stderr=stderr)

    assert exit_code == 1
    assert "[PASS] Python dependency: requests" in stdout.getvalue()
    assert "[WARN] CODESYS binary" in stdout.getvalue()
    assert "[FAIL] CODESYS path environment" in stderr.getvalue()
    assert "Set CODESYS_API_CODESYS_PATH to CODESYS.exe." in stderr.getvalue()


def test_cli_doctor_json_mode_emits_raw_json_and_uses_fail_exit_code() -> None:
    body = {
        "success": True,
        "checks": [
            {
                "name": "Python dependency: win32api",
                "status": "FAIL",
                "detail": "Cannot import win32api.",
                "suggestion": "Install dependency: pip install pywin32",
            }
        ],
    }
    service = FakeActionService(ActionResult(body=body))
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["--json", "doctor"], action_service=cast(ActionServiceLike, service), stdout=stdout, stderr=stderr)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == body
    assert stderr.getvalue() == ""
