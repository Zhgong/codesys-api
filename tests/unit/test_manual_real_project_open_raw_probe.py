from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_project_open_raw_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_project_open_raw_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_open_only_script_calls_projects_open_without_save_as() -> None:
    module = load_probe_module()

    script = module.build_open_only_script(r"C:\temp\demo.project", "open_existing_project_only")

    assert 'project = scriptengine.projects.open(project_path)' in script
    assert 'project.save_as(' not in script
    assert '"step": step_name' in script


def test_resolve_open_target_for_template_mode_uses_template_path() -> None:
    module = load_probe_module()

    class Args:
        mode = "template"
        project_path = None

    open_path, step_name = module.resolve_open_target(
        Args(),
        {"CODESYS_API_CODESYS_PATH": r"C:\Program Files\CODESYS 3.5.20.50\CODESYS\Common\CODESYS.exe"},
    )

    assert open_path == r"C:\Program Files\CODESYS 3.5.20.50\CODESYS\Templates\Standard.project"
    assert step_name == "open_template_only"


def test_resolve_open_target_for_existing_mode_requires_project_path() -> None:
    module = load_probe_module()

    class Args:
        mode = "existing"
        project_path = None

    try:
        module.resolve_open_target(Args(), {"CODESYS_API_CODESYS_PATH": "unused"})
    except ValueError as exc:
        assert "--project-path is required" in str(exc)
    else:
        raise AssertionError("Expected ValueError when project_path is missing")
