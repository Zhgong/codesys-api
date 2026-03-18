from __future__ import annotations

import ctypes
import json
import struct
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Final

from transport_result import (
    build_timeout_transport_error,
    build_transport_error,
    create_transport_request,
    normalize_transport_result,
)


INVALID_HANDLE_VALUE: Final[int] = -1
GENERIC_READ: Final[int] = 0x80000000
GENERIC_WRITE: Final[int] = 0x40000000
OPEN_EXISTING: Final[int] = 3
PIPE_ACCESS_DUPLEX: Final[int] = 0x00000003
PIPE_TYPE_BYTE: Final[int] = 0x00000000
PIPE_READMODE_BYTE: Final[int] = 0x00000000
PIPE_WAIT: Final[int] = 0x00000000
PIPE_UNLIMITED_INSTANCES: Final[int] = 255
ERROR_FILE_NOT_FOUND: Final[int] = 2
ERROR_INVALID_HANDLE: Final[int] = 6
ERROR_PIPE_BUSY: Final[int] = 231
ERROR_BROKEN_PIPE: Final[int] = 109
ERROR_SEM_TIMEOUT: Final[int] = 121


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


kernel32.CreateFileW.argtypes = [
    ctypes.c_wchar_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
]
kernel32.CreateFileW.restype = ctypes.c_void_p

kernel32.WaitNamedPipeW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
kernel32.WaitNamedPipeW.restype = ctypes.c_int

kernel32.ReadFile.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
kernel32.ReadFile.restype = ctypes.c_int

kernel32.WriteFile.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
kernel32.WriteFile.restype = ctypes.c_int

kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_int

kernel32.CreateNamedPipeW.argtypes = [
    ctypes.c_wchar_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
]
kernel32.CreateNamedPipeW.restype = ctypes.c_void_p

kernel32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.ConnectNamedPipe.restype = ctypes.c_int

kernel32.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
kernel32.DisconnectNamedPipe.restype = ctypes.c_int

kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
kernel32.FlushFileBuffers.restype = ctypes.c_int


@dataclass(frozen=True)
class NamedPipeConfig:
    pipe_name: str
    connect_poll_interval: float = 0.1
    write_retry_delay: float = 0.5
    max_write_retries: int = 8


def build_pipe_path(pipe_name: str) -> str:
    return r"\\.\pipe\{0}".format(pipe_name)


def wait_for_named_pipe_listener(
    pipe_name: str,
    timeout_seconds: float,
    *,
    now_fn: Callable[[], float] = time.time,
    sleep_fn: Callable[[float], None] = time.sleep,
    poll_interval: float = 0.1,
) -> bool:
    pipe_path = build_pipe_path(pipe_name)
    deadline = now_fn() + timeout_seconds

    while now_fn() < deadline:
        remaining_ms = max(1, min(int((deadline - now_fn()) * 1000), 250))
        if kernel32.WaitNamedPipeW(pipe_path, remaining_ms):
            return True
        error_code = ctypes.get_last_error()
        if error_code not in (ERROR_SEM_TIMEOUT, ERROR_FILE_NOT_FOUND):
            raise OSError(error_code, "WaitNamedPipeW failed while waiting for listener")
        sleep_fn(poll_interval)

    return False


def encode_pipe_message(payload: Mapping[str, object]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return struct.pack("<I", len(body)) + body


def decode_pipe_message(data: bytes) -> dict[str, Any]:
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Named pipe payload must be a JSON object")
    return payload


def create_named_pipe_server_handle(pipe_name: str) -> ctypes.c_void_p:
    raw_handle = kernel32.CreateNamedPipeW(
        build_pipe_path(pipe_name),
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1,
        65536,
        65536,
        0,
        None,
    )
    handle_value = ctypes.c_void_p(raw_handle).value
    if handle_value is None or handle_value == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateNamedPipeW failed")
    return ctypes.c_void_p(handle_value)


def wait_for_named_pipe_client(handle: ctypes.c_void_p) -> None:
    connected = kernel32.ConnectNamedPipe(handle, None)
    if connected:
        return
    error_code = ctypes.get_last_error()
    if error_code == 535:  # ERROR_PIPE_CONNECTED
        return
    raise OSError(error_code, "ConnectNamedPipe failed")


def disconnect_named_pipe(handle: ctypes.c_void_p) -> None:
    kernel32.DisconnectNamedPipe(handle)


def close_pipe_handle(handle: ctypes.c_void_p) -> None:
    kernel32.CloseHandle(handle)


def _read_exact(handle: ctypes.c_void_p, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size

    while remaining > 0:
        buffer = ctypes.create_string_buffer(remaining)
        read = ctypes.c_uint32()
        success = kernel32.ReadFile(handle, buffer, remaining, ctypes.byref(read), None)
        if not success:
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "ReadFile failed")
        if read.value == 0:
            raise EOFError("Named pipe closed before enough data was read")
        chunks.append(buffer.raw[: read.value])
        remaining -= int(read.value)

    return b"".join(chunks)


def read_pipe_payload(handle: ctypes.c_void_p) -> dict[str, Any]:
    header = _read_exact(handle, 4)
    expected_size = struct.unpack("<I", header)[0]
    body = _read_exact(handle, expected_size)
    return decode_pipe_message(body)


def write_pipe_payload(handle: ctypes.c_void_p, payload: Mapping[str, object]) -> None:
    message = encode_pipe_message(payload)
    offset = 0

    while offset < len(message):
        chunk = message[offset:]
        written = ctypes.c_uint32()
        buffer = ctypes.create_string_buffer(chunk)
        success = kernel32.WriteFile(handle, buffer, len(chunk), ctypes.byref(written), None)
        if not success:
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "WriteFile failed")
        offset += int(written.value)

    kernel32.FlushFileBuffers(handle)


