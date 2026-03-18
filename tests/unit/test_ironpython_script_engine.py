from __future__ import annotations

import logging
from pathlib import Path

from ironpython_script_engine import IronPythonScriptEngineAdapter


def make_adapter() -> IronPythonScriptEngineAdapter:
    return IronPythonScriptEngineAdapter(
        codesys_path=Path(r"C:\Program Files\CODESYS\CODESYS\Common\CODESYS.exe"),
        logger=logging.getLogger("ironpython-script-engine-test"),
    )


def test_session_start_script_uses_global_scriptengine_system() -> None:
    adapter = make_adapter()

    script = adapter.build_execution("session.start", {}).script

    assert "import scriptengine" in script
    assert "scriptengine.system" in script


def test_project_create_script_contains_template_and_codesys_path() -> None:
    adapter = make_adapter()

    script = adapter.build_execution("project.create", {"path": r"C:\repo\Demo.project"}).script

    assert "scriptengine.projects.open" in script
    assert "Templates" in script
    assert r"C:\\Program Files\\CODESYS\\CODESYS\\Common\\CODESYS.exe" in script


def test_project_open_script_uses_global_projects_instance() -> None:
    adapter = make_adapter()
    project_path = r"C:\repo\Demo.project"

    script = adapter.build_execution("project.open", {"path": project_path}).script

    assert "scriptengine.projects.open" in script
    assert project_path.replace("\\", "\\\\") in script


def test_pou_create_script_uses_scriptengine_pou_type_mapping() -> None:
    adapter = make_adapter()

    script = adapter.build_execution(
        "pou.create",
        {"name": "MotorController", "type": "FunctionBlock", "language": "ST"},
    ).script

    assert "pou_container.create_pou" in script
    assert "scriptengine.PouType.FunctionBlock" in script
    assert "ImplementationLanguages.st" in script
    assert "MotorController" in script


def test_pou_code_script_uses_text_document_replace() -> None:
    adapter = make_adapter()

    script = adapter.build_execution(
        "pou.code",
        {
            "path": "Application/MotorController",
            "declaration": "FUNCTION_BLOCK MotorController",
            "implementation": "IF Enable THEN\nEND_IF;",
        },
    ).script

    assert "textual_declaration.replace(new_text=" in script
    assert "textual_implementation.replace(new_text=" in script
    assert "session.created_pous.get(target_name)" in script
    assert "for candidate in search_result" in script


def test_project_compile_script_uses_session_system_for_messages() -> None:
    adapter = make_adapter()

    script = adapter.build_execution("project.compile", {"clean_build": False}).script

    assert "system = session.system" in script
    assert "system.get_messages()" in script


def test_adapter_reports_engine_name() -> None:
    adapter = make_adapter()

    assert adapter.engine_name == "codesys-ironpython-scriptengine"


def test_adapter_reports_expected_capabilities() -> None:
    adapter = make_adapter()

    capabilities = adapter.capabilities()

    assert capabilities.session_start is True
    assert capabilities.session_status is True
    assert capabilities.script_execute is True
    assert capabilities.project_create is True
    assert capabilities.project_open is True
    assert capabilities.project_save is True
    assert capabilities.project_close is True
    assert capabilities.project_list is True
    assert capabilities.project_compile is True
    assert capabilities.pou_create is True
    assert capabilities.pou_code is True
    assert capabilities.pou_list is True


def test_build_execution_returns_project_compile_script_and_default_timeout() -> None:
    adapter = make_adapter()

    execution = adapter.build_execution("project.compile", {"clean_build": True})

    assert execution.timeout == 120
    assert "Starting project compilation script" in execution.script


def test_build_execution_returns_raw_script_for_script_execute() -> None:
    adapter = make_adapter()

    execution = adapter.build_execution("script.execute", {"script": "print('hi')"})

    assert execution.timeout == 60
    assert execution.script == "print('hi')"


def test_normalize_result_marks_missing_success_as_failure() -> None:
    adapter = make_adapter()

    result = adapter.normalize_result("project.create", {"project": {"name": "Demo"}})

    assert result == {
        "project": {"name": "Demo"},
        "success": False,
        "error": "Engine result missing success flag for action: project.create",
    }
