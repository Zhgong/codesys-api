from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_readme_states_public_support_boundary() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Windows-only" in readme
    assert "experimental" in readme
    assert "local CODESYS" in readme
    assert "named_pipe" in readme
    assert "codesys-tools" in readme
    assert "codesys" in readme
    assert "codesys-server" in readme


def test_public_release_docs_link_current_public_entrypoints() -> None:
    release_doc = (REPO_ROOT / "docs" / "PUBLIC_RELEASE.md").read_text(encoding="utf-8")
    install_doc = (REPO_ROOT / "docs" / "INSTALLATION_GUIDE.md").read_text(encoding="utf-8")

    assert "python scripts\\check_public_release.py" in release_doc
    assert "Windows-only" in release_doc
    assert "experimental" in release_doc
    assert "codesys --help" in install_doc
    assert "codesys-server --help" in install_doc
    assert "named_pipe" in install_doc
