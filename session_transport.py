from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from legacy_file_transport import FileScriptTransport, build_legacy_file_transport
from named_pipe_transport import NamedPipeScriptTransport
from transport_result import TransportExecutionContext, TransportRequest

__all__ = [
    "TransportRequest",
    "TransportExecutionContext",
    "FileScriptTransport",
    "NamedPipeScriptTransport",
    "build_legacy_file_transport",
    "build_script_transport",
]

NowFn = Callable[[], float]
SleepFn = Callable[[float], None]


def build_script_transport(
    *,
    transport_name: str,
    request_dir: Path,
    result_dir: Path,
    temp_root: Path,
    pipe_name: str,
    now_fn: NowFn = time.time,
    sleep_fn: SleepFn = time.sleep,
) -> FileScriptTransport | NamedPipeScriptTransport:
    """Build the configured transport, preferring named pipes as the primary path."""

    if transport_name == "file":
        return build_legacy_file_transport(
            request_dir=request_dir,
            result_dir=result_dir,
            temp_root=temp_root,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
    if transport_name == "named_pipe":
        return NamedPipeScriptTransport(
            pipe_name=pipe_name,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
    raise ValueError("Unsupported transport: {0}".format(transport_name))
