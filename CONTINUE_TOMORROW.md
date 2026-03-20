# Continue Tomorrow

## Current State

The host-side refactor, engine adapter landing, runtime hardening, and transport
primary-path work are now far enough along to support both fast and full real
CODESYS acceptance.

Latest checkpoint:

- Commit `cca2125` prepared host-side file transport removal.
- Current follow-up is host-side file-removal prep stage 2 in:
  - `CONTINUE_TOMORROW.md`
  - `FILE_TRANSPORT_RETIREMENT.md`
  - `STRATEGIC_PLAN.md`
  - `session_transport.py`
  - `tests/integration/test_script_executor.py`

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
- Added transport support with a primary and fallback path:
  - `named_pipe` primary transport
  - `file` legacy fallback transport
  - host-side transport selection through config
  - CODESYS-side named-pipe listener in `PERSISTENT_SESSION.py`
  - explicit transport error classification and metadata
  - named-pipe listener readiness check in `CodesysProcessManager.start()`
  - shared host-side transport request and timeout helpers in `transport_result.py`
  - reduced duplicate request/error logic between `file` and `named_pipe`
  - explicit `build_script_transport()` contract coverage for `file`, `named_pipe`, and unsupported transports
  - normalized transport result shape so success and error paths consistently carry `transport` and `request_id`
  - shared success-result normalization helper in `transport_result.py`
  - shared transport execution context for request/deadline/timeout handling
  - shared execution-context helpers for standard success/error result construction
  - file-specific result polling moved behind a private helper
  - named-pipe exchange/retry logic moved behind a private helper
  - CODESYS-side named-pipe request validation and response normalization helpers in `PERSISTENT_SESSION.py`
  - contract tests for the named-pipe request/response envelope in `PERSISTENT_SESSION.py`
  - marked `file` as a legacy fallback transport in config and `system/info`
  - kept `named_pipe` as the only recommended transport
- Added real `pytest` CODESYS E2E under `tests/e2e/codesys`
- Split real CODESYS acceptance into:
  - fast main track
  - slow runtime-hardening track
- Added explicit E2E transport policy helpers in `codesys_e2e_policy.py`
- Added `FILE_TRANSPORT_RETIREMENT.md` to record when `file` can move from legacy fallback to removal candidate
- Split file-specific transport coverage out of the main transport tests:
  - `tests/integration/test_file_transport_legacy_baseline.py`
  - `tests/unit/test_file_transport_legacy_unit.py`
  - `tests/integration/test_script_executor.py` now focuses on generic / named-pipe coverage
  - `tests/unit/test_named_pipe_transport.py` now focuses on named-pipe coverage
- Started host-side file-removal prep without deleting file transport:
  - `server_config.py` now exposes explicit primary / legacy transport helpers
  - `session_transport.py` now routes the file branch through `build_legacy_file_transport()`
  - `legacy_file_transport.py` now contains the isolated host-side file transport implementation
  - legacy-path tests now lock the file branch behind a dedicated host-side removal seam
- Continued host-side file-removal prep:
  - `session_transport.py` now behaves as a primary transport facade only
  - `session_transport.py` no longer re-exports `FileScriptTransport` or `build_legacy_file_transport()`
  - primary transport tests now lock the facade surface so file-specific symbols stay in `legacy_file_transport.py`
  - `HTTP_SERVER.py` runtime transport selection now defaults to `build_primary_script_transport()`
  - `HTTP_SERVER.py` only uses the file builder when legacy transport is explicitly opted in
- Tightened runtime recovery behavior:
  - `stop_session()` and `start_session()` now wait for state convergence in real E2E
  - fallback compile now saves and closes the project before restarting in UI mode
  - real compile E2E uses a longer timeout for noUI fallback recovery

## Verification Status

These commands were green at the end of the session:

```powershell
python -m pytest -q
python -m mypy
python -m py_compile HTTP_SERVER.py action_layer.py api_key_store.py codesys_e2e_policy.py codesys_process.py server_config.py file_ipc.py server_logic.py test_server.py ironpython_script_engine.py engine_adapter.py legacy_file_transport.py named_pipe_transport.py session_transport.py transport_result.py tests/e2e/codesys/test_real_codesys_e2e.py tests/integration/test_file_transport_legacy_baseline.py tests/integration/test_script_executor.py tests/unit/test_file_transport_legacy_unit.py tests/unit/test_http_server_system_info.py tests/unit/test_named_pipe_transport.py tests/unit/test_real_codesys_e2e_policy.py tests/unit/test_server_config.py
```

Expected results at handoff:

- `pytest`: 115 tests passing, 5 skipped without real CODESYS env
- `pytest -m "codesys and not codesys_slow"`: default real acceptance entrypoint
- `pytest -m codesys`: default full acceptance entrypoint for `named_pipe`
- `mypy`: success with no issues in 28 source files
- `git status --short`: currently expected to show stage-2 host-side removal-prep changes in:
  - `CONTINUE_TOMORROW.md`
  - `HTTP_SERVER.py`
  - `session_transport.py`
  - `tests/integration/test_script_executor.py`
  - `tests/unit/test_http_server_system_info.py`

