# Packaging

## Summary

The repository now supports two packaging levels:

- local install: `pip install .`
- release artifact build: `python scripts\build_release.py`
- public release prep gate: `python scripts\check_public_release.py`

The immediate goal of packaging phase 2 is **repeatable internal distribution**, not PyPI.

For the release checklist and internal install flow, see [RELEASE.md](RELEASE.md).
For public package preparation, see [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md).

## Prerequisites

- Python 3.14+
- Windows environment
- `build` package installed locally:

```powershell
python -m pip install build
```

## Build Release Artifacts

Run the release helper from the repository root:

```powershell
python scripts\build_release.py
```

By default it removes previous `dist/` and `build/` directories, runs `python -m build`, and prints the generated artifacts.

To keep existing build directories:

```powershell
python scripts\build_release.py --keep-existing
```

Expected artifacts:

- `dist/*.whl`
- `dist/*.tar.gz`

## Wheel Smoke Test

Recommended verification flow in a clean virtual environment:

```powershell
python -m venv C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\python.exe -m pip install --upgrade pip
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\python.exe -m pip install dist\codesys_tools-*.whl
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\codesys-tools.exe --help
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\codesys-tools-server.exe --help
```

Installed package smoke should also confirm:

- packaged `PERSISTENT_SESSION.py` resolves
- packaged `ScriptLib/` resolves
- default API key path remains `%APPDATA%\codesys-api\api_keys.json`

## Release Gate

Before treating a build as releasable, run:

```powershell
python scripts\run_baseline.py
python scripts\build_release.py
```

Then verify wheel install smoke in a clean environment.

## Internal Install and Upgrade

Install from a built wheel:

```powershell
python -m pip install dist\codesys_tools-*.whl
```

Upgrade an existing installation:

```powershell
python -m pip install --upgrade dist\codesys_tools-*.whl
```

The formal internal release sequence is documented in [RELEASE.md](RELEASE.md).

## Current Boundaries

- Windows-first only
- `named_pipe` remains the only runtime transport
- CLI entrypoints remain:
  - `codesys-tools`
  - `codesys-tools-server`
- This phase does **not** include:
  - PyPI publishing
  - installer generation
  - cross-platform support
