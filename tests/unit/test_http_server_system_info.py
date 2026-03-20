from __future__ import annotations

from typing import Any, cast

import HTTP_SERVER
from HTTP_SERVER import build_runtime_transport, build_system_info


class FakeProcessManager:
    def __init__(self, running: bool) -> None:
        self.running = running

    def is_running(self) -> bool:
        return self.running


def test_build_system_info_reports_named_pipe_as_primary() -> None:
    info = build_system_info(FakeProcessManager(True))
    process_manager = cast(dict[str, object], info["process_manager"])

    assert process_manager["status"] is True
    assert info["transport"] == "named_pipe"
    assert info["transport_role"] == "primary"
    assert info["transport_legacy"] is False
    assert info["recommended_transport"] == "named_pipe"


def test_build_system_info_uses_config_transport_role_helpers(monkeypatch: Any) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_is_primary = True
        transport_is_legacy = False
        transport_requires_explicit_opt_in = False
        transport_role = "primary"
        recommended_transport = "named_pipe"

    monkeypatch.setattr(HTTP_SERVER, "APP_CONFIG", FakeConfig())
    monkeypatch.setattr(HTTP_SERVER, "TRANSPORT_NAME", "named_pipe")
    monkeypatch.setattr(HTTP_SERVER, "PIPE_NAME", "codesys_api_session")

    info = build_system_info(FakeProcessManager(True))

    assert info["transport"] == "named_pipe"
    assert info["transport_role"] == "primary"
    assert info["transport_legacy"] is False
    assert info["recommended_transport"] == "named_pipe"


def test_build_system_info_has_stable_transport_fields() -> None:
    info = build_system_info(FakeProcessManager(False))
    process_manager = cast(dict[str, object], info["process_manager"])

    expected_keys = {
        "version",
        "process_manager",
        "codesys_path",
        "persistent_script",
        "transport",
        "transport_role",
        "transport_legacy",
        "recommended_transport",
        "pipe_name",
    }

    assert expected_keys.issubset(set(info.keys()))
    assert process_manager["status"] is False


def test_build_system_info_reports_file_as_legacy(monkeypatch: Any) -> None:
    class FakeConfig:
        transport_is_primary = False
        transport_role = "legacy_fallback"
        transport_is_legacy = True
        transport_requires_explicit_opt_in = True
        recommended_transport = "named_pipe"

    monkeypatch.setattr(HTTP_SERVER, "APP_CONFIG", FakeConfig())
    monkeypatch.setattr(HTTP_SERVER, "TRANSPORT_NAME", "file")
    monkeypatch.setattr(HTTP_SERVER, "PIPE_NAME", "unused")

    info = build_system_info(FakeProcessManager(True))

    assert info["transport"] == "file"
    assert info["transport_role"] == "legacy_fallback"
    assert info["transport_legacy"] is True
    assert info["recommended_transport"] == "named_pipe"


def test_build_runtime_transport_uses_primary_builder_by_default(monkeypatch: Any, tmp_path: Any) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_requires_explicit_opt_in = False
        request_dir = tmp_path / "requests"
        result_dir = tmp_path / "results"
        pipe_name = "codesys_api_test_pipe"

    sentinel = object()

    monkeypatch.setattr(HTTP_SERVER, "APP_CONFIG", FakeConfig())
    monkeypatch.setattr(HTTP_SERVER, "build_primary_script_transport", lambda **kwargs: sentinel)
    monkeypatch.setattr(
        HTTP_SERVER,
        "build_legacy_file_transport",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy builder should not be used")),
    )

    transport = build_runtime_transport()

    assert transport is sentinel


def test_build_runtime_transport_uses_legacy_builder_only_for_explicit_opt_in(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    class FakeConfig:
        transport_name = "file"
        transport_requires_explicit_opt_in = True
        request_dir = tmp_path / "requests"
        result_dir = tmp_path / "results"
        pipe_name = "unused"

    sentinel = object()

    monkeypatch.setattr(HTTP_SERVER, "APP_CONFIG", FakeConfig())
    monkeypatch.setattr(
        HTTP_SERVER,
        "build_primary_script_transport",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("primary builder should not be used")),
    )
    monkeypatch.setattr(HTTP_SERVER, "build_legacy_file_transport", lambda **kwargs: sentinel)

    transport = build_runtime_transport()

    assert transport is sentinel
