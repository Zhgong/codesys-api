from __future__ import annotations

from pathlib import Path


def test_http_server_uses_external_ironpython_adapter_only() -> None:
    source = Path("HTTP_SERVER.py").read_text(encoding="utf-8")

    assert "from ironpython_script_engine import IronPythonScriptEngineAdapter" in source
    assert "IronPythonScriptEngineAdapter(" in source
    assert "class ScriptGenerator:" not in source
    assert "class _LegacyScriptGenerator:" not in source