class NamedPipeScriptTransport:
    transport_name = "named_pipe"

    def __init__(
        self,
        *,
        pipe_name: str,
        now_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = NamedPipeConfig(pipe_name=pipe_name)
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn

    def execute_script(self, script_content: str, timeout: int = 60) -> dict[str, object]:
        transport_request = create_transport_request(
            script=script_content,
            timeout_hint=timeout,
            now_fn=self.now_fn,
        )
        payload = transport_request.as_payload()
        deadline = self.now_fn() + timeout
        attempts = 0

        while True:
            remaining = deadline - self.now_fn()
            if remaining <= 0:
                return build_timeout_transport_error(
                    transport=self.transport_name,
                    elapsed_seconds=float(timeout),
                    request_id=transport_request.request_id,
                )

            try:
                handle = self._connect(max(1, int(remaining)))
            except TimeoutError:
                return build_timeout_transport_error(
                    transport=self.transport_name,
                    elapsed_seconds=float(timeout),
                    request_id=transport_request.request_id,
                )
            except OSError as exc:
                return build_transport_error(
                    transport=self.transport_name,
                    stage="connect",
                    error="Named pipe connection failed: {0}".format(exc),
                    request_id=transport_request.request_id,
                    retryable=False,
                )

            try:
                write_pipe_payload(handle, payload)
                result = read_pipe_payload(handle)
            except OSError as exc:
                if self._should_retry_write(exc) and attempts < self.config.max_write_retries:
                    attempts += 1
                    self.sleep_fn(self.config.write_retry_delay)
                    close_pipe_handle(handle)
                    continue
                close_pipe_handle(handle)
                return build_transport_error(
                    transport=self.transport_name,
                    stage=self._error_stage_for_os_error(exc),
                    error="Named pipe transport failed: {0}".format(exc),
                    request_id=transport_request.request_id,
                    retryable=self._should_retry_write(exc),
                )
            except TimeoutError:
                close_pipe_handle(handle)
                return build_timeout_transport_error(
                    transport=self.transport_name,
                    elapsed_seconds=float(timeout),
                    request_id=transport_request.request_id,
                )
            except (EOFError, ValueError, json.JSONDecodeError) as exc:
                close_pipe_handle(handle)
                return build_transport_error(
                    transport=self.transport_name,
                    stage="decode",
                    error="Named pipe transport failed: {0}".format(exc),
                    request_id=transport_request.request_id,
                    retryable=False,
                )

            close_pipe_handle(handle)

            response_id = result.get("request_id")
            if response_id != transport_request.request_id:
                return build_transport_error(
                    transport=self.transport_name,
                    stage="response_mismatch",
                    error="Named pipe response request_id mismatch",
                    request_id=transport_request.request_id,
                    retryable=False,
                )

            return normalize_transport_result(
                result,
                transport=self.transport_name,
                request_id=transport_request.request_id,
            )

    def _connect(self, timeout: int) -> ctypes.c_void_p:
        pipe_path = build_pipe_path(self.config.pipe_name)
        deadline = self.now_fn() + timeout

        while True:
            raw_handle = kernel32.CreateFileW(
                pipe_path,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None,
            )
            handle_value = ctypes.c_void_p(raw_handle).value
            if handle_value is not None and handle_value != INVALID_HANDLE_VALUE:
                return ctypes.c_void_p(handle_value)

            error_code = ctypes.get_last_error()
            remaining_seconds = deadline - self.now_fn()
            if remaining_seconds <= 0:
                raise TimeoutError("Timed out connecting to named pipe")

            wait_ms = max(1, min(int(remaining_seconds * 1000), 250))
            if error_code in (ERROR_PIPE_BUSY, ERROR_FILE_NOT_FOUND):
                if kernel32.WaitNamedPipeW(pipe_path, wait_ms):
                    continue
                wait_error = ctypes.get_last_error()
                if wait_error not in (ERROR_SEM_TIMEOUT, ERROR_FILE_NOT_FOUND):
                    raise OSError(wait_error, "WaitNamedPipeW failed")
                self.sleep_fn(self.config.connect_poll_interval)
                continue

            raise OSError(error_code, "CreateFileW failed while connecting to named pipe")

    def _should_retry_write(self, exc: OSError) -> bool:
        return exc.errno in (ERROR_INVALID_HANDLE, ERROR_BROKEN_PIPE)

    def _error_stage_for_os_error(self, exc: OSError) -> str:
        if exc.errno in (ERROR_INVALID_HANDLE, ERROR_BROKEN_PIPE):
            return "write"
        return "read"
