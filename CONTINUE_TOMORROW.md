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

The current active line is now baseline establishment:

- `BASELINE.md` defines the current engineering, contract, and real-CODESYS baseline
- `scripts/run_baseline.py` runs the local engineering baseline
- baseline documentation tests lock the commands and references

Latest stable checkpoints:

- `3a16ec9` completed transport cleanup and established the local CLI
- `8e0d4d3` replaced file-based session logs with a runtime buffer

## Verification Status

These commands are green:

```powershell
python -m pytest -q --basetemp C:\Users\vboxuser\Desktop\pytest_manual_root
python -m mypy
python -m py_compile HTTP_SERVER.py action_layer.py api_key_store.py app_runtime.py codesys_cli.py codesys_e2e_policy.py codesys_process.py engine_adapter.py ironpython_script_engine.py runtime_transport.py script_executor.py server_config.py server_logic.py test_server.py named_pipe_transport.py transport_result.py tests/e2e/codesys/test_real_codesys_cli.py
```

Expected results at handoff:

- `pytest`: `150 passed, 8 skipped`
- `mypy`: success with no issues in `36` source files
- `git status --short`: expected to show only the baseline follow-up files if this phase is still uncommitted

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

This round did not rerun real CODESYS acceptance. The baseline documents the current real acceptance commands and expectations, but local gates were the required proof for this phase.

## Important Constraints

- Do not reopen transport design or file-transport work unless a regression appears.
- Keep REST API v1 behavior stable.
- Keep `PERSISTENT_SESSION.py` untyped and IronPython-safe.
- `CODESYS_API_CODESYS_NO_UI` remains opt-in.
- On this machine, run `pytest` with `--basetemp C:\Users\vboxuser\Desktop\pytest_manual_root`.
- `project list` uses the current CODESYS recent-projects API and may return an empty list even after a successful create/save/close flow.
- Close the project before stopping the session after project-based validation flows to avoid IDE-side locks.

## Next Best Steps

1. Treat the CLI as the active major phase.
2. Finish the final small CLI polish pass:
   - keep command coverage fixed
   - improve grouped help examples
   - keep human-readable output and setup errors consistent with `CLI_USAGE.md`
3. Do not add more commands by default unless a clearly missing workflow appears.
4. Treat the baseline as the required safety net before repo reorg or packaging work.
5. The next stage after this one should be repo reorganization, not new transport/lifecycle work.

## Quick Resume Checklist

1. Open `STRATEGIC_PLAN.md`
2. Open `BASELINE.md`
3. Open this file
4. Run:

```powershell
python scripts\run_baseline.py
git status --short
```
