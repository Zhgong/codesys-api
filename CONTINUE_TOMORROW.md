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

The baseline and repo-reorg phases are complete:

- core host-side implementation now lives under `src/codesys_api/`
- long-lived documents now live under `docs/`
- debug and diagnostic helpers now live under `scripts/debug/`
- runtime stub assets now live under `codesys_assets/`
- root entrypoints remain compatible through thin wrapper modules

Latest stable checkpoints:

- `3a16ec9` completed transport cleanup and established the local CLI
- `8e0d4d3` replaced file-based session logs with a runtime buffer
- `75d84b4` established the repository baseline
- `8e95c68` reorganized the repository into a structured layout

## Verification Status

These commands are green:

```powershell
python scripts\run_baseline.py
```

Expected results at handoff:

- `pytest`: `150 passed, 8 skipped`
- `mypy`: success with no issues in `44` source files
- `git status --short`: should only show `M CONTINUE_TOMORROW.md` until this handoff note is committed

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

This round did not rerun real CODESYS acceptance. The baseline still documents the current real acceptance commands and expectations, but the required proof for the reorg phase was the local baseline gate.

## Important Constraints

- Do not reopen transport design or file-transport work unless a regression appears.
- Keep REST API v1 behavior stable.
- Keep `PERSISTENT_SESSION.py` untyped and IronPython-safe.
- `CODESYS_API_CODESYS_NO_UI` remains opt-in.
- On this machine, run `pytest` with `--basetemp C:\Users\vboxuser\Desktop\pytest_manual_root`.
- `project list` uses the current CODESYS recent-projects API and may return an empty list even after a successful create/save/close flow.
- Close the project before stopping the session after project-based validation flows to avoid IDE-side locks.

## Next Best Steps

1. Treat repo reorganization as the active major phase.
2. Keep root entrypoints compatible while moving internal code and long-lived assets into their structured directories.
3. Run `python scripts\run_baseline.py` after each structural slice.
4. Do not reopen transport or lifecycle work unless packaging exposes a regression.
5. The next active stage should be packaging:
   - make `pip install .` work on the reorganized layout
   - add formal console entrypoints
   - make runtime asset lookup work without relying on repo-root assumptions

## Quick Resume Checklist

1. Open `STRATEGIC_PLAN.md`
2. Open `BASELINE.md`
3. Open this file
4. Run:

```powershell
python scripts\run_baseline.py
git status --short
```
