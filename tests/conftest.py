from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re
import shutil
import uuid

from _repo_bootstrap import bootstrap_src_path
import pytest


bootstrap_src_path()


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Iterator[Path]:
    # Avoid pytest's Windows temp-root ACL issue by keeping test scratch dirs inside the repo.
    base_dir = Path(".codex_test_tmp") / "pytest"
    base_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)
    temp_dir = base_dir / "{0}_{1}".format(safe_name, uuid.uuid4().hex)
    temp_dir.mkdir()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
