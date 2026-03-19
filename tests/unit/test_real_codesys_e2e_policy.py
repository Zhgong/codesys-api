from __future__ import annotations

from codesys_e2e_policy import (
    current_codesys_e2e_transport,
    current_codesys_e2e_transport_is_legacy,
    legacy_file_full_track_enabled,
)


def test_current_codesys_e2e_transport_defaults_to_named_pipe() -> None:
    assert current_codesys_e2e_transport({}) == "named_pipe"


def test_current_codesys_e2e_transport_normalizes_case_and_whitespace() -> None:
    assert current_codesys_e2e_transport({"CODESYS_E2E_TRANSPORT": " FILE "}) == "file"


def test_current_codesys_e2e_transport_is_legacy_tracks_file_only() -> None:
    assert current_codesys_e2e_transport_is_legacy({}) is False
    assert current_codesys_e2e_transport_is_legacy({"CODESYS_E2E_TRANSPORT": "file"}) is True


def test_legacy_file_full_track_enabled_defaults_to_false() -> None:
    assert legacy_file_full_track_enabled({}) is False


def test_legacy_file_full_track_enabled_accepts_truthy_values() -> None:
    assert legacy_file_full_track_enabled({"CODESYS_E2E_FILE_FULL": "true"}) is True
