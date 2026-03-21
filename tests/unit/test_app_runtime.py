from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from codesys_api.app_runtime import build_app_runtime
from codesys_api.server_config import load_server_config


class FakeProcessManager:
    def __init__(self, config, *, logger):  # type: ignore[no-untyped-def]
        self.config = config
        self.logger = logger


class FakeScriptExecutor:
    def __init__(self, transport, *, logger):  # type: ignore[no-untyped-def]
        self.transport = transport
        self.logger = logger


class FakeEngineAdapter:
    def __init__(self, *, codesys_path, logger):  # type: ignore[no-untyped-def]
        self.codesys_path = codesys_path
        self.logger = logger


class FakeActionService:
    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        self.kwargs = kwargs


def test_build_app_runtime_wires_shared_runtime_dependencies(tmp_path: Path) -> None:
    config = load_server_config(tmp_path, {})
    sentinel_transport = object()

    runtime = build_app_runtime(
        config,
        logger=logging.getLogger("app-runtime-test"),
        process_manager_cls=FakeProcessManager,
        transport_builder=lambda _config: sentinel_transport,
        script_executor_cls=FakeScriptExecutor,
        engine_adapter_cls=FakeEngineAdapter,
        action_service_cls=FakeActionService,
    )

    assert runtime.process_manager.config.codesys_path == config.codesys_path
    assert runtime.script_executor.transport is sentinel_transport
    assert runtime.engine_adapter.codesys_path == config.codesys_path
    actions_service = cast(Any, runtime.actions_service)
    assert actions_service.kwargs["process_manager"] is runtime.process_manager
    assert actions_service.kwargs["script_executor"] is runtime.script_executor
    assert actions_service.kwargs["engine_adapter"] is runtime.engine_adapter
