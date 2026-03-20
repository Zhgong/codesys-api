from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from runtime_transport import build_runtime_transport


def test_build_runtime_transport_uses_primary_builder_by_default(tmp_path: Path) -> None:
    class FakeConfig:
        transport_name = "named_pipe"
        transport_is_supported = True
        transport_requires_explicit_opt_in = False
        request_dir = tmp_path / "requests"
        result_dir = tmp_path / "results"
        pipe_name = "codesys_api_test_pipe"

    sentinel = object()

    transport = build_runtime_transport(
        cast(Any, FakeConfig()),
        primary_builder=cast(Any, lambda **kwargs: sentinel),
        legacy_builder=cast(Any, lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy builder should not be used"))),
    )

    assert transport is sentinel


def test_build_runtime_transport_uses_legacy_builder_only_for_explicit_opt_in(
    tmp_path: Path,
) -> None:
    class FakeConfig:
        transport_name = "file"
        transport_is_supported = True
        transport_requires_explicit_opt_in = True
        request_dir = tmp_path / "requests"
        result_dir = tmp_path / "results"
        pipe_name = "unused"

    sentinel = object()

    transport = build_runtime_transport(
        cast(Any, FakeConfig()),
        primary_builder=cast(Any, lambda **kwargs: (_ for _ in ()).throw(AssertionError("primary builder should not be used"))),
        legacy_builder=cast(Any, lambda **kwargs: sentinel),
    )

    assert transport is sentinel


def test_build_runtime_transport_rejects_unsupported_transport(tmp_path: Path) -> None:
    class FakeConfig:
        transport_name = "unknown"
        transport_is_supported = False
        transport_requires_explicit_opt_in = False
        request_dir = tmp_path / "requests"
        result_dir = tmp_path / "results"
        pipe_name = "unused"

    try:
        build_runtime_transport(cast(Any, FakeConfig()))
    except ValueError as exc:
        assert "unsupported transport" in str(exc).lower()
    else:
        raise AssertionError("Expected build_runtime_transport to reject unsupported transport")
