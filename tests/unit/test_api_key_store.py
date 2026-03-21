from __future__ import annotations

import json
from pathlib import Path

from codesys_api.api_key_store import ApiKeyManager


def test_missing_key_file_bootstraps_default_admin_key(tmp_path: Path) -> None:
    key_file = tmp_path / "api_keys.json"

    manager = ApiKeyManager(key_file, now_fn=lambda: 123.0)

    assert manager.validate_key("admin") is True
    assert key_file.exists() is True
    payload = json.loads(key_file.read_text(encoding="utf-8"))
    assert payload["admin"]["name"] == "Admin"
    assert payload["admin"]["created"] == 123.0


def test_malformed_key_file_loads_as_empty_key_set(tmp_path: Path) -> None:
    key_file = tmp_path / "api_keys.json"
    key_file.write_text("{", encoding="utf-8")

    manager = ApiKeyManager(key_file)

    assert manager.validate_key("admin") is False


def test_validate_key_accepts_known_key_and_rejects_unknown_key(tmp_path: Path) -> None:
    key_file = tmp_path / "api_keys.json"
    key_file.write_text(
        json.dumps({"build-bot": {"name": "Build Bot", "created": 456.0}}),
        encoding="utf-8",
    )

    manager = ApiKeyManager(key_file)

    assert manager.validate_key("build-bot") is True
    assert manager.validate_key("admin") is False
