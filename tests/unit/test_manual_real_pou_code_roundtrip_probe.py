from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_pou_code_roundtrip_probe.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_pou_code_roundtrip_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_readback_script_targets_plc_prg() -> None:
    module = load_probe_module()

    script = module.build_readback_script("Application/PLC_PRG")

    assert 'raw_path = "Application/PLC_PRG"' in script
    assert "target = session.created_pous.get(target_name)" in script
    assert 'resolved_via = "session.created_pous"' in script
    assert 'requested_paths.append(candidate)' in script
    assert 'application = project.find("Application")' in script
    assert '"matched_path": matched_path' in script
    assert '"resolved_via": resolved_via' in script
    assert '"application_children": application_children' in script
    assert '"session_created_pous": session_created_pous' in script
    assert '"implementation_contains_missing_var": "MissingVar" in implementation_text' in script
    assert '"resolved_name": getattr(target, \'name\', target_name)' in script


def test_is_expected_roundtrip_response_requires_successful_missing_var_readback() -> None:
    module = load_probe_module()

    assert module.is_expected_roundtrip_response(
        200,
        {
            "success": True,
            "implementation_contains_missing_var": True,
        },
    )
    assert module.is_expected_roundtrip_response(200, {"success": True, "implementation_contains_missing_var": False}) is False
    assert module.is_expected_roundtrip_response(500, {"success": True, "implementation_contains_missing_var": True}) is False


def test_extract_pou_names_reads_pou_list_payload() -> None:
    module = load_probe_module()

    assert module.extract_pou_names({"pous": [{"name": "PLC_PRG"}, {"name": "MotorController"}]}) == [
        "PLC_PRG",
        "MotorController",
    ]
    assert module.extract_pou_names({"pous": [None, {"name": 3}]}) == []
