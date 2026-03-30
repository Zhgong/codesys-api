from __future__ import annotations

from codesys_api.server_entry import build_parser as build_server_entry_parser
from codesys_api.http_server import build_parser as build_http_server_parser


def test_server_entry_help_includes_env_vars_auth_and_compile_notes() -> None:
    help_text = build_server_entry_parser().format_help()

    assert "CODESYS_API_CODESYS_PATH" in help_text
    assert "CODESYS_API_CODESYS_PROFILE_PATH" in help_text
    assert "CODESYS_API_CODESYS_NO_UI" in help_text
    assert "Authorization: ApiKey <key>" in help_text
    assert "named_pipe only" in help_text
    assert "FUNCTION_BLOCK/PROGRAM header line" in help_text


def test_repo_local_http_server_help_matches_installed_server_help() -> None:
    help_text = build_http_server_parser().format_help()

    assert "CODESYS_API_CODESYS_PATH" in help_text
    assert "Authorization: ApiKey <key>" in help_text
    assert "HTTP is the primary workflow for persistent multi-step operations" in help_text
