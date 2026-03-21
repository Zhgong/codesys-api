from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
DEFAULT_DATA_DIR_NAME = "codesys-api"


def packaged_persistent_script() -> Path:
    return ASSETS_DIR / "PERSISTENT_SESSION.py"


def packaged_script_lib_dir() -> Path:
    return ASSETS_DIR / "ScriptLib"


def default_user_data_dir(env: Mapping[str, str]) -> Path:
    appdata = env.get("APPDATA")
    if appdata:
        return Path(appdata) / DEFAULT_DATA_DIR_NAME
    return Path.home() / "AppData" / "Roaming" / DEFAULT_DATA_DIR_NAME


def default_api_key_file(env: Mapping[str, str]) -> Path:
    return default_user_data_dir(env) / "api_keys.json"


def default_runtime_log_dir(env: Mapping[str, str]) -> Path:
    return default_user_data_dir(env) / "logs"
