from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class EngineCapabilities:
    session_start: bool
    session_status: bool
    script_execute: bool
    project_create: bool
    project_open: bool
    project_save: bool
    project_close: bool
    project_list: bool
    project_compile: bool
    pou_create: bool
    pou_code: bool
    pou_list: bool


@dataclass(frozen=True)
class ExecutionSpec:
    script: str
    timeout: int


class EngineAdapter(Protocol):
    @property
    def engine_name(self) -> str: ...

    def capabilities(self) -> EngineCapabilities: ...

    def build_execution(self, action: str, params: dict[str, object]) -> ExecutionSpec: ...

    def normalize_result(self, action: str, raw_result: dict[str, Any]) -> dict[str, object]: ...
