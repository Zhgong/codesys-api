from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from .action_layer import ActionRequest, ActionServiceLike, ActionType
from .app_runtime import build_app_runtime
from .server_config import load_server_config

if TYPE_CHECKING:
    from .action_layer import ActionResult


class CodesysToolDispatcher:
    """Thin synchronous wrapper over ActionService — one method per ActionType.

    Each method builds an ActionRequest, delegates to ActionService.execute(),
    and returns the result body as a JSON string.
    """

    def __init__(self, actions_service: ActionServiceLike) -> None:
        self._svc = actions_service

    def _call(self, action: ActionType, params: dict[str, object] | None = None) -> str:
        result: ActionResult = self._svc.execute(
            ActionRequest(action=action, params=params or {})
        )
        return json.dumps(result.body)

    # --- Session ---

    def session_start(self) -> str:
        return self._call(ActionType.SESSION_START)

    def session_stop(self) -> str:
        return self._call(ActionType.SESSION_STOP)

    def session_restart(self) -> str:
        return self._call(ActionType.SESSION_RESTART)

    def session_status(self) -> str:
        return self._call(ActionType.SESSION_STATUS)

    # --- Project ---

    def project_create(self, path: str, skeleton: bool = True) -> str:
        return self._call(ActionType.PROJECT_CREATE, {"path": path, "skeleton": skeleton})

    def project_open(self, path: str) -> str:
        return self._call(ActionType.PROJECT_OPEN, {"path": path})

    def project_save(self) -> str:
        return self._call(ActionType.PROJECT_SAVE)

    def project_close(self) -> str:
        return self._call(ActionType.PROJECT_CLOSE)

    def project_list(self) -> str:
        return self._call(ActionType.PROJECT_LIST)

    def project_compile(self) -> str:
        return self._call(ActionType.PROJECT_COMPILE)

    def project_import_xml(self, xml_path: str) -> str:
        return self._call(ActionType.PROJECT_IMPORT_XML, {"xml_path": xml_path})

    def project_import_xml_content(self, xml_content: str) -> str:
        return self._call(ActionType.PROJECT_IMPORT_XML_CONTENT, {"xml_content": xml_content})

    def project_import_xml_b64(self, xml_b64: str) -> str:
        return self._call(ActionType.PROJECT_IMPORT_XML_B64, {"xml_b64": xml_b64})

    # --- POU ---

    def pou_create(self, name: str, type: str, language: str) -> str:
        return self._call(ActionType.POU_CREATE, {"name": name, "type": type, "language": language})

    def pou_code(
        self,
        path: str,
        declaration: str = "",
        implementation: str = "",
    ) -> str:
        params: dict[str, object] = {"path": path}
        if declaration:
            params["declaration"] = declaration
        if implementation:
            params["implementation"] = implementation
        return self._call(ActionType.POU_CODE, params)

    def pou_list(self) -> str:
        return self._call(ActionType.POU_LIST)

    # --- Script ---

    def script_execute(self, script: str) -> str:
        return self._call(ActionType.SCRIPT_EXECUTE, {"script": script})


DEFAULT_MCP_HOST = "0.0.0.0"
DEFAULT_MCP_PORT = 8001
DEFAULT_MCP_TRANSPORT = "sse"


