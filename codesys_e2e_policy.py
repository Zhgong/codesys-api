from __future__ import annotations

from collections.abc import Mapping


DEFAULT_E2E_TRANSPORT = "named_pipe"
LEGACY_TRANSPORT = "file"
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def current_codesys_e2e_transport(env: Mapping[str, str]) -> str:
    return env.get("CODESYS_E2E_TRANSPORT", DEFAULT_E2E_TRANSPORT).strip().lower()


def current_codesys_e2e_transport_is_legacy(env: Mapping[str, str]) -> bool:
    return current_codesys_e2e_transport(env) == LEGACY_TRANSPORT


def legacy_file_full_track_enabled(env: Mapping[str, str]) -> bool:
    return env.get("CODESYS_E2E_FILE_FULL", "").strip().lower() in TRUTHY_VALUES
