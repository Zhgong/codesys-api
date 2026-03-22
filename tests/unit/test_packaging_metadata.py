from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_defines_build_backend_and_console_scripts() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'build-backend = "setuptools.build_meta"' in pyproject
    assert 'name = "codesys-tools"' in pyproject
    assert 'version = "0.2.0"' in pyproject
    assert 'requires-python = ">=3.13"' in pyproject
    assert 'codesys-tools = "codesys_api.cli_entry:main"' in pyproject
    assert 'codesys-tools-server = "codesys_api.server_entry:main"' in pyproject
    assert 'Programming Language :: Python :: 3.13' in pyproject
    assert 'Programming Language :: Python :: 3.14' in pyproject
    assert 'authors = [' in pyproject
    assert 'keywords = [' in pyproject
    assert '[project.urls]' in pyproject
    assert 'Homepage = "https://github.com/Zhgong/codesys-api"' in pyproject
    assert 'Development Status :: 3 - Alpha' in pyproject


def test_root_wrappers_delegate_to_package_entrypoints() -> None:
    cli_wrapper = (REPO_ROOT / "codesys_cli.py").read_text(encoding="utf-8")
    server_wrapper = (REPO_ROOT / "HTTP_SERVER.py").read_text(encoding="utf-8")

    assert 'alias_module(__name__, "codesys_api.cli_entry")' in cli_wrapper
    assert 'from codesys_api.cli_entry import main' in cli_wrapper
    assert 'alias_module(__name__, "codesys_api.http_server")' in server_wrapper
    assert 'from codesys_api.http_server import main' in server_wrapper