def create_mcp_server(
    dispatcher: CodesysToolDispatcher,
    *,
    host: str = DEFAULT_MCP_HOST,
    port: int = DEFAULT_MCP_PORT,
) -> FastMCP:
    """Register all CODESYS tools on a FastMCP server and return it."""

    mcp: FastMCP = FastMCP("codesys-api", host=host, port=port)

    @mcp.tool()
    def session_start() -> str:
        """Launch the CODESYS process and open the IPC session."""
        return dispatcher.session_start()

    @mcp.tool()
    def session_stop() -> str:
        """Stop the CODESYS process and close the IPC session."""
        return dispatcher.session_stop()

    @mcp.tool()
    def session_restart() -> str:
        """Stop then restart the CODESYS process."""
        return dispatcher.session_restart()

    @mcp.tool()
    def session_status() -> str:
        """Return the current CODESYS process and IPC session status."""
        return dispatcher.session_status()

    @mcp.tool()
    def project_create(path: str, skeleton: bool = True) -> str:
        """Create a new CODESYS project at the given absolute path and open it.

        When skeleton is True (default), the project is seeded with a default
        device, PLC_PRG, MainTask, and task configuration. Pass skeleton=False
        to create a bare empty project — useful right before importing a
        PLCopen XML that already contains its own device tree (otherwise the
        project ends up with two devices).
        """
        return dispatcher.project_create(path=path, skeleton=skeleton)

    @mcp.tool()
    def project_open(path: str) -> str:
        """Open an existing CODESYS .project file."""
        return dispatcher.project_open(path=path)

    @mcp.tool()
    def project_save() -> str:
        """Save the currently open CODESYS project."""
        return dispatcher.project_save()

    @mcp.tool()
    def project_close() -> str:
        """Close the currently open CODESYS project."""
        return dispatcher.project_close()

    @mcp.tool()
    def project_list() -> str:
        """List projects known to the active CODESYS session."""
        return dispatcher.project_list()

    @mcp.tool()
    def project_compile() -> str:
        """Build the active CODESYS project and return message-store results."""
        return dispatcher.project_compile()

    @mcp.tool()
    def project_import_xml(xml_path: str) -> str:
        """Import a PLCopen XML file into the currently open CODESYS project."""
        return dispatcher.project_import_xml(xml_path=xml_path)

    @mcp.tool()
    def project_import_xml_content(xml_content: str) -> str:
        """Import a PLCopen XML file into the currently open CODESYS project.

        Pass the raw XML text as a string; the server writes a temporary file
        automatically so the client does not need to manage any file paths.
        """
        return dispatcher.project_import_xml_content(xml_content=xml_content)

    @mcp.tool()
    def project_import_xml_b64(xml_b64: str) -> str:
        """Import a PLCopen XML file into the currently open CODESYS project.

        Pass the XML content base64-encoded; the server decodes it and writes
        a temporary file automatically.
        """
        return dispatcher.project_import_xml_b64(xml_b64=xml_b64)

    @mcp.tool()
    def pou_create(name: str, type: str, language: str) -> str:
        """Create a new POU in the active project.

        Args:
            name: POU name (e.g. "CounterFB").
            type: POU type — one of FunctionBlock, Function, Program.
            language: Implementation language — one of ST, FBD, LD, IL, CFC.
        """
        return dispatcher.pou_create(name=name, type=type, language=language)

    @mcp.tool()
    def pou_code(
        path: str,
        declaration: str = "",
        implementation: str = "",
    ) -> str:
        """Set POU declaration and/or implementation text.

        Args:
            path: Scriptengine tree path to the POU, e.g. "Application\\CounterFB".
            declaration: VAR block text (omit the FUNCTION_BLOCK/PROGRAM header line).
            implementation: ST/FBD/etc. body text.
        """
        return dispatcher.pou_code(path=path, declaration=declaration, implementation=implementation)

    @mcp.tool()
    def pou_list() -> str:
        """List POUs in the active CODESYS project."""
        return dispatcher.pou_list()

    @mcp.tool()
    def script_execute(script: str) -> str:
        """Execute arbitrary IronPython 2.7 code inside CODESYS. Use with caution."""
        return dispatcher.script_execute(script=script)

    return mcp


def main() -> None:
    transport = os.environ.get("CODESYS_API_MCP_TRANSPORT", DEFAULT_MCP_TRANSPORT)
    host = os.environ.get("CODESYS_API_MCP_HOST", DEFAULT_MCP_HOST)
    port = int(os.environ.get("CODESYS_API_MCP_PORT", str(DEFAULT_MCP_PORT)))

    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("codesys_mcp")
    config = load_server_config(Path.cwd(), os.environ)
    runtime = build_app_runtime(config, logger=logger)
    dispatcher = CodesysToolDispatcher(runtime.actions_service)
    server = create_mcp_server(dispatcher, host=host, port=port)

    if transport == "sse":
        print(f"CODESYS MCP server listening on http://{host}:{port}/sse")

    server.run(transport=transport)  # type: ignore[arg-type]
