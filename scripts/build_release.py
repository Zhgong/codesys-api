from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build wheel and sdist release artifacts for codesys-api.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not remove existing dist/ and build/ directories before building.",
    )
    return parser


def _ensure_build_module() -> None:
    try:
        __import__("build.__main__")
    except Exception as exc:  # pragma: no cover - exercised in script smoke only
        raise SystemExit(
            "The 'build' package is required. Install it with: "
            f"{sys.executable} -m pip install build"
        ) from exc


def _clean_previous_artifacts() -> None:
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    shutil.rmtree(BUILD_DIR, ignore_errors=True)


def _run_build() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "build"],
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _load_project_metadata() -> tuple[str, str]:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = data["project"]
    return str(project["name"]), str(project["version"])


def _verify_artifact_names(artifacts: list[Path]) -> None:
    project_name, version = _load_project_metadata()
    distribution_name = project_name.replace("-", "_")
    expected_wheel_prefix = f"{distribution_name}-{version}-"
    expected_sdist_name = f"{distribution_name}-{version}.tar.gz"

    wheel_matches = [artifact for artifact in artifacts if artifact.name.startswith(expected_wheel_prefix)]
    sdist_matches = [artifact for artifact in artifacts if artifact.name == expected_sdist_name]

    if not wheel_matches:
        raise SystemExit(
            "Build produced no wheel matching the current version. "
            f"Expected prefix: {expected_wheel_prefix}"
        )

    if not sdist_matches:
        raise SystemExit(
            "Build produced no sdist matching the current version. "
            f"Expected name: {expected_sdist_name}"
        )


def _print_artifacts() -> None:
    artifacts = sorted(DIST_DIR.glob("*"))
    if not artifacts:
        raise SystemExit("Build finished without producing any files in dist/.")

    _verify_artifact_names(artifacts)

    print("Release artifacts:")
    for artifact in artifacts:
        print(f"- {artifact.relative_to(REPO_ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _ensure_build_module()

    if not args.keep_existing:
        _clean_previous_artifacts()

    _run_build()
    _print_artifacts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
