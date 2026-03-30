from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "direct_codesys_runscript_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("direct_codesys_runscript_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_mode_names_follow_expected_order() -> None:
    module = load_probe_module()

    assert module.mode_names() == [
        "create_and_build_clean",
        "create_and_build_error",
        "create_build_generate",
    ]


def test_build_mode_settings_for_error_mode_injects_missing_var() -> None:
    module = load_probe_module()

    settings = module.build_mode_settings("create_and_build_error")

    assert settings["implementation_text"] == "MissingVar := TRUE;"
    assert settings["run_generate_code"] is False


def test_build_mode_settings_for_generate_mode_enables_generate_code() -> None:
    module = load_probe_module()

    settings = module.build_mode_settings("create_build_generate")

    assert settings["implementation_text"] == ""
    assert settings["run_generate_code"] is True


def test_build_launch_command_uses_profile_and_runscript_without_no_ui_by_default() -> None:
    module = load_probe_module()

    command = module.build_launch_command(
        Path(r"C:\Program Files\CODESYS\Common\CODESYS.exe"),
        "Demo Profile",
        Path(r"C:\temp\probe.py"),
    )

    assert command == (
        '"C:\\Program Files\\CODESYS\\Common\\CODESYS.exe" '
        '--profile="Demo Profile" '
        '--runscript="C:\\temp\\probe.py"'
    )


def test_generated_error_script_contains_minimal_build_flow() -> None:
    module = load_probe_module()

    script = module.build_generated_script(
        r"C:\temp\demo.project",
        r"C:\temp\result.json",
        "create_and_build_error",
    )

    assert "scriptengine.projects.create(PROJECT_PATH, True)" in script
    assert 'project.add("CODESYS Control Win V3 x64", 4096, "0000 0004", "3.5.20.50")' in script
    assert 'name="PLC_PRG"' in script
    assert 'task_config.create_task("MainTask")' in script
    assert 'pou.textual_implementation.replace(new_text=IMPLEMENTATION_TEXT)' in script
    assert 'IMPLEMENTATION_TEXT = "MissingVar := TRUE;"' in script
    assert "app.build()" in script
    assert "app.generate_code()" not in script
    assert 'system.get_messages()' in script
    assert 'system.get_message_categories(True)' in script
    assert '"contains_missing_var": False' in script
    assert '"build_returned": False' in script


def test_generated_generate_script_includes_generate_code_without_missing_var() -> None:
    module = load_probe_module()

    script = module.build_generated_script(
        r"C:\temp\demo.project",
        r"C:\temp\result.json",
        "create_build_generate",
    )

    assert 'IMPLEMENTATION_TEXT = ""' in script
    assert "app.build()" in script
    assert "app.generate_code()" in script
    assert 'system.get_messages()' in script
    assert '"generate_code_returned": False' in script


def test_build_parser_defaults_to_error_mode() -> None:
    module = load_probe_module()

    parser = module.build_parser()
    args = parser.parse_args([])

    assert args.mode == "create_and_build_error"
    assert args.timeout == 180
    assert args.keep_open is False
