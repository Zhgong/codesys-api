from __future__ import annotations

from collections.abc import Mapping


DEFAULT_E2E_TRANSPORT = "named_pipe"
SUPPORTED_E2E_TRANSPORTS = frozenset({DEFAULT_E2E_TRANSPORT})


def current_codesys_e2e_transport(env: Mapping[str, str]) -> str:
    return env.get("CODESYS_E2E_TRANSPORT", DEFAULT_E2E_TRANSPORT).strip().lower()


def current_codesys_e2e_transport_is_supported(env: Mapping[str, str]) -> bool:
    return current_codesys_e2e_transport(env) in SUPPORTED_E2E_TRANSPORTS
