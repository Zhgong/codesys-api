# Continue Tomorrow

## Executive Summary

This file is the primary breakpoint document for the current real-CODESYS investigation.

Method and lessons-learned reference:

- [REAL_CODESYS_LESSONS.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/REAL_CODESYS_LESSONS.md)
- [CODESYS_BOUNDARY_CONTRACT.md](/C:/Users/vboxuser/Desktop/Repos/codesys-api/docs/CODESYS_BOUNDARY_CONTRACT.md)

The active internal engineering milestone is:

- `Real CODESYS Contract Ladder v1`

Current product line:

- `0.3.0` workflow hardening from external user feedback

Do not reframe this as `0.2.x`.

## Product Goal Clarification

The project goal is defined in terms of utility, not implementation style.

What must be true for the product to be considered correct:

- a CODESYS session can stay alive across multiple user-visible steps
- later operations can keep working on the same in-memory project state
- step-by-step flows such as `session/start -> project/create -> pou/code -> project/compile` return trustworthy results

What does not define success by itself:

- whether the implementation uses CLI, HTTP, files, named pipes, threads, or extra processes
- whether a request technically returns JSON if the underlying CODESYS result is incomplete or corrupted

Current debugging and design decisions should therefore be evaluated against this question:

- does the implementation preserve persistent session utility and reliable stepwise operation?

If not, the implementation detail is wrong even if the API surface appears to work.

## Current Product And Branch State

- branch:
  - `feature/external-feedback-hardening`
- current product version source:
  - `pyproject.toml` -> `0.2.1`
- frozen implementation line:
  - `0.3.0` workflow hardening from external user feedback

## Verification Status (2026-03-28)

Current local verification baseline:

- full unit sweep:
  - `266 passed`
- `python -m mypy`:
  - `Success: no issues found in 83 source files`

## Completed Work This Session

### Layers 1–4: All GREEN

All prior layers remain green. The thread-root-cause narrative is fully resolved.

### CLI Compile-Error Probe (Layer 4): GREEN

`python scripts\manual\real_cli_compile_error_probe.py` exits 0.

- `cli session/start`: success
- `cli project/create`: success
- `cli pou/code`: success
- `cli project/compile`: exit_code=1, success=false, message_counts.errors=2
  - messages include `Identifier 'MissingVar' not defined`
  - messages include `'MissingVar' is no valid assignment target`
- no popup, no orphan windows

### Lifecycle Stress Probe (2026-03-28): CodesysProcessManager CLEARED

Created `scripts/manual/lifecycle_stress_probe.py` — bypasses HTTP server and pytest entirely,
drives `CodesysProcessManager` + `NamedPipeScriptTransport` + `ScriptExecutor` directly.

Result: **PASSED all 12 consecutive start → health-check → stop cycles** (UI mode, `--ui`).

```
python scripts\manual\lifecycle_stress_probe.py --ui --cycles 12
# PASSED all 12 lifecycle cycles.
# Interpretation: fault is NOT in process management layer - look at the HTTP server.
```

This definitively clears `CodesysProcessManager` as the source of the per-lifecycle leak.
The fault is in the **HTTP server layer** — something in the `HTTPServer` / `BaseHTTPRequestHandler`
Python process that accumulates state across CODESYS lifecycle transitions.

Side-finding during probe development: `_build_launch_env()` in `codesys_process.py` does NOT
inject `CODESYS_API_PIPE_NAME` into the subprocess env — it relies on the caller having already
set `os.environ["CODESYS_API_PIPE_NAME"]` before the process manager is constructed. The HTTP
server works because the pipe name is in its env at startup. Any standalone probe must set
`os.environ["CODESYS_API_PIPE_NAME"]` explicitly before creating `ProcessManagerConfig`.

### Changes applied this session

1. `scripts/manual/real_cli_compile_error_probe.py`
   - Added `is_expected_compile_error_stderr()` — accepts compile-error stderr instead of requiring `== ""`

2. `src/codesys_api/codesys_process.py` — `_stop_attached_session()`
   - Snapshots pre-shutdown CODESYS pids
   - Taskkills orphan processes that survive after pipe is gone

3. `src/codesys_api/ironpython_script_engine.py`
   - Removed `application.generate_code()` call entirely — unproven primitive, causes
     post-compile hang in UI mode by queuing background work in CODESYS's UI layer
   - Changed compile `build_type` label from `"build+generate_code"` to `"build"`
   - Changed success message from "compiled and generated code" to "compiled successfully"

4. `tests/e2e/codesys/test_real_codesys_e2e.py`
   - Split `test_real_codesys_compile_detects_project_errors` into two focused tests:
     - `test_real_codesys_compile_detects_errors` — compile with errors → 500
     - `test_real_codesys_compile_succeeds_with_valid_project` — clean project → 200

