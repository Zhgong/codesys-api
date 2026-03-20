from __future__ import annotations

from pathlib import Path


def test_http_server_depends_on_runtime_transport_boundary() -> None:
    source = Path("HTTP_SERVER.py").read_text(encoding="utf-8")

    assert "from runtime_transport import build_runtime_transport" in source
    assert "from session_transport import build_primary_script_transport" not in source
    assert "from legacy_file_transport import build_legacy_file_transport" not in source
    assert "transport = build_runtime_transport(APP_CONFIG)" in source
