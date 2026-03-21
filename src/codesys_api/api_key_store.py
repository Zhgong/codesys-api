from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, TypedDict, cast


NowFn = Callable[[], float]


class ApiKeyMetadata(TypedDict):
    name: str
    created: float


class ApiKeyManager:
    def __init__(self, key_file_path: Path | str, now_fn: NowFn = time.time) -> None:
        self.key_file_path = Path(key_file_path)
        self.now_fn = now_fn
        self.keys = self._load_keys()

    def _load_keys(self) -> dict[str, ApiKeyMetadata]:
        if not self.key_file_path.exists():
            keys: dict[str, ApiKeyMetadata] = {
                "admin": {"name": "Admin", "created": self.now_fn()}
            }
            self._save_keys(keys)
            return keys

        try:
            payload = json.loads(self.key_file_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return cast(dict[str, ApiKeyMetadata], payload)
        except Exception:
            return {}

        return {}

    def _save_keys(self, keys: dict[str, ApiKeyMetadata]) -> None:
        self.key_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_file_path.write_text(json.dumps(keys), encoding="utf-8")

    def validate_key(self, key: str) -> bool:
        return key in self.keys
