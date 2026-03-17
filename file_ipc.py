from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final


DEFAULT_MAX_RESULT_READ_RETRIES: Final[int] = 5


@dataclass(frozen=True)
class FileIpcRequestArtifacts:
    request_id: str
    request_dir: Path
    script_path: Path
    result_path: Path
    request_path: Path


def create_ipc_request(
    script_content: str,
    request_id: str,
    request_root: Path,
    temp_root: Path | None = None,
    timestamp: float | None = None,
) -> FileIpcRequestArtifacts:
    effective_temp_root = temp_root if temp_root is not None else Path(tempfile.gettempdir())
    request_dir = effective_temp_root / f"codesys_req_{request_id}"
    request_dir.mkdir(parents=True, exist_ok=True)

    script_path = request_dir / "script.py"
    result_path = request_dir / "result.json"
    request_path = request_root / f"{request_id}.request"

    script_path.write_text(script_content, encoding="utf-8")
    request_payload = {
        "script_path": str(script_path).replace("\\", "\\\\"),
        "result_path": str(result_path).replace("\\", "\\\\"),
        "timestamp": time.time() if timestamp is None else timestamp,
        "request_id": request_id,
    }
    request_path.write_text(json.dumps(request_payload), encoding="utf-8")

    return FileIpcRequestArtifacts(
        request_id=request_id,
        request_dir=request_dir,
        script_path=script_path,
        result_path=result_path,
        request_path=request_path,
    )


def read_ipc_result(
    result_path: Path,
    max_retries: int = DEFAULT_MAX_RESULT_READ_RETRIES,
    settle_delay_seconds: float = 0.2,
    retry_delay_seconds: float = 0.5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    file_size = result_path.stat().st_size
    retry_count = 0

    while retry_count < max_retries:
        sleep_fn(settle_delay_seconds)
        new_size = result_path.stat().st_size
        if new_size != file_size:
            file_size = new_size
            retry_count += 1
            continue

        content = result_path.read_text(encoding="utf-8")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            retry_count += 1
            sleep_fn(retry_delay_seconds)
            continue

        if not isinstance(payload, dict):
            raise ValueError("IPC result payload must be a JSON object")

        return payload

    raise ValueError(f"Failed to read valid result after {max_retries} retries")


def build_timeout_result(elapsed_seconds: float) -> dict[str, object]:
    return {
        "success": False,
        "error": "Script execution timed out after {:.2f} seconds".format(elapsed_seconds),
        "timeout": True,
    }


def determine_poll_interval(elapsed_seconds: float) -> float:
    if elapsed_seconds < 5:
        return 0.1
    if elapsed_seconds < 30:
        return 0.5
    return 1.0


def cleanup_ipc_files(*paths: str | os.PathLike[str] | None) -> None:
    for path in paths:
        if path is None:
            continue

        candidate = Path(path)
        if candidate.exists():
            candidate.unlink()


def cleanup_request_dir(request_dir: str | os.PathLike[str] | None) -> None:
    if request_dir is None:
        return

    candidate = Path(request_dir)
    if candidate.exists() and candidate.is_dir() and not any(candidate.iterdir()):
        candidate.rmdir()
