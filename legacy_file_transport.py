from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from file_ipc import (
    cleanup_ipc_files,
    cleanup_request_dir,
    create_ipc_request,
    determine_poll_interval,
    read_ipc_result,
)
from transport_result import TransportExecutionContext, create_transport_execution


NowFn = Callable[[], float]
SleepFn = Callable[[float], None]


class FileScriptTransport:
    """Legacy file-backed transport kept as an explicit fallback path."""

    transport_name = "file"

    def __init__(
        self,
        *,
        request_dir: Path,
        result_dir: Path,
        temp_root: Path,
        now_fn: NowFn = time.time,
        sleep_fn: SleepFn = time.sleep,
    ) -> None:
        self.request_dir = request_dir
        self.result_dir = result_dir
        self.temp_root = temp_root
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn

    def execute_script(self, script_content: str, timeout: int = 60) -> dict[str, object]:
        execution = create_transport_execution(
            script=script_content,
            timeout_hint=timeout,
            now_fn=self.now_fn,
        )
        transport_request = execution.request
        script_path: str | None = None
        result_path: str | None = None
        request_path: str | None = None
        request_work_dir: str | None = None

        try:
            artifacts = create_ipc_request(
                script_content=script_content,
                request_id=transport_request.request_id,
                request_root=self.request_dir,
                temp_root=self.temp_root,
            )
            request_work_dir = str(artifacts.request_dir)
            script_path = str(artifacts.script_path)
            result_path = str(artifacts.result_path)
            request_path = str(artifacts.request_path)

            try:
                result = self._wait_for_result_payload(artifacts.result_path, execution)
            except TimeoutError:
                result = None
            except Exception as exc:
                self._cleanup(script_path, result_path, request_path, request_work_dir)
                return execution.build_error(
                    self.transport_name,
                    stage="result_read",
                    error=str(exc),
                )

            if result is not None:
                self._cleanup(script_path, result_path, request_path, request_work_dir)
                return execution.normalize_result(
                    result,
                    self.transport_name,
                )

            if artifacts.result_path.parent.exists():
                artifacts.result_path.write_text(
                    json.dumps(execution.build_timeout_error(self.transport_name, now_fn=self.now_fn)),
                    encoding="utf-8",
                )
            self._cleanup(script_path, None, request_path, request_work_dir)
            return execution.build_timeout_error(self.transport_name, now_fn=self.now_fn)
        except Exception as exc:
            self._cleanup(script_path, result_path, request_path, request_work_dir)
            return execution.build_error(
                self.transport_name,
                stage="request_create",
                error=str(exc),
            )

    def _cleanup(
        self,
        script_path: str | None,
        result_path: str | None,
        request_path: str | None,
        request_dir: str | None,
    ) -> None:
        cleanup_ipc_files(script_path, result_path, request_path)
        cleanup_request_dir(request_dir)

    def _wait_for_result_payload(
        self,
        result_path: Path,
        execution: TransportExecutionContext,
    ) -> dict[str, object]:
        while not execution.timed_out(self.now_fn):
            if result_path.exists():
                return read_ipc_result(result_path)
            elapsed = execution.elapsed_seconds(self.now_fn)
            self.sleep_fn(determine_poll_interval(elapsed))
        raise TimeoutError("Timed out waiting for file transport result")


def build_legacy_file_transport(
    *,
    request_dir: Path,
    result_dir: Path,
    temp_root: Path,
    now_fn: NowFn = time.time,
    sleep_fn: SleepFn = time.sleep,
) -> FileScriptTransport:
    """Build the legacy file transport behind a dedicated removal seam."""

    return FileScriptTransport(
        request_dir=request_dir,
        result_dir=result_dir,
        temp_root=temp_root,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )
