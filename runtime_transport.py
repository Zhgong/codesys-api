from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from legacy_file_transport import build_legacy_file_transport
from named_pipe_transport import NamedPipeScriptTransport
from server_config import ServerConfig
from session_transport import build_primary_script_transport


PrimaryBuilder = Callable[..., NamedPipeScriptTransport]
LegacyBuilder = Callable[..., object]


def build_runtime_transport(
    config: ServerConfig,
    *,
    temp_root: Path | None = None,
    primary_builder: PrimaryBuilder = build_primary_script_transport,
    legacy_builder: LegacyBuilder = build_legacy_file_transport,
) -> object:
    """Build the active runtime transport using primary-by-default semantics."""

    if config.transport_requires_explicit_opt_in:
        return legacy_builder(
            request_dir=config.request_dir,
            result_dir=config.result_dir,
            temp_root=temp_root or Path(tempfile.gettempdir()),
        )
    if not config.transport_is_supported:
        raise ValueError("Unsupported transport: {0}".format(config.transport_name))
    return primary_builder(
        pipe_name=config.pipe_name,
    )
