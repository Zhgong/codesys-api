from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "profile_launch_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("profile_launch_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_probe_env_sets_named_pipe_and_pipe_name() -> None:
    module = load_probe_module()

    result = module.build_probe_env(
        {"PATH": "demo"},
        {"CODESYS_API_CODESYS_PATH": "C:\\demo\\CODESYS.exe"},
        "codesys_probe_pipe",
    )

    assert result["PATH"] == "demo"
    assert result["CODESYS_API_CODESYS_PATH"] == "C:\\demo\\CODESYS.exe"
    assert result["CODESYS_API_TRANSPORT"] == "named_pipe"
    assert result["CODESYS_API_PIPE_NAME"] == "codesys_probe_pipe"


def test_build_launch_spec_shell_string_matches_manual_success_shape() -> None:
    module = load_probe_module()

    spec = module.build_launch_spec(
        "shell_string",
        Path(r"C:\Program Files\CODESYS\Common\CODESYS.exe"),
        "Demo Profile",
        Path(r"C:\repo\PERSISTENT_SESSION.py"),
    )

    assert spec.shell is True
    assert spec.command == (
        '"C:\\Program Files\\CODESYS\\Common\\CODESYS.exe" '
        '--profile="Demo Profile" '
        '--runscript="C:\\repo\\PERSISTENT_SESSION.py"'
    )


def test_build_launch_spec_argv_modes_keep_mode_specific_argument_shape() -> None:
    module = load_probe_module()
    codesys_path = Path(r"C:\Program Files\CODESYS\Common\CODESYS.exe")
    script_path = Path(r"C:\repo\PERSISTENT_SESSION.py")

    quoted = module.build_launch_spec("argv_quoted", codesys_path, "Demo Profile", script_path)
    plain = module.build_launch_spec("argv_plain", codesys_path, "Demo Profile", script_path)

    assert quoted.shell is False
    assert plain.shell is False
    assert quoted.command == [
        str(codesys_path),
        '--profile="Demo Profile"',
        '--runscript="C:\\repo\\PERSISTENT_SESSION.py"',
    ]
    assert plain.command == [
        str(codesys_path),
        "--profile=Demo Profile",
        "--runscript=C:\\repo\\PERSISTENT_SESSION.py",
    ]


def test_new_codesys_process_ids_returns_only_new_codesys_processes() -> None:
    module = load_probe_module()

    result = module.new_codesys_process_ids([100, 200], [200, 300, 400])

    assert result == [300, 400]
