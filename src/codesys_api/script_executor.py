from __future__ import annotations

import logging
import traceback
import uuid
from typing import Any, cast


class ScriptExecutor:
    """Executes scripts through the active runtime transport."""

    def __init__(self, transport: Any, *, logger: logging.Logger) -> None:
        self.transport = transport
        self.logger = logger

    def execute_script(self, script_content: str, timeout: int = 60) -> dict[str, object]:
        """Execute a script and return the transport result."""
        try:
            request_id = str(uuid.uuid4())
            self.logger.info(
                "Executing script (request ID: %s, timeout: %s seconds)",
                request_id,
                timeout,
            )
            script_preview = script_content[:500].replace("\n", " ")
            self.logger.info("Script preview: %s...", script_preview)
            result = self.transport.execute_script(script_content, timeout=timeout)
            if result.get("success", False):
                self.logger.info("Script execution successful")
            else:
                self.logger.warning(
                    "Script execution failed via transport=%s stage=%s retryable=%s: %s",
                    result.get("transport", getattr(self.transport, "transport_name", "unknown")),
                    result.get("error_stage", "unknown"),
                    result.get("retryable", "n/a"),
                    result.get("error", "Unknown error"),
                )
            return cast(dict[str, object], result)
        except Exception as exc:
            self.logger.error("Error executing script: %s", str(exc))
            self.logger.error(traceback.format_exc())
            return {"success": False, "error": str(exc)}
