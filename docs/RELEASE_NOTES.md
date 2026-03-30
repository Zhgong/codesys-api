# Release Notes

## Unreleased

_(nothing queued)_

---

## 0.3.0 — 2026-03-30

### Summary

Workflow reliability hardening from real-CODESYS validation and external user feedback.
All five layers of the Real CODESYS Contract Ladder v1 are GREEN.

### Changes

**Bug fixes**

- Fix HTTP server lifecycle stall: override `log_message()` in `CodesysApiHandler` to
  redirect `BaseHTTPRequestHandler` access logs from `sys.stderr` to a file logger.
  Root cause: E2E tests start the server with `stderr=PIPE`; the anonymous pipe buffer
  (~4 KB) fills after ~7 lifecycles, blocking `send_response()` permanently.
- Fix CODESYS orphan processes on stop: move `taskkill /PID /T /F` before
  `process.terminate()` so the cmd.exe child tree is killed atomically, preventing
  residual CODESYS windows from surviving session stop.
- Add `timeout=10` to the PowerShell `subprocess.run` call in `list_codesys_process_ids()`
  to prevent indefinite blocking when WMI enumeration is slow.
- Remove `application.generate_code()` call after compile — unproven primitive that causes
  a post-compile hang in UI mode by queuing background work in CODESYS's UI layer.
- Remove noUI compile fallback — `build()` works directly in noUI mode; the fallback added
  complexity and caused project-lock errors when switching back from UI mode.

**Architecture**

- Add `proven_primitives.py`: single source of truth for CODESYS scriptengine calls
  validated by real-CODESYS probes. `ironpython_script_engine.py` composes from this module.
- Rebuild `project/create` and session primitives on `scriptengine.projects.create(path, True)`
  instead of `projects.open(Standard.project)` (proven broken in this environment).
- Named pipe transport (`named_pipe_transport.py`) and persistent session
  (`PERSISTENT_SESSION.py`) for reliable multi-step workflows across session boundaries.
- CLI internal logs redirected to `%APPDATA%\codesys-api\logs\codesys_api_cli.log`;
  no longer propagate to stderr, preserving the `--json` contract.

**Documentation**

- `docs/CODESYS_BOUNDARY_CONTRACT.md` — contract between host code and CODESYS scriptengine
- `docs/REAL_CODESYS_LESSONS.md` — lessons from the real-CODESYS investigation
- `docs/BUG_HTTP_LIFECYCLE_STALL.md` — resolved incident report with root-cause analysis
- `docs/DEBUGGING_METHODOLOGY.md` — general debugging methodology extracted from this case

### Verification

**Unit and static gate (pre-release, 2026-03-30)**

- Baseline: `265 passed, mypy clean (82 source files)`
- Branch: `development`, HEAD `0bfe886`

**Real CODESYS E2E (Windows, real CODESYS 3.5.21.0)**

- `http-pipe-stress-lifecycles`: `1 passed` in 381.86s
- `http-all` (8 tests): `8 passed` in 352.37s
- `cli-all` (2 tests): `2 passed` in 95.44s

**Packaging gate**

- [x] `python scripts\build_release.py` succeeds
- [x] wheel and sdist produced
- [x] clean wheel-install smoke passes
- [x] `codesys-tools` entrypoint verified
- [x] `codesys-tools-server` entrypoint verified
- [x] `PERSISTENT_SESSION.py` packaged
- [x] `ScriptLib/` packaged

**TestPyPI**

- [x] `Publish Package (target=testpypi)` passes
- [x] `Verify Published Package (target=testpypi, version=0.3.0)` passes

**PyPI**

- [x] Published: https://pypi.org/project/codesys-tools/
- [x] Verified
- [x] Git tag: `v0.3.0`

---

## 0.2.1

- Commit: `a3719c8`
- Baseline gate: `170 passed, 8 skipped`
- Static gate: `mypy` passes with no issues in `60` source files
