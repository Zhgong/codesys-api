from __future__ import annotations

import json
import threading
from http.server import HTTPServer
from typing import Any
from urllib import error, request

from codesys_api.action_layer import ActionResult, ActionType
from codesys_api.http_server import CodesysApiHandler


class FakeApiKeyManager:
    def validate_key(self, api_key: str) -> bool:
        return api_key == "admin"


class FakeActionService:
    def __init__(self, result: ActionResult) -> None:
        self.result = result
        self.requests: list[Any] = []

    def execute(self, action_request: Any) -> ActionResult:
        self.requests.append(action_request)
        return self.result


def test_project_compile_handler_returns_json_error_payload() -> None:
    compile_error_payload = {
        "success": False,
        "error": "Compilation completed with errors",
        "messages": [{"text": "C0032: MissingVar", "level": "error"}],
        "message_counts": {"errors": 1, "warnings": 0, "infos": 0},
    }
    actions_service = FakeActionService(
        ActionResult(body=compile_error_payload, status_code=500, request_id="compile-request")
    )

    def handler(*args: Any) -> CodesysApiHandler:
        return CodesysApiHandler(  # type: ignore[no-untyped-call]
            process_manager=None,
            script_executor=None,
            engine_adapter=None,
            api_key_manager=FakeApiKeyManager(),
            actions_service=actions_service,
            *args,
        )

    server = HTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        url = "http://127.0.0.1:{0}/api/v1/project/compile".format(server.server_address[1])
        req = request.Request(
            url,
            data=json.dumps({"clean_build": False}).encode("utf-8"),
            headers={
                "Authorization": "ApiKey admin",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            request.urlopen(req, timeout=5)
        except error.HTTPError as exc:
            response_payload = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 500
        else:
            raise AssertionError("Expected HTTP 500 compile error response")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    assert len(actions_service.requests) == 1
    recorded_request = actions_service.requests[0]
    assert recorded_request.action == ActionType.PROJECT_COMPILE
    assert recorded_request.params == {"clean_build": False}
    assert response_payload == compile_error_payload
