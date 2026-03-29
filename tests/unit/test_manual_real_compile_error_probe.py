from __future__ import annotations

import importlib.util
import io
import sys
from email.message import Message
from urllib import error
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_compile_error_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_compile_error_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_probe_env_sets_server_runtime_defaults() -> None:
    module = load_probe_module()

    result = module.build_probe_env(
        {"APPDATA": r"C:\Users\vboxuser\AppData\Roaming"},
        {"CODESYS_API_CODESYS_PATH": r"C:\demo\CODESYS.exe"},
        60123,
    )

    assert result["APPDATA"] == r"C:\Users\vboxuser\AppData\Roaming"
    assert result["CODESYS_API_CODESYS_PATH"] == r"C:\demo\CODESYS.exe"
    assert result["CODESYS_E2E_NO_UI"] == "0"
    assert result["CODESYS_API_CODESYS_NO_UI"] == "0"
    assert result["CODESYS_API_SERVER_HOST"] == "127.0.0.1"
    assert result["CODESYS_API_SERVER_PORT"] == "60123"
    assert result["CODESYS_API_TRANSPORT"] == "named_pipe"
    assert result["CODESYS_API_PIPE_NAME"] == "codesys_api_probe_60123"


def test_is_expected_compile_error_response_accepts_http_500_with_errors() -> None:
    module = load_probe_module()

    assert module.is_expected_compile_error_response(
        500,
        {
            "success": False,
            "message_counts": {"errors": 1, "warnings": 0, "infos": 0},
        },
    )


def test_is_expected_compile_error_response_rejects_non_error_payloads() -> None:
    module = load_probe_module()

    assert module.is_expected_compile_error_response(200, {"success": False}) is False
    assert module.is_expected_compile_error_response(
        500,
        {"success": False, "message_counts": {"errors": 0, "warnings": 0, "infos": 0}},
    ) is False
    assert module.is_expected_compile_error_response(500, {"success": True}) is False


def test_read_log_excerpt_filters_to_current_probe_window(tmp_path: Path) -> None:
    module = load_probe_module()
    appdata = tmp_path / "appdata"
    log_dir = appdata / "codesys-api" / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "codesys_api_server.log"
    log_file.write_text(
        "\n".join(
            [
                "2026-03-25 10:00:00,000 - codesys_api_server - INFO - old line",
                "2026-03-25 13:00:00,000 - codesys_api_server - INFO - current line",
            ]
        ),
        encoding="utf-8",
    )

    excerpt = module.read_log_excerpt({"APPDATA": str(appdata)}, max_lines=20, started_at=1774440000.0)

    assert "current line" in excerpt
    assert "old line" not in excerpt


def test_call_json_encodes_get_payload_into_query_string(monkeypatch: Any) -> None:
    module = load_probe_module()
    recorded: dict[str, object] = {}

    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"success": true}'

    def fake_urlopen(req: Any, timeout: int) -> Response:
        recorded["url"] = req.full_url
        recorded["data"] = req.data
        recorded["timeout"] = timeout
        return Response()

    monkeypatch.setattr(module.request, "urlopen", fake_urlopen)

    status_code, payload = module.call_json(
        "http://127.0.0.1:1234",
        "/api/v1/pou/list",
        method="GET",
        payload={"parentPath": "Application"},
        timeout=7,
    )

    assert status_code == 200
    assert payload == {"success": True}
    assert recorded["url"] == "http://127.0.0.1:1234/api/v1/pou/list?parentPath=Application"
    assert recorded["data"] is None
    assert recorded["timeout"] == 7


def test_call_json_wraps_non_json_http_error_body(monkeypatch: Any) -> None:
    module = load_probe_module()

    def fake_urlopen(req: Any, timeout: int) -> object:
        raise error.HTTPError(
            req.full_url,
            404,
            "Not Found",
            hdrs=Message(),
            fp=io.BytesIO(b"<!DOCTYPE HTML><html><body>Not Found</body></html>"),
        )

    monkeypatch.setattr(module.request, "urlopen", fake_urlopen)

    status_code, payload = module.call_json(
        "http://127.0.0.1:1234",
        "/api/v1/pou/list",
        method="GET",
        payload={"parentPath": "Application"},
        timeout=7,
    )

    assert status_code == 404
    assert payload["success"] is False
    assert payload["http_status"] == 404
    assert "Not Found" in str(payload["error"])
