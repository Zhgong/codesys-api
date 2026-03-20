from __future__ import annotations

from codesys_e2e_policy import (
    current_codesys_e2e_transport,
    current_codesys_e2e_transport_is_supported,
)


def test_current_codesys_e2e_transport_defaults_to_named_pipe() -> None:
    assert current_codesys_e2e_transport({}) == "named_pipe"


def test_current_codesys_e2e_transport_normalizes_case_and_whitespace() -> None:
    assert current_codesys_e2e_transport({"CODESYS_E2E_TRANSPORT": " named_pipe "}) == "named_pipe"


def test_current_codesys_e2e_transport_is_supported_tracks_named_pipe_only() -> None:
    assert current_codesys_e2e_transport_is_supported({}) is True
    assert current_codesys_e2e_transport_is_supported({"CODESYS_E2E_TRANSPORT": "named_pipe"}) is True
    assert current_codesys_e2e_transport_is_supported({"CODESYS_E2E_TRANSPORT": "file"}) is False
