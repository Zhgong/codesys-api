from __future__ import annotations

from typing import Callable

from .named_pipe_transport import NamedPipeScriptTransport
from .server_config import ServerConfig
from .session_transport import build_primary_script_transport


PrimaryBuilder = Callable[..., NamedPipeScriptTransport]


def build_runtime_transport(
    config: ServerConfig,
    *,
    primary_builder: PrimaryBuilder = build_primary_script_transport,
) -> NamedPipeScriptTransport:
    """Build the active runtime transport using primary-by-default semantics."""

    if not config.transport_is_supported:
        raise ValueError("Unsupported transport: {0}".format(config.transport_name))
    return primary_builder(
        pipe_name=config.pipe_name,
    )