5. `scripts/manual/run_real_codesys_e2e.py`
   - Updated `http-compile-error` target `-k` expression for the two new test names
   - Added: `http-compile-detect`, `http-compile-succeed`, `http-compile-3`,
     `http-last5`, `http-last6`, `http-last7`, `http-last8`

6. `scripts/manual/lifecycle_stress_probe.py` (NEW)
   - Standalone probe: `CodesysProcessManager` + `NamedPipeScriptTransport` + `ScriptExecutor`
   - No HTTP server, no pytest. Loops N cycles of start → health-check → stop.
   - Usage: `python scripts\manual\lifecycle_stress_probe.py --ui --cycles 12`

## Current Breakpoint: Per-Lifecycle Resource Leak in HTTP Server

### Symptom

`python scripts\manual\run_real_codesys_e2e.py --target http-all` fails:

- 8 tests collected; tests 1–6 pass; test 7 or 8 times out at HTTP socket read (TimeoutError)
- HTTP server stops responding to requests — server accepts the TCP connection but never
  sends a response
- Exact failure: POST `/api/v1/session/stop` (cycle 7) is accepted by the server socket
  but no response is ever sent. Server is blocked inside `do_POST`.

### Root Cause (confirmed by stress test experiments 2026-03-28)

**Per-CODESYS-lifecycle resource leak** in the HTTP server's Python process.

The fault accumulates once per stop→start cycle, NOT once per pipe operation,
AND is triggered by something specific to the HTTP server context — NOT by
`CodesysProcessManager` in isolation.

**Evidence:**

| Experiment | Result | Conclusion |
|---|---|---|
| `http-pipe-stress-roundtrips`: 20 pou/code ops, 1 lifecycle | PASS | per-pipe-op leak ruled out |
| `http-pipe-stress-lifecycles`: 8 stop→start cycles, 3 ops/cycle | FAIL ~cycle 7 | per-lifecycle leak confirmed |
| `lifecycle_stress_probe.py --ui --cycles 12`: direct process manager, no HTTP | **PASS** | `CodesysProcessManager` cleared |

The `named_pipe_transport.py` client side already has `finally: close_pipe_handle(handle)` on
every `CreateFileW` call — raw client-side pipe handles ARE properly closed.

`PERSISTENT_SESSION.py` reuses one `NamedPipeServerStream` for the entire CODESYS lifetime
(no server-side handle accumulation).

### What the probe tells us about the candidates

