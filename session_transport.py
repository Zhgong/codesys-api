from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import legacy_file_transport
import named_pipe_transport
from transport_result import TransportExecutionContext, TransportRequest

__all__ = [
    "TransportRequest",
    "TransportExecutionContext",
    "build_primary_script_transport",
    "build_script_transport",
]

NowFn = Callable[[], float]
SleepFn = Callable[[float], None]


def build_primary_script_transport(
    *,
    pipe_name: str,
    now_fn: NowFn = time.time,
    sleep_fn: SleepFn = time.sleep,
) -> named_pipe_transport.NamedPipeScriptTransport:
    """Build the standard named-pipe transport for the primary path."""

    return named_pipe_transport.NamedPipeScriptTransport(
        pipe_name=pipe_name,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )


def build_script_transport(
    *,
    transport_name: str,
    request_dir: Path,
    result_dir: Path,
    temp_root: Path,
    pipe_name: str,
    now_fn: NowFn = time.time,
    sleep_fn: SleepFn = time.sleep,
) -> legacy_file_transport.FileScriptTransport | named_pipe_transport.NamedPipeScriptTransport:
    """Compatibility transport builder; prefer build_primary_script_transport for the standard path."""

    if transport_name == "file":
        return legacy_file_transport.build_legacy_file_transport(
            request_dir=request_dir,
            result_dir=result_dir,
            temp_root=temp_root,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
    if transport_name == "named_pipe":
        return build_primary_script_transport(
            pipe_name=pipe_name,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
    raise ValueError("Unsupported transport: {0}".format(transport_name))
