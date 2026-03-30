from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_root_keeps_only_formal_entrypoints_and_metadata() -> None:
    expected_root_files = {
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "HTTP_SERVER.py",
        "LICENSE",
        "PERSISTENT_SESSION.py",
        "README.md",
        "_repo_bootstrap.py",
        "codesys_cli.py",
        "install.bat",
        "pyproject.toml",
        "run_cli.bat",
        "uninstall.bat",
        "windows_service.py",
    }
    allowed_local_files = {
        ".env.real-codesys.local",
    }

    actual_root_files = {path.name for path in REPO_ROOT.iterdir() if path.is_file()} - allowed_local_files

    assert actual_root_files == expected_root_files


def test_repo_root_no_longer_contains_plain_module_shims_or_root_docs() -> None:
    forbidden_root_entries = {
        "BASELINE.md",
        "CLI_USAGE.md",
        "CONTINUE_TOMORROW.md",
        "STRATEGIC_PLAN.md",
        "action_layer.py",
        "api_key_store.py",
        "app_runtime.py",
        "codesys_e2e_policy.py",
        "codesys_process.py",
        "engine_adapter.py",
        "ironpython_script_engine.py",
        "named_pipe_transport.py",
        "runtime_transport.py",
        "script_executor.py",
        "server_config.py",
        "server_logic.py",
        "session_transport.py",
        "transport_result.py",
    }

    actual_root_names = {path.name for path in REPO_ROOT.iterdir()}

    assert forbidden_root_entries.isdisjoint(actual_root_names)
