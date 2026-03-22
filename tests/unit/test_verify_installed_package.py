from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_verify_installed_package_supports_wheel_testpypi_and_pypi_targets() -> None:
    script = (REPO_ROOT / "scripts" / "verify_installed_package.py").read_text(encoding="utf-8")

    assert 'choices=["wheel", "testpypi", "pypi"]' in script
    assert "--version" in script
    assert "--wheel-path" in script
    assert 'PACKAGE_NAME = "codesys-tools"' in script
    assert 'requirement = f"{PACKAGE_NAME}=={args.version}"' in script
    assert "https://test.pypi.org/simple/" in script


def test_verify_installed_package_checks_entrypoints_and_packaged_assets() -> None:
    script = (REPO_ROOT / "scripts" / "verify_installed_package.py").read_text(encoding="utf-8")

    assert "codesys-tools.exe" in script
    assert "codesys-tools-server.exe" in script
    assert "packaged_persistent_script" in script
    assert "packaged_script_lib_dir" in script
