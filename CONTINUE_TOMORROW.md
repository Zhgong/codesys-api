# Continue Tomorrow

## Current State

The transport and lifecycle cleanup lines are complete enough for normal development:

- `named_pipe` is the only supported runtime transport
- host-side and CODESYS-side file transport paths are gone
- file-based control and status are gone
- file-based logging is gone
- `/api/v1/system/logs` now reads from an in-memory runtime log buffer

CLI productization is complete enough for normal use:

- CLI v1 and v2 command coverage are implemented
- real CLI positive and negative smoke paths exist
- the next work is no longer command expansion by default
- productization is complete:
  - formal local entrypoint
  - usage documentation
  - contract tests for docs and launcher
Latest stable checkpoints:

- `5ef1e1c` completed CLI v1 smoke coverage
- `64a9595` expanded the CLI main workflow coverage
- `eed289f` productized the local CLI entrypoint
- `274d0a8` improved CLI usability and setup errors
- `f2521ea` finalized the CLI polish pass

## Current Follow-Up

Current uncommitted work completes lifecycle cleanup phase 2:

- `HTTP_SERVER.py`
- `PERSISTENT_SESSION.py`
- `app_runtime.py`
- `codesys_process.py`
- `CONTINUE_TOMORROW.md`
- `STRATEGIC_PLAN.md`
- `server_config.py`
- `tests/unit/test_codesys_process.py`
- `tests/unit/test_http_server_system_logs.py`
- `tests/unit/test_persistent_session_contract.py`
- `tests/unit/test_server_config.py`

## Verification Status

These commands are green:

```powershell
python -m pytest -q --basetemp C:\Users\vboxuser\Desktop\pytest_manual_root
python -m mypy
python -m py_compile HTTP_SERVER.py action_layer.py api_key_store.py app_runtime.py codesys_cli.py codesys_e2e_policy.py codesys_process.py engine_adapter.py ironpython_script_engine.py runtime_transport.py script_executor.py server_config.py server_logic.py test_server.py named_pipe_transport.py transport_result.py tests/e2e/codesys/test_real_codesys_cli.py
```

Expected results at handoff:

- `pytest`: `147 passed, 8 skipped`
- `mypy`: success with no issues in `35` source files
- `git status --short`: expected to show only the lifecycle cleanup phase 2 follow-up files listed above

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

This round did not run real CODESYS acceptance because local gates were sufficient to land the in-memory logging refactor. If needed, validate `/api/v1/system/logs` on a real session before the next checkpoint.

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
4. After this phase lands, lifecycle cleanup is effectively done.
5. The next stage should be chosen outside the old transport/lifecycle line.

## Quick Resume Checklist

1. Open `STRATEGIC_PLAN.md`
2. Open this file
3. Open `STRATEGIC_PLAN.md`
4. Run:

```powershell
python -m pytest -q --basetemp C:\Users\vboxuser\Desktop\pytest_manual_root
python -m mypy
git status --short
```
