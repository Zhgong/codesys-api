from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_project_skeleton_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_project_skeleton_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_steps_returns_seven_steps_in_order() -> None:
    module = load_probe_module()

    steps = module.build_steps(r"C:\temp\skeleton_test.project")

    assert [name for name, _script in steps] == [
        "create_empty_project",
        "add_device",
        "resolve_active_application",
        "create_plc_prg",
        "create_task_configuration",
        "create_main_task",
        "assign_plc_prg_to_task",
    ]


def test_create_empty_project_step_uses_projects_create() -> None:
    module = load_probe_module()

    script = module.build_create_empty_project_step(r"C:\temp\skeleton_test.project")

    assert "scriptengine.projects.create(" in script
    assert "projects.open(" not in script
    assert "save_as(" not in script
    assert '"step": "create_empty_project"' in script
    assert "session.active_project = project" in script


def test_add_device_step_uses_project_add() -> None:
    module = load_probe_module()

    script = module.build_add_device_step("My Device", 4096, "0000 0004", "3.5.20.50")

    assert "project.add(" in script
    assert "My Device" in script
    assert '"step": "add_device"' in script
    assert "session.skeleton_device" in script


def test_resolve_active_application_step_stores_skeleton_app() -> None:
    module = load_probe_module()

    script = module.build_resolve_active_application_step()

    assert "session.skeleton_app" in script
    assert "is_application" in script
    assert '"step": "resolve_active_application"' in script
    # no .format() call — script must use literal { } not {{ }}
    assert "{{" not in script


def test_create_plc_prg_step_uses_create_pou() -> None:
    module = load_probe_module()

    script = module.build_create_plc_prg_step("PLC_PRG")

    assert "app.create_pou(" in script
    assert "PLC_PRG" in script
    assert "PouType.Program" in script
    assert "session.created_pous" in script
    assert '"step": "create_plc_prg"' in script


def test_create_task_configuration_step_uses_create_task_configuration() -> None:
    module = load_probe_module()

    script = module.build_create_task_configuration_step()

    assert "app.create_task_configuration()" in script
    assert "session.skeleton_task_config" in script
    assert '"step": "create_task_configuration"' in script
    # no .format() call — script must use literal { } not {{ }}
    assert "{{" not in script


def test_create_main_task_step_uses_create_task() -> None:
    module = load_probe_module()

    script = module.build_create_main_task_step("MainTask")

    assert 'task_config.create_task(task_name)' in script
    assert "MainTask" in script
    assert "session.skeleton_main_task" in script
    assert '"step": "create_main_task"' in script


def test_assign_plc_prg_to_task_step_uses_pous_add() -> None:
    module = load_probe_module()

    script = module.build_assign_plc_prg_to_task_step("PLC_PRG")

    assert "task.pous" in script
    assert "task_pous.add(" in script
    assert "PLC_PRG" in script
    assert '"step": "assign_plc_prg_to_task"' in script


def test_build_steps_default_device_values() -> None:
    module = load_probe_module()

    steps = module.build_steps(r"C:\temp\skeleton_test.project")
    add_device_script = dict(steps)["add_device"]

    assert "CODESYS Control Win V3 x64" in add_device_script
    assert "0000 0004" in add_device_script
    assert "3.5.20.50" in add_device_script