Verified real acceptance results:

- Fast real acceptance passes with `CODESYS_E2E_TRANSPORT=named_pipe`
- Full real acceptance passes with `CODESYS_E2E_TRANSPORT=named_pipe`
- Legacy fallback baseline still passes with `CODESYS_E2E_TRANSPORT=file`
- Legacy `file` slow-track real E2E is now opt-in via `CODESYS_E2E_FILE_FULL=1`

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
- `file` is no longer the peer default path; it is a manual legacy fallback for compatibility and transport debugging.
- Slow-track real E2E now defaults to `named_pipe`; `file` only runs fast-track unless `CODESYS_E2E_FILE_FULL=1`.
- The current `file` removal criteria live in `FILE_TRANSPORT_RETIREMENT.md`.
- Host-side removal prep is active, but `PERSISTENT_SESSION.py` still keeps the file path intact.
- The host-side file implementation now lives in `legacy_file_transport.py`; `session_transport.py` keeps the primary transport entrypoint and the legacy branch wiring only.
- Runtime transport selection now also separates the default primary builder from the legacy file builder.

## Next Best Steps

1. Continue host-side file-removal prep with `named_pipe` as the standard path.
2. Keep `file` only as a minimal compatibility baseline while measuring against `FILE_TRANSPORT_RETIREMENT.md`.
3. Continue isolating host-side file code so future removal becomes mechanical instead of structural.
4. Do not touch `PERSISTENT_SESSION.py` file transport paths yet.
5. Keep the real CODESYS E2E as the phase-boundary runtime acceptance test, not just a happy-path smoke.
6. Do not reopen the `--noUI` compile issue unless new regressions appear.

## Recommended Sequence For Next Session

Start with transport work.

Reason:

- The host-side seams and engine adapter seam are active
- The real happy path is already verified end-to-end
- The slow runtime-hardening track is now also verified with `named_pipe`
- `named_pipe` is now the only recommended transport path
- The current checkpoint already includes `file` soft deprecation and retirement-readiness documentation
- The current checkpoint also keeps file-specific coverage isolated in dedicated legacy baseline tests
- The current follow-up is now code-level host-side removal prep, not just doc alignment
- The current follow-up keeps shrinking the primary facade surface, not deleting file transport yet
- CLI is still lower priority than transport reliability

## Quick Resume Checklist

1. Open `STRATEGIC_PLAN.md`
2. Open `COLLABORATION_TEMPLATE.md`
3. Open `FILE_TRANSPORT_RETIREMENT.md`
4. Open this file
5. Run:

```powershell
python -m pytest -q
python -m mypy
git status --short
```

6. If running real CODESYS fast acceptance:

```powershell
$env:CODESYS_E2E_ENABLE="1"
$env:CODESYS_API_CODESYS_PATH="..."
$env:CODESYS_API_CODESYS_PROFILE="..."
$env:CODESYS_API_CODESYS_PROFILE_PATH="..."
$env:CODESYS_E2E_NO_UI="true"
$env:CODESYS_E2E_TRANSPORT="named_pipe"
python -m pytest -q -m "codesys and not codesys_slow" tests/e2e/codesys
```

7. If running full real CODESYS acceptance:

```powershell
$env:CODESYS_E2E_ENABLE="1"
$env:CODESYS_API_CODESYS_PATH="..."
$env:CODESYS_API_CODESYS_PROFILE="..."
$env:CODESYS_API_CODESYS_PROFILE_PATH="..."
$env:CODESYS_E2E_NO_UI="true"
$env:CODESYS_E2E_TRANSPORT="named_pipe"
python -m pytest -q -m codesys tests/e2e/codesys
```

8. If checking the legacy fallback transport only:

```powershell
$env:CODESYS_E2E_ENABLE="1"
$env:CODESYS_API_CODESYS_PATH="..."
$env:CODESYS_API_CODESYS_PROFILE="..."
$env:CODESYS_API_CODESYS_PROFILE_PATH="..."
$env:CODESYS_E2E_NO_UI="true"
$env:CODESYS_E2E_TRANSPORT="file"
python -m pytest -q -m "codesys and not codesys_slow" tests/e2e/codesys
```

9. If you explicitly need the legacy `file` slow track:

```powershell
$env:CODESYS_E2E_ENABLE="1"
$env:CODESYS_API_CODESYS_PATH="..."
$env:CODESYS_API_CODESYS_PROFILE="..."
$env:CODESYS_API_CODESYS_PROFILE_PATH="..."
$env:CODESYS_E2E_NO_UI="true"
$env:CODESYS_E2E_TRANSPORT="file"
$env:CODESYS_E2E_FILE_FULL="1"
python -m pytest -q -m codesys tests/e2e/codesys
```
