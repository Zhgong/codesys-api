from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path


def bootstrap_src_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def alias_module(wrapper_name: str, target_name: str) -> None:
    bootstrap_src_path()
    module = import_module(target_name)
    sys.modules[wrapper_name] = module

