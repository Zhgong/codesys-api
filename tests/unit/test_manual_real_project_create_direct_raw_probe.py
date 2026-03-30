from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_project_create_direct_raw_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_project_create_direct_raw_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_steps_uses_direct_create_then_inspect() -> None:
    module = load_probe_module()

    steps = module.build_steps(r"C:\temp\demo.project")

    assert [name for name, _script in steps] == [
        "create_project_only",
        "inspect_project_structure",
    ]


def test_create_project_only_step_uses_projects_create_not_template_open() -> None:
    module = load_probe_module()

    script = module.build_create_project_only_step(r"C:\temp\demo.project")

    assert 'project = scriptengine.projects.create(target_path, True)' in script
    assert 'scriptengine.projects.open(' not in script
    assert 'save_as(' not in script
    assert '"step": "create_project_only"' in script


def test_inspect_project_structure_step_checks_expected_project_path() -> None:
    module = load_probe_module()

    script = module.build_inspect_project_structure_step(r"C:\temp\demo.project")

    assert 'expected_project_path = "C:\\\\temp\\\\demo.project"' in script
    assert 'application_names' in script
    assert 'device_names' in script
    assert '"step": "inspect_project_structure"' in script
