from __future__ import annotations

import time
from typing import Callable

import named_pipe_transport
from transport_result import TransportExecutionContext, TransportRequest

__all__ = [
    "TransportRequest",
    "TransportExecutionContext",
    "build_primary_script_transport",
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
