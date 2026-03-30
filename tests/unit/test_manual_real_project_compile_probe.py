from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_project_compile_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_project_compile_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_steps_returns_three_steps_in_order() -> None:
    module = load_probe_module()

    steps = module.build_steps(r"C:\temp\compile_test.project")

    assert [name for name, _script in steps] == [
        "create_project_with_plc_prg",
        "build",
        "generate_code",
    ]


def test_create_project_step_uses_proven_skeleton() -> None:
    module = load_probe_module()

    script = module.build_create_project_with_plc_prg_step(r"C:\temp\compile_test.project")

    assert "scriptengine.projects.create(" in script
    assert "projects.open(" not in script
    assert "save_as(" not in script
    assert "project.add(" in script
    assert "app.create_pou(" in script
    assert "app.create_task_configuration()" in script
    assert "task_config.create_task(" in script
    assert "existing_task.pous.add(" in script
    assert "session.active_project = project" in script
    assert "session.created_pous" in script
    assert '"step": "create_project_with_plc_prg"' in script


def test_build_step_calls_application_build() -> None:
    module = load_probe_module()

    script = module.build_build_step()

    assert "application.build()" in script
    assert '"step": "build"' in script
    # no .format() — must use literal braces
    assert "{{" not in script


def test_generate_code_step_calls_application_generate_code() -> None:
    module = load_probe_module()

    script = module.build_generate_code_step()

    assert "application.generate_code()" in script
    assert '"step": "generate_code"' in script
    # no .format() — must use literal braces
    assert "{{" not in script


def test_build_steps_embeds_default_device_values() -> None:
    module = load_probe_module()

    steps = module.build_steps(r"C:\temp\compile_test.project")
    create_script = dict(steps)["create_project_with_plc_prg"]

    assert "CODESYS Control Win V3 x64" in create_script
    assert "0000 0004" in create_script
    assert "3.5.20.50" in create_script
