# File Transport Retirement Readiness

## Current Position

- `named_pipe` is the only recommended transport.
- `file` remains available as a manual legacy fallback.
- `file` fast real acceptance is retained as a compatibility baseline.
- `file` slow real acceptance is opt-in through `CODESYS_E2E_FILE_FULL=1`.

## Retirement Readiness Criteria

The `file` transport is ready to move from "legacy fallback" to "removal candidate"
only when all of the following are true:

1. `named_pipe` passes the default fast real CODESYS acceptance repeatedly.
2. `named_pipe` passes the default full real CODESYS acceptance repeatedly.
3. No known runtime issue requires switching to `file` to complete the main project,
   POU, script, compile, or recovery workflows.
4. Transport diagnostics and recovery analysis can be performed using `named_pipe`
   logs, metadata, and tests without depending on `file` for differential debugging.
5. Host-side and CODESYS-side protocol coverage for `named_pipe` remains green in
   the default `pytest`, `mypy`, and `py_compile` gates.

## Not In Scope Yet

- This document does not authorize deleting `FileScriptTransport`.
- This document does not authorize removing file-based paths from
  `PERSISTENT_SESSION.py`.
- This document does not change REST API behavior.
- This document does not change the default environment variables.

## Next Step After Readiness

Once the readiness criteria are satisfied for a sustained period, the next phase
should be a separate, explicit removal plan that:

- removes `file` from default documentation and operational guidance entirely
- reduces host-side file transport code to migration-only stubs or deletes it
- removes file-based real E2E baselines
- keeps one final regression checkpoint before actual deletion
