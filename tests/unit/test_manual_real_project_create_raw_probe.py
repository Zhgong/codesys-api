from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_project_create_raw_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_project_create_raw_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_derive_template_path_uses_codesys_install_layout() -> None:
    module = load_probe_module()

    assert module.derive_template_path(
        r"C:\Program Files\CODESYS 3.5.20.50\CODESYS\Common\CODESYS.exe"
    ) == r"C:\Program Files\CODESYS 3.5.20.50\CODESYS\Templates\Standard.project"


def test_build_steps_includes_expected_project_create_breakpoints() -> None:
    module = load_probe_module()

    steps = module.build_steps(r"C:\temp\demo.project", r"C:\templates\Standard.project")

    assert [name for name, _script in steps] == [
        "open_template",
        "replace_device",
        "resolve_application",
        "create_program",
        "create_task",
        "status",
    ]


def test_open_template_step_uses_script_execute_only() -> None:
    module = load_probe_module()

    script = module.build_open_template_step(r"C:\temp\demo.project", r"C:\templates\Standard.project")

    assert 'scriptengine.projects.open(template_path)' in script
    assert 'project.save_as(target_path)' in script
    assert 'session.active_project = project' in script
    assert '"step": "open_template"' in script


def test_replace_device_step_contains_single_device_operation() -> None:
    module = load_probe_module()

    script = module.build_replace_device_step()

    assert 'project.add(desired_device_name, desired_device_type, desired_device_id, desired_device_version)' in script
    assert '"step": "replace_device"' in script


def test_status_step_compares_expected_project_path() -> None:
    module = load_probe_module()

    script = module.build_project_status_step(r"C:\temp\demo.project")

    assert 'expected_project_path = "C:\\\\temp\\\\demo.project"' in script
    assert 'actual_project_path' in script
    assert '"step": "status"' in script
