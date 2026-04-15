from __future__ import annotations

import json

from codesys_api.action_layer import ActionRequest, ActionResult, ActionType
from codesys_api.mcp_server import CodesysToolDispatcher


# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


class FakeActionService:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.last_request: ActionRequest | None = None

    def execute(self, request: ActionRequest) -> ActionResult:
        self.last_request = request
        return ActionResult(body=self.result)


def make_dispatcher(result: dict[str, object] | None = None) -> tuple[CodesysToolDispatcher, FakeActionService]:
    r = result if result is not None else {"success": True}
    svc = FakeActionService(r)
    return CodesysToolDispatcher(svc), svc


# ---------------------------------------------------------------------------
# Session tools
# ---------------------------------------------------------------------------


def test_session_start_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.session_start()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.SESSION_START
    assert svc.last_request.params == {}


def test_session_stop_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.session_stop()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.SESSION_STOP
    assert svc.last_request.params == {}


def test_session_restart_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.session_restart()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.SESSION_RESTART
    assert svc.last_request.params == {}


def test_session_status_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.session_status()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.SESSION_STATUS
    assert svc.last_request.params == {}


# ---------------------------------------------------------------------------
# Project tools
# ---------------------------------------------------------------------------


def test_project_create_passes_path() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_create(path=r"C:\work\demo.project")
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_CREATE
    assert svc.last_request.params == {"path": r"C:\work\demo.project", "skeleton": True}


def test_project_create_passes_skeleton_false() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_create(path=r"C:\work\bare.project", skeleton=False)
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_CREATE
    assert svc.last_request.params == {"path": r"C:\work\bare.project", "skeleton": False}


def test_project_open_passes_path() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_open(path=r"C:\work\existing.project")
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_OPEN
    assert svc.last_request.params == {"path": r"C:\work\existing.project"}


def test_project_save_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_save()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_SAVE
    assert svc.last_request.params == {}


def test_project_close_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_close()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_CLOSE
    assert svc.last_request.params == {}


def test_project_list_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_list()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_LIST
    assert svc.last_request.params == {}


def test_project_compile_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_compile()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_COMPILE
    assert svc.last_request.params == {}


def test_project_import_xml_passes_xml_path() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.project_import_xml(xml_path=r"C:\exports\Verify002.xml")
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_IMPORT_XML
    assert svc.last_request.params == {"xml_path": r"C:\exports\Verify002.xml"}


def test_project_import_xml_content_passes_xml_content() -> None:
    dispatcher, svc = make_dispatcher()
    xml = "<PLCOpenXML><fileHeader /></PLCOpenXML>"
    dispatcher.project_import_xml_content(xml_content=xml)
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_IMPORT_XML_CONTENT
    assert svc.last_request.params == {"xml_content": xml}


def test_project_import_xml_b64_passes_xml_b64() -> None:
    dispatcher, svc = make_dispatcher()
    encoded = "PFBMQw=="
    dispatcher.project_import_xml_b64(xml_b64=encoded)
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.PROJECT_IMPORT_XML_B64
    assert svc.last_request.params == {"xml_b64": encoded}


# ---------------------------------------------------------------------------
# POU tools
# ---------------------------------------------------------------------------


def test_pou_create_passes_name_type_language() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.pou_create(name="CounterFB", type="FunctionBlock", language="ST")
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.POU_CREATE
    assert svc.last_request.params == {
        "name": "CounterFB",
        "type": "FunctionBlock",
        "language": "ST",
    }


def test_pou_code_passes_path_and_implementation() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.pou_code(
        path=r"Application\CounterFB",
        declaration="VAR_INPUT\n    Enable : BOOL;\nEND_VAR",
        implementation="Output := Enable;",
    )
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.POU_CODE
    assert svc.last_request.params["path"] == r"Application\CounterFB"
    assert svc.last_request.params["declaration"] == "VAR_INPUT\n    Enable : BOOL;\nEND_VAR"
    assert svc.last_request.params["implementation"] == "Output := Enable;"


def test_pou_code_omits_empty_optional_fields() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.pou_code(path=r"Application\MyFB", implementation="x := 1;")
    assert svc.last_request is not None
    assert "declaration" not in svc.last_request.params


def test_pou_list_sends_correct_action() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.pou_list()
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.POU_LIST
    assert svc.last_request.params == {}


# ---------------------------------------------------------------------------
# Script tool
# ---------------------------------------------------------------------------


def test_script_execute_passes_script() -> None:
    dispatcher, svc = make_dispatcher()
    dispatcher.script_execute(script='print("hello")')
    assert svc.last_request is not None
    assert svc.last_request.action == ActionType.SCRIPT_EXECUTE
    assert svc.last_request.params == {"script": 'print("hello")'}


# ---------------------------------------------------------------------------
# Return value contract
# ---------------------------------------------------------------------------


def test_dispatcher_returns_json_string() -> None:
    dispatcher, _ = make_dispatcher(result={"success": True, "project_path": r"C:\work\demo.project"})
    raw = dispatcher.project_create(path=r"C:\work\demo.project")
    parsed = json.loads(raw)
    assert parsed["success"] is True
    assert parsed["project_path"] == r"C:\work\demo.project"


def test_dispatcher_propagates_success_true() -> None:
    dispatcher, _ = make_dispatcher(result={"success": True})
    raw = dispatcher.session_start()
    assert json.loads(raw)["success"] is True


def test_dispatcher_propagates_failure_body() -> None:
    dispatcher, _ = make_dispatcher(result={"success": False, "error": "CODESYS not running"})
    raw = dispatcher.session_status()
    parsed = json.loads(raw)
    assert parsed["success"] is False
    assert parsed["error"] == "CODESYS not running"
