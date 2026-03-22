# Continue Tomorrow

## Current State

The old transport and lifecycle main line is complete:

- `named_pipe` is the only supported runtime transport
- host-side and CODESYS-side file transport paths are gone
- file-based control, status, and logging are gone
- `/api/v1/system/logs` now reads from an in-memory runtime log buffer

CLI is complete enough for normal local use:

- CLI v1 and v2 command coverage are implemented
- local entrypoints and usage docs are in place
- real CLI positive and negative smoke paths exist

The baseline, repo reorg, packaging phase 1, root cleanup, packaging phase 2, internal release flow, and public release prep are complete:

- core host-side implementation now lives under `src/codesys_api/`
- long-lived documents now live under `docs/`
- debug and diagnostic helpers now live under `scripts/debug/`
- runtime stub assets now live under `src/codesys_api/assets/`
- root entrypoints remain compatible through thin wrapper modules
- ordinary root module shims are gone
- most root docs and helper scripts now live under `docs/` and `scripts/`
- wheel and sdist build flow is now documented and repeatable
- clean wheel-install smoke has been validated in a fresh venv
- internal release checklist and release notes are now in place
- public-facing metadata, README, install guide, and release-prep gate are now in place
- GitHub Actions CI, release-build, and manual publish workflows are now in place
- public Python support is now targeting 3.13+

Latest stable checkpoints:

- `3a16ec9` completed transport cleanup and established the local CLI
- `8e0d4d3` replaced file-based session logs with a runtime buffer
- `75d84b4` established the repository baseline
- `8e95c68` reorganized the repository into a structured layout
- `fdf6f47` packaged the reorganized project for `pip install .`
- `c4a59f2` reduced root layout to formal entrypoints
- `01f36fa` formalized wheel build and release flow
- `1fa83b0` defined the internal wheel release flow
- `771aa04` prepared the package for public release
- `f117636` renamed the public package to `codesys-tools`
- `045d963` added GitHub Actions CI and release workflows
- published-package verification automation local work is implemented but not yet committed

## Verification Status

These commands are green:

```powershell
python scripts\run_baseline.py
```

Expected results at handoff:

- `pytest`: `170 passed, 8 skipped`
- `mypy`: success with no issues in `60` source files
- `git status --short`: should show the GitHub CI/CD working set until this round is committed

Real validation already confirmed:

- CLI positive flow works in a clean environment:
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
- CLI negative compile detection works when breaking `Application\PLC_PRG`

Internal release proof now includes:

- local baseline stays green
- `pip install .` works
- `python scripts\build_release.py` works
- `dist/*.whl` and `dist/*.tar.gz` are produced
- `codesys-tools --help` works
- `codesys-tools-server --help` works
- installed `codesys-tools --help` works from a clean venv
- installed `codesys-tools-server --help` works from a clean venv
- installed package assets resolve correctly
- internal release docs exist:
  - `docs/RELEASE.md`
  - `docs/RELEASE_NOTES.md`

Public release prep now adds:

- `python scripts\check_public_release.py` succeeds
- README states Windows experimental support
- install docs match the current package and entrypoints
- public release checklist exists
- package name is now `codesys-tools`
- installed entrypoints are now:
  - `codesys-tools`
  - `codesys-tools-server`
- GitHub Actions workflows now exist for:
  - CI on `master`
  - manual release builds
  - manual TestPyPI / PyPI publish
- a manual published-package verification workflow now exists for:
  - TestPyPI install verification
  - PyPI install verification

## Important Constraints

- Do not reopen transport design or file-transport work unless a regression appears.
- Keep REST API v1 behavior stable.
- Keep `PERSISTENT_SESSION.py` untyped and IronPython-safe.
- `CODESYS_API_CODESYS_NO_UI` remains opt-in.
- On this machine, run `pytest` with `--basetemp C:\Users\vboxuser\Desktop\pytest_manual_root`.
- `project list` uses the current CODESYS recent-projects API and may return an empty list even after a successful create/save/close flow.
- Close the project before stopping the session after project-based validation flows to avoid IDE-side locks.

## Next Best Steps

1. Keep `HTTP_SERVER.py`, `codesys_cli.py`, `run_cli.bat`, and `PERSISTENT_SESSION.py` compatible.
2. Keep ordinary imports on `codesys_api.*`; do not reintroduce root module shims.
3. Run `python scripts\run_baseline.py` before any follow-up release or product work.
4. The active stage is now published-package verification:
   - wire GitHub Environments for Trusted Publishing
   - run the first TestPyPI publish
   - run `Verify Published Package` against TestPyPI
   - then decide on first real PyPI publication
5. Keep public Python support at 3.13+:
   - CI should validate 3.13 and 3.14
   - release/publish flows stay pinned to 3.14

## Quick Resume Checklist

1. Open `docs\STRATEGIC_PLAN.md`
2. Open `docs\BASELINE.md`
3. Open this file
4. Run:

```powershell
python scripts\run_baseline.py
git status --short
```
