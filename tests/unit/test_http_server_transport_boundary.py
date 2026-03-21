from __future__ import annotations

from pathlib import Path


def test_http_server_depends_on_runtime_transport_boundary() -> None:
    source = Path("src/codesys_api/http_server.py").read_text(encoding="utf-8")

    assert "from .app_runtime import build_app_runtime" in source
    assert "from .session_transport import build_primary_script_transport" not in source
    assert "from .runtime_transport import build_runtime_transport" not in source
    assert "build_runtime_transport(APP_CONFIG)" not in source