Because `lifecycle_stress_probe.py` passed 12 cycles, the leak is NOT caused by:
- `_start_output_threads()` accumulating blocked threads (they join in 0.000s in both contexts)
- `process.wait()` not being called (probe doesn't call it either and still passes)
- `CodesysProcessManager.stop()` itself hanging

What's different in the HTTP context vs the probe:
- Between each stop and the next start, the HTTP test issues **multiple GET `/session/status`
  requests** via `wait_for_session_state` (polling loop, up to 45s).
- Each `session/status` call invokes `process_manager.is_running()`, which calls
  `_is_local_session_running()` → `_is_managed_codesys_running()` → `_refresh_managed_codesys_pids()`.
- `_refresh_managed_codesys_pids()` calls `list_codesys_process_ids()`, which spawns
  **PowerShell** via `subprocess.run` with **no timeout**.
- The probe never calls `is_running()` between stop and start.

### Primary suspect (narrowed)

**`list_codesys_process_ids()` / PowerShell** — called only in the HTTP path (via `is_running()`
inside `session/status`), never between cycles in the probe. After 7 CODESYS process starts/stops,
WMI state or process table entries cause `Get-Process -Name CODESYS` to hang indefinitely,
blocking the single-threaded HTTP server permanently.

Fix: add `timeout=10` to the `subprocess.run` call in `list_codesys_process_ids()`.

### File to fix

`src/codesys_api/codesys_process.py` — `list_codesys_process_ids()` at line ~47:

```python
# Current (no timeout — hangs if WMI is slow):
completed = subprocess.run([...], capture_output=True, text=True, check=False)

# Fix:
completed = subprocess.run([...], capture_output=True, text=True, check=False, timeout=10)
```

Also add `process.wait(timeout=5)` in `stop()` after the kill sequence, as a belt-and-suspenders
handle cleanup measure.

### Minimum Reproduction (fast)

```powershell
python scripts\manual\run_real_codesys_e2e.py --target http-pipe-stress-lifecycles
```

This runs 8 stop→start cycles with 3 pipe ops/cycle in ~6 minutes.
The `--target http-pipe-stress-roundtrips` target (20 ops, 1 lifecycle) passes cleanly.

## Active Internal Milestone: Real CODESYS Contract Ladder v1

### Layer 1: Startup Contract - GREEN

### Layer 2: Session And Project Contract - GREEN

- `project/create` works on the correct primitive

### Layer 3: Object Discovery And Write Verification - GREEN

- `real_pou_code_roundtrip_probe.py` passes

### Layer 4: CLI Compile-Error Contract - GREEN

- `real_cli_compile_error_probe.py` exits 0
- no popup, no orphan windows

### Layer 5: HTTP/CLI Comparison And Aggregate E2E - BLOCKED on lifecycle leak

- Individual HTTP tests and subset runs pass
- Full `http-all` (8 tests) fails at test 7 or 8 due to per-lifecycle leak
- `cli-all` not yet run
- Minimum repro: `http-pipe-stress-lifecycles` (8 cycles, ~6 min)

## Strict Next Steps

Do these in order.

1. Fix `list_codesys_process_ids()` in `src/codesys_api/codesys_process.py` — add `timeout=10`
   to the `subprocess.run` call. Also add `process.wait(timeout=5)` in `stop()` after the
   kill/taskkill sequence, before `_join_output_threads()`.

2. Run unit tests and mypy.

3. Run `http-pipe-stress-lifecycles` to confirm fix:

```powershell
python -m pytest tests/unit/ -p no:cacheprovider -q
python -m mypy
python scripts\manual\run_real_codesys_e2e.py --target http-pipe-stress-lifecycles
```

4. If lifecycle stress passes, run `http-all`:

```powershell
python scripts\manual\run_real_codesys_e2e.py --target http-all
```

5. If `http-all` passes, run `cli-all`:

```powershell
python scripts\manual\run_real_codesys_e2e.py --target cli-all
```

## Completed Layer Entry Points (reference)

These probes passed and form the regression baseline.

```powershell
python scripts\manual\profile_launch_probe.py --mode shell_string
python scripts\manual\real_project_open_raw_probe.py --mode template
python scripts\manual\real_project_create_direct_raw_probe.py
python scripts\manual\real_pou_code_roundtrip_probe.py
python scripts\manual\real_project_compile_probe.py --script-timeout 300
python scripts\manual\direct_codesys_runscript_probe.py --mode create_and_build_error
python scripts\manual\direct_codesys_persistent_host_probe.py --exec-mode background --mode single_request_full_build
python scripts\manual\direct_codesys_persistent_host_probe.py --exec-mode primary --mode single_request_full_build
python scripts\manual\real_cli_compile_error_probe.py
python scripts\manual\run_real_codesys_e2e.py --target http-compile-error
python scripts\manual\run_real_codesys_e2e.py --target http-pipe-stress-roundtrips   <- GREEN
python scripts\manual\lifecycle_stress_probe.py --ui --cycles 12                     <- GREEN (process manager cleared)
python scripts\manual\run_real_codesys_e2e.py --target http-pipe-stress-lifecycles   <- CURRENTLY FAILING
python scripts\manual\run_real_codesys_e2e.py --target http-all                      <- CURRENTLY FAILING
python scripts\manual\run_real_codesys_e2e.py --target cli-all                       <- NOT YET RUN
```

## What Not To Do

- do not reopen transport redesign as the primary problem
- do not treat sandbox-launch failures as product regressions
- do not treat empty stderr as the definition of correct compile-error behavior
- do not reopen the old noUI fallback narrative as the current blocker
- do not add to `proven_primitives.py` without a passing real probe
- do not reopen `Standard.project` template approach
- do not treat `named_pipe_transport.py` as the source of the leak — client handles ARE
  properly closed (`finally: close_pipe_handle(handle)` confirmed present)
- do not remove `generate_code()` as the sole fix for http-all — it was already removed and
  http-all still fails
- do not blame `CodesysProcessManager` in isolation — `lifecycle_stress_probe.py --ui --cycles 12`
  PASSED, proving the process manager can handle 12+ cycles cleanly without the HTTP layer

## Working Set

- `src/codesys_api/codesys_process.py` — **fix here: `list_codesys_process_ids()` needs `timeout=10`**
- `tests/e2e/codesys/test_pipe_stress.py` — minimum repro test
- `scripts/manual/lifecycle_stress_probe.py` — process-manager isolation probe (passes 12 cycles)
- `src/codesys_api/assets/PERSISTENT_SESSION.py` (current proven primary-thread runtime)
- `scripts/manual/run_real_codesys_e2e.py` (diagnostic targets already added)

## Quick Resume Checklist

1. Open:

- `docs\CONTINUE_TOMORROW.md`
- `docs\CODESYS_BOUNDARY_CONTRACT.md`

2. Refresh local baseline:

```powershell
git status --short --branch
python -m pytest tests/unit/ -p no:cacheprovider -q
python -m mypy
```

Expected: 266 passed, mypy clean.

3. Read `src/codesys_api/codesys_process.py` and fix the lifecycle leak.

4. Run:

```powershell
python -m pytest tests/unit/ -p no:cacheprovider -q
python -m mypy
python scripts\manual\run_real_codesys_e2e.py --target http-pipe-stress-lifecycles
python scripts\manual\run_real_codesys_e2e.py --target http-all
```
