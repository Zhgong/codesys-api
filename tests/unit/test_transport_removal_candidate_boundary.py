from __future__ import annotations

from pathlib import Path


def test_host_side_file_transport_modules_are_deleted() -> None:
    assert not Path("legacy_file_transport.py").exists()
    assert not Path("file_ipc.py").exists()


def test_no_production_code_imports_deleted_file_transport_modules() -> None:
    offenders: list[str] = []

    for path in Path(".").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if (
            "from legacy_file_transport import" in source
            or "import legacy_file_transport" in source
            or "from file_ipc import" in source
            or "import file_ipc" in source
        ):
            offenders.append(path.name)

    assert offenders == []
