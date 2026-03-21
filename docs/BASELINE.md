# Baseline

## Summary

This repository now maintains a formal baseline before any large refactor, repo reorg, or packaging work.

The baseline is split into three layers:

- engineering gate baseline
- contract baseline
- real CODESYS baseline

The goal is not to snapshot every response byte. The goal is to preserve the high-value behaviors that must remain stable across upgrades and structural changes.

## Engineering Gate Baseline

Run these commands on every major change:

```powershell
python -m pytest -q --basetemp C:\Users\vboxuser\Desktop\pytest_manual_root
python -m mypy
python -m py_compile HTTP_SERVER.py codesys_cli.py scripts/dev/test_server.py _repo_bootstrap.py src/codesys_api/*.py tests/e2e/codesys/test_real_codesys_cli.py
python scripts\run_baseline.py
```

Current expected result:

- `pytest`: `164 passed, 8 skipped`
- `mypy`: success with no issues in `57` source files
- `py_compile`: success

## Contract Baseline

The contract baseline protects high-value CLI and HTTP behaviors.

CLI baseline coverage:

- help and launcher contract
- `session status`
- `project create`
- `project compile`
- `project list`
- `pou list`
- setup/preflight failures
- exit code behavior

HTTP baseline coverage:

- `/api/v1/system/info`
- `/api/v1/system/logs`
- mock-server smoke path

These are currently represented by:

- `tests/unit/test_codesys_cli.py`
- `tests/unit/test_cli_documentation.py`
- `tests/unit/test_http_server_system_info.py`
- `tests/unit/test_http_server_system_logs.py`
- `tests/e2e/mock/test_mock_server_e2e.py`
- `tests/e2e/codesys/test_real_codesys_cli.py`
- `tests/e2e/codesys/test_real_codesys_e2e.py`

## Real CODESYS Baseline

The real baseline keeps the current working CODESYS path stable.

HTTP real baseline:

- positive main flow
- restart/start/stop repeatability
- compile without active project fails cleanly
- compile detects project errors

CLI real baseline:

- positive CLI smoke:
  - `session start`
  - `project create`
  - `pou create`
  - `pou list`
  - `project save`
  - `project compile`
  - `project close`
  - `session restart`
  - `project list`
  - `session stop`
- negative CLI compile:
  - break `Application/PLC_PRG`
  - `project compile` must fail with `errors > 0`

Important current expectations:

- runtime transport is `named_pipe` only
- compile uses `build + generate_code`
- `project list` may legitimately return an empty list
- `/api/v1/system/logs` remains available and now reads from an in-memory runtime log buffer

## Baseline Entry Points

Use the baseline runner for the local engineering and contract baseline:

```powershell
python scripts\run_baseline.py
```

The baseline runner now also protects the current reorg direction:

- root entrypoints remain callable
- implementation modules live under `src/codesys_api/`
- runtime stub assets live under `src/codesys_api/assets/`
- long-lived docs live under `docs/`

Real CODESYS baseline remains opt-in and requires the existing environment variables:

- `CODESYS_E2E_ENABLE=1`
- `CODESYS_API_CODESYS_PATH`
- `CODESYS_API_CODESYS_PROFILE`
- `CODESYS_API_CODESYS_PROFILE_PATH`

Suggested real baseline commands:

```powershell
python -m pytest -q tests\e2e\codesys\test_real_codesys_e2e.py --basetemp C:\Users\vboxuser\Desktop\pytest_manual_root -m "codesys"
python -m pytest -q tests\e2e\codesys\test_real_codesys_cli.py --basetemp C:\Users\vboxuser\Desktop\pytest_manual_root -m "codesys"
```

## Usage

Use this baseline before:

- repo reorganization
- packaging work
- major dependency upgrades
- CODESYS version changes
- runtime or compile behavior changes

## Packaging Phase 2 Gate

Packaging phase 2 adds a release-artifact gate on top of the engineering baseline:

```powershell
python scripts\build_release.py
```

Expected result:

- `dist/*.whl` exists
- `dist/*.tar.gz` exists
- clean wheel install smoke succeeds
- installed `codesys-cli --help` succeeds
- installed `codesys-api-server --help` succeeds
- installed package assets resolve correctly

## Internal Release Gate

Internal release flow builds on packaging phase 2 and requires:

- `docs/RELEASE.md`
- `docs/RELEASE_NOTES.md`
- baseline success
- version-matching wheel and sdist artifacts
- clean wheel-install smoke

## Public Release Prep Gate

Public release prep adds a public-facing documentation and metadata gate:

```powershell
python scripts\check_public_release.py
```

Expected result:

- public metadata exists in `pyproject.toml`
- `README.md` states Windows experimental support and local CODESYS dependency
- `docs/PUBLIC_RELEASE.md` exists
- wheel build succeeds
- clean wheel-install smoke succeeds
