from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "direct_codesys_persistent_host_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("direct_codesys_persistent_host_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_mode_names_follow_expected_order() -> None:
    module = load_probe_module()

    assert module.mode_names() == [
        "single_request_full_build",
        "two_request_session_flow",
    ]


def test_build_probe_env_sets_pipe_name_and_exec_mode() -> None:
    module = load_probe_module()

    result = module.build_probe_env(
        {"PATH": "demo"},
        {"CODESYS_API_CODESYS_PATH": r"C:\demo\CODESYS.exe"},
        pipe_name="codesys_direct_pipe",
        exec_mode="primary",
    )

    assert result["PATH"] == "demo"
    assert result["CODESYS_API_CODESYS_PATH"] == r"C:\demo\CODESYS.exe"
    assert result["CODESYS_API_PIPE_NAME"] == "codesys_direct_pipe"
    assert result["CODESYS_DIRECT_SESSION_EXEC_MODE"] == "primary"


def test_host_script_supports_background_and_primary_execution_modes() -> None:
    module = load_probe_module()

    script = module.build_host_script()

    assert 'EXEC_MODE = os.environ.get("CODESYS_DIRECT_SESSION_EXEC_MODE", "background")' in script
    assert 'if EXEC_MODE == "primary":' in script
    assert 'self.process_named_pipe_requests()' in script
    assert 'threading.Thread(target=self.process_named_pipe_requests)' in script
    assert 'result["host_exec_mode"] = EXEC_MODE' in script


def test_single_request_script_matches_direct_build_shape() -> None:
    module = load_probe_module()

    script = module.build_single_request_full_build_script(r"C:\temp\demo.project")

    assert 'scriptengine.projects.create("C:\\\\temp\\\\demo.project", True)' in script
    assert 'project.add("CODESYS Control Win V3 x64", 4096, "0000 0004", "3.5.20.50")' in script
    assert 'name="PLC_PRG"' in script
    assert 'task_config.create_task("MainTask")' in script
    assert 'pou.textual_implementation.replace(new_text="MissingVar := TRUE;")' in script
    assert "app.build()" in script
    assert 'system.get_messages()' in script
    assert 'system.get_message_categories(True)' in script
    assert '"contains_missing_var":' in script


def test_two_request_scripts_split_create_and_build() -> None:
    module = load_probe_module()

    create_script = module.build_session_create_and_write_script(r"C:\temp\demo.project")
    build_script = module.build_session_build_and_messages_script()

    assert "app.build()" not in create_script
    assert 'pou.textual_implementation.replace(new_text="MissingVar := TRUE;")' in create_script
    assert '"step": "session_create_and_write"' in create_script

    assert "app.build()" in build_script
    assert 'system.get_messages()' in build_script
    assert '"step": "session_build_and_messages"' in build_script


def test_build_parser_defaults_to_single_request_background_mode() -> None:
    module = load_probe_module()

    parser = module.build_parser()
    args = parser.parse_args([])

    assert args.mode == "single_request_full_build"
    assert args.exec_mode == "background"
    assert args.timeout == 180
    assert args.keep_open is False
