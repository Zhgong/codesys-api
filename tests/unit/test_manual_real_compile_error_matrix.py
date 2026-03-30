from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "manual" / "real_compile_error_matrix.py"


def load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_compile_error_matrix", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_payload_contains_missing_var_matches_json_text() -> None:
    module = load_script_module()

    assert module.payload_contains_missing_var({"messages": [{"text": "C0032: MissingVar"}]}) is True
    assert module.payload_contains_missing_var({"messages": [{"text": "All good"}]}) is False


def test_extract_error_count_reads_message_counts() -> None:
    module = load_script_module()

    assert module.extract_error_count({"message_counts": {"errors": 2, "warnings": 0, "infos": 0}}) == 2
    assert module.extract_error_count({"message_counts": {"errors": "bad"}}) is None
    assert module.extract_error_count({}) is None
