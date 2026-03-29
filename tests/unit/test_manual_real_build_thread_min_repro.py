from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts" / "manual" / "real_build_thread_min_repro.py"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_build_thread_min_repro", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_step_names_follow_min_repro_order() -> None:
    module = load_probe_module()

    assert module.step_names() == [
        "background_noop",
        "background_resolve_application_only",
        "background_build_only_min",
        "primary_thread_build_only_min",
        "primary_thread_generate_code_only_min",
    ]


def test_background_resolve_application_only_does_not_build() -> None:
    module = load_probe_module()

    script = module.build_background_resolve_application_only_step()

    assert "session.active_project.active_application" in script
    assert "app.build()" not in script
    assert "execute_on_primary_thread" not in script
    assert '"step": "background_resolve_application_only"' in script


def test_background_build_only_min_is_plain_background_build() -> None:
    module = load_probe_module()

    script = module.build_background_build_only_min_step()

    assert "session.active_project.active_application" in script
    assert "app.build()" in script
    assert "app.generate_code()" not in script
    assert "execute_on_primary_thread" not in script
    assert "get_message_categories(" not in script
    assert '"step": "background_build_only_min"' in script


def test_primary_thread_build_only_min_uses_execute_on_primary_thread() -> None:
    module = load_probe_module()

    script = module.build_primary_thread_build_only_min_step()

    assert "execute_on_primary_thread" in script
    assert "def run_on_primary_thread():" in script
    assert "app = session.active_project.active_application" in script
    assert "app.build()" in script
    assert "app.generate_code()" not in script
    assert '"step": "primary_thread_build_only_min"' in script


def test_primary_thread_generate_code_only_min_uses_execute_on_primary_thread() -> None:
    module = load_probe_module()

    script = module.build_primary_thread_generate_code_only_min_step()

    assert "execute_on_primary_thread" in script
    assert "def run_on_primary_thread():" in script
    assert "app = session.active_project.active_application" in script
    assert "app.generate_code()" in script
    assert "app.build()" not in script
    assert '"step": "primary_thread_generate_code_only_min"' in script


def test_build_step_script_dispatches_expected_step() -> None:
    module = load_probe_module()

    script = module.build_step_script("background_noop")

    assert '"step": "background_noop"' in script


def test_build_parser_defaults_to_background_build_only_min() -> None:
    module = load_probe_module()

    parser = module.build_parser()
    args = parser.parse_args([])

    assert args.step == "background_build_only_min"
    assert args.script_timeout == 300
