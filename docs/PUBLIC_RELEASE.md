# Public Release Preparation

## Summary

This checklist prepares `codesys-tools` for a future public package release without uploading anything yet.

Current target posture:

- Windows-only
- experimental
- local CODESYS dependency required
- published through GitHub Actions using Trusted Publishing

## Public Release Gate

Run from the repository root:

```powershell
python scripts\run_baseline.py
python scripts\build_release.py
python scripts\check_public_release.py
```

GitHub Actions release automation now exists:

- `.github/workflows/ci.yml`
- `.github/workflows/release-build.yml`
- `.github/workflows/publish.yml`

## Required Public Claims

Before calling the package public-release-ready, verify that:

- `README.md` presents the package as Windows experimental
- installation instructions match the current package shape
- `named_pipe` is the only supported runtime transport
- local CODESYS dependency is stated clearly
- public docs do not mention removed file-based transport or lifecycle mechanisms

## Required Packaging Checks

- wheel and sdist build successfully
- wheel filename matches the current `project.version`
- installed `codesys --help` succeeds
- installed `codesys-server --help` succeeds
- packaged `PERSISTENT_SESSION.py` resolves
- packaged `ScriptLib/` resolves

## Not Part Of This Phase

- PyPI upload
- installer creation
- cross-platform support
- support commitments beyond Windows experimental

## Trusted Publishing Setup

Before the first public upload, configure:

- a `testpypi` GitHub Environment
- a `pypi` GitHub Environment
- matching Trusted Publisher entries on TestPyPI and PyPI

The repository should publish through the manual `Publish Package` workflow, not through long-lived API tokens.

## Outcome

When this checklist is green, the project is **PyPI-ready in shape**, but still not published.
