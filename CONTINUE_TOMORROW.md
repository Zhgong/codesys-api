# Continue Tomorrow

## Current State

The host-side refactor, engine adapter landing, runtime hardening, and transport
dual-stack work are now far enough along to support both fast and full real
CODESYS acceptance.

Completed so far:

- Added `pytest` and `mypy --strict` in `pyproject.toml`
- Extracted typed host-side modules:
  - `server_logic.py`
  - `file_ipc.py`
  - `codesys_process.py`
  - `api_key_store.py`
  - `server_config.py`
  - `action_layer.py`
  - `engine_adapter.py`
  - `ironpython_script_engine.py`
  - `named_pipe_transport.py`
  - `session_transport.py`
- Moved these endpoints behind the action layer:
  - `session/start`
  - `session/stop`
  - `session/restart`
  - `session/status`
  - `project/create`
  - `project/open`
  - `project/save`
  - `project/close`
  - `project/list`
  - `project/compile`
  - `pou/create`
  - `pou/code`
  - `pou/list`
  - `script/execute`
- Fixed non-interactive startup handling:
  - explicit profile support
  - optional `--noUI` via env var
- Completed the engine adapter landing phase:
  - wired `HTTP_SERVER.py` to instantiate `IronPythonScriptEngineAdapter`
  - removed the legacy in-file script generator from `HTTP_SERVER.py`
  - added adapter metadata and capability reporting
  - added capability gating in `action_layer.py` for engine-supported actions
  - changed `action_layer.py` to depend on the formal engine adapter contract
  - changed the adapter to expose `build_execution()` and `normalize_result()`
- Added automatic `project.compile` fallback for `--noUI` sessions:
  - save active project
  - stop CODESYS
  - restart without `--noUI`
  - reinitialize session
  - reopen project
  - compile automatically without manual intervention
- Added runtime-mode reset after explicit `session/stop` and `session/restart`
- Added transport dual-stack support:
  - `file` transport
  - `named_pipe` transport
  - host-side transport selection through config
  - CODESYS-side named-pipe listener in `PERSISTENT_SESSION.py`
  - explicit transport error classification and metadata
  - named-pipe listener readiness check in `CodesysProcessManager.start()`
  - shared host-side transport request and timeout helpers in `transport_result.py`
  - reduced duplicate request/error logic between `file` and `named_pipe`
  - explicit `build_script_transport()` contract coverage for `file`, `named_pipe`, and unsupported transports
  - normalized transport result shape so success and error paths consistently carry `transport` and `request_id`
  - shared success-result normalization helper in `transport_result.py`
- Added real `pytest` CODESYS E2E under `tests/e2e/codesys`
- Split real CODESYS acceptance into:
  - fast main track
  - slow runtime-hardening track
- Tightened runtime recovery behavior:
  - `stop_session()` and `start_session()` now wait for state convergence in real E2E
  - fallback compile now saves and closes the project before restarting in UI mode
  - real compile E2E uses a longer timeout for noUI fallback recovery

## Verification Status

These commands were green at the end of the session:

```powershell
python -m pytest -q
python -m mypy
python -m py_compile HTTP_SERVER.py action_layer.py api_key_store.py codesys_process.py server_config.py file_ipc.py server_logic.py test_server.py ironpython_script_engine.py engine_adapter.py named_pipe_transport.py session_transport.py transport_result.py tests/e2e/codesys/test_real_codesys_e2e.py
```

Expected results at handoff:

- `pytest`: 92 tests passing, 5 skipped without real CODESYS env
- `pytest -m "codesys and not codesys_slow"`: default real acceptance entrypoint
- `pytest -m codesys`: full real acceptance entrypoint
- `mypy`: success with no issues

Verified real acceptance results:

- Fast real acceptance passes with `CODESYS_E2E_TRANSPORT=file`
- Fast real acceptance passes with `CODESYS_E2E_TRANSPORT=named_pipe`
- Full real acceptance passes with `CODESYS_E2E_TRANSPORT=file`
- Full real acceptance passes with `CODESYS_E2E_TRANSPORT=named_pipe`

## Important Constraints

- Do not try to strictly type `PERSISTENT_SESSION.py` or injected CODESYS script bodies yet.
- Keep REST API v1 behavior stable while continuing internal extraction.
- `CODESYS_API_CODESYS_NO_UI` is opt-in; it is not the default.
- Do not hardcode local machine CODESYS paths into repo defaults.
- Real CODESYS compile succeeds on this machine with `CODESYS_API_CODESYS_NO_UI=false`.
- Real CODESYS compile also succeeds with `CODESYS_API_CODESYS_NO_UI=true` via automatic host-side fallback to UI mode for the compile path.
- After a noUI compile fallback, the live session stays in UI mode until explicit `session/stop` or `session/restart`.
- Named-pipe startup is not considered ready until the pipe listener is actually reachable.
- The slowest noUI fallback compile path is long-running; real E2E currently uses a 300-second client timeout for that path.
- Keep real E2E speedup separate from future transport tuning work.

## Next Best Steps

1. Continue transport evolution, now that both fast and full real acceptance pass with `named_pipe`.
2. Focus on transport diagnostics, edge-case recovery, and simplifying the remaining dual-stack behavior.
3. Keep the real CODESYS E2E as the phase-boundary runtime acceptance test, not just a happy-path smoke.
4. Do not reopen the `--noUI` compile issue unless new regressions appear.

## Recommended Sequence For Next Session

Start with transport work.

Reason:

- The host-side seams and engine adapter seam are active
- The real happy path is already verified end-to-end
- The slow runtime-hardening track is now also verified with `named_pipe`
- CLI is still lower priority than transport reliability

## Quick Resume Checklist

1. Open `STRATEGIC_PLAN.md`
2. Open `COLLABORATION_TEMPLATE.md`
3. Open this file
4. Run:

```powershell
python -m pytest -q
python -m mypy
git status --short
```

5. If running real CODESYS fast acceptance:

```powershell
$env:CODESYS_E2E_ENABLE="1"
$env:CODESYS_API_CODESYS_PATH="..."
$env:CODESYS_API_CODESYS_PROFILE="..."
$env:CODESYS_API_CODESYS_PROFILE_PATH="..."
$env:CODESYS_E2E_NO_UI="true"
$env:CODESYS_E2E_TRANSPORT="named_pipe"
python -m pytest -q -m "codesys and not codesys_slow" tests/e2e/codesys
```

6. If running full real CODESYS acceptance:

```powershell
$env:CODESYS_E2E_ENABLE="1"
$env:CODESYS_API_CODESYS_PATH="..."
$env:CODESYS_API_CODESYS_PROFILE="..."
$env:CODESYS_API_CODESYS_PROFILE_PATH="..."
$env:CODESYS_E2E_NO_UI="true"
$env:CODESYS_E2E_TRANSPORT="named_pipe"
python -m pytest -q -m codesys tests/e2e/codesys
```
