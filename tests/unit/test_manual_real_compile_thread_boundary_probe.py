from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_compile_thread_boundary_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_compile_thread_boundary_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_step_names_follow_reduction_order() -> None:
    module = load_probe_module()

    assert module.step_names() == [
        "setup_only",
        "readback_only",
        "build_only",
        "build_and_generate_only",
        "clear_messages_then_build",
        "build_then_get_messages",
        "build_then_get_message_objects",
        "full_current_compile_wrapper",
    ]


def test_build_only_step_is_smallest_build_candidate() -> None:
    module = load_probe_module()

    script = module.build_build_only_step()

    assert "application.build()" in script
    assert "application.generate_code()" not in script
    assert "clear_messages(" not in script
    assert "get_messages()" not in script
    assert '"step": "build_only"' in script


def test_clear_messages_then_build_step_targets_message_clear_api() -> None:
    module = load_probe_module()

    script = module.build_clear_messages_then_build_step()

    assert "system.get_message_categories(True)" in script
    assert "system.clear_messages(category)" in script
    assert "application.build()" in script
    assert "get_message_objects(" not in script
    assert '"step": "clear_messages_then_build"' in script


def test_build_then_get_messages_step_targets_text_harvest_only() -> None:
    module = load_probe_module()

    script = module.build_build_then_get_messages_step()

    assert "application.build()" in script
    assert "system.get_messages()" in script
    assert "get_message_objects(" not in script
    assert "clear_messages(" not in script
    assert '"step": "build_then_get_messages"' in script


def test_build_then_get_message_objects_step_targets_object_harvest_only() -> None:
    module = load_probe_module()

    script = module.build_build_then_get_message_objects_step()

    assert "application.build()" in script
    assert "system.get_message_categories(True)" in script
    assert "system.get_message_objects(category)" in script
    assert "clear_messages(" not in script
    assert '"step": "build_then_get_message_objects"' in script


def test_full_current_compile_wrapper_step_matches_current_engine_script() -> None:
    module = load_probe_module()

    script = module.build_full_current_compile_wrapper_step(r"C:\Program Files\CODESYS\CODESYS\Common\CODESYS.exe")

    assert "safe_message_harvest = True" in script
    assert "application.build()" in script
    assert "application.generate_code()" not in script
    assert "system.get_message_categories(True)" in script
    assert "system.clear_messages(category)" in script
    assert "not safe_message_harvest" in script


def test_build_step_script_returns_none_for_setup_only() -> None:
    module = load_probe_module()

    assert module.build_step_script("setup_only", codesys_path=r"C:\demo\CODESYS.exe") is None


def test_build_parser_defaults_to_full_wrapper_step() -> None:
    module = load_probe_module()

    parser = module.build_parser()
    args = parser.parse_args([])

    assert args.step == "full_current_compile_wrapper"
    assert args.include_readback is False
    assert args.script_timeout == 300
