from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from action_layer import ActionService
from codesys_process import CodesysProcessManager, ProcessManagerConfig
from ironpython_script_engine import IronPythonScriptEngineAdapter
from runtime_transport import build_runtime_transport
from script_executor import ScriptExecutor
from server_config import ServerConfig


NowFn = Callable[[], float]


@dataclass(frozen=True)
class AppRuntime:
    process_manager: Any
    script_executor: Any
    engine_adapter: Any
    actions_service: Any


def build_app_runtime(
    config: ServerConfig,
    *,
    logger: logging.Logger,
    now_fn: NowFn = time.time,
    process_manager_cls: Any = CodesysProcessManager,
    transport_builder: Callable[[ServerConfig], Any] = build_runtime_transport,
    script_executor_cls: Any = ScriptExecutor,
    engine_adapter_cls: Any = IronPythonScriptEngineAdapter,
    action_service_cls: Any = ActionService,
) -> AppRuntime:
    process_config = ProcessManagerConfig(
        codesys_path=config.codesys_path,
        script_path=config.persistent_script,
        script_lib_dir=config.script_lib_dir,
        profile_name=config.codesys_profile_name,
        profile_path=config.codesys_profile_path,
        no_ui=config.codesys_no_ui,
        transport_name=config.transport_name,
        pipe_name=config.pipe_name,
    )
    process_manager = process_manager_cls(process_config, logger=logger)
    transport = transport_builder(config)
    script_executor = script_executor_cls(transport, logger=logger)
    engine_adapter = engine_adapter_cls(codesys_path=config.codesys_path, logger=logger)
    actions_service = action_service_cls(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=engine_adapter,
        logger=logger,
        now_fn=now_fn,
        script_dir=config.script_dir,
    )
    return AppRuntime(
        process_manager=process_manager,
        script_executor=script_executor,
        engine_adapter=engine_adapter,
        actions_service=actions_service,
    )
