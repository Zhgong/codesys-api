# File Transport Retirement Readiness

## Current Position

- `named_pipe` is the only supported runtime transport.
- host-side `file` transport has been deleted.
- the historical CODESYS-side file request/result path has also been deleted from `PERSISTENT_SESSION.py`.
- file-based control and status have also been removed.
- the only remaining file artifact is:
  - `session.log`

## Historical Readiness Criteria

The host-side `file` transport reached removal-candidate status only after all
of the following were true:

1. `named_pipe` passed the default fast real CODESYS acceptance repeatedly.
2. `named_pipe` passed the default full real CODESYS acceptance repeatedly.
3. No known runtime issue required switching to `file` for main project, POU,
   script, compile, or recovery workflows.
4. Transport diagnostics and recovery analysis could be performed using
   `named_pipe` logs, metadata, and tests without depending on `file`.
5. Host-side and CODESYS-side protocol coverage for `named_pipe` stayed green in
   the default `pytest`, `mypy`, and `py_compile` gates.

## Historical Candidate Boundary

The removal-candidate boundary that enabled host-side deletion was:

- keep `file` behind explicit legacy seams
- isolate the host-side file transport implementation
- keep the primary transport facade free of file-specific exports
- keep runtime transport selection on a primary-builder path
- fail fast on unsupported transport names
- keep default diagnostics and default acceptance centered on `named_pipe`
- postpone deletion of the CODESYS-side file request path until host-side work was complete

## Current Status

The host-side deletion phase defined in
`HOST_SIDE_FILE_TRANSPORT_DELETION_PLAN.md` has been executed.

The follow-up CODESYS-side request-path cleanup has also been executed.

This document is now purely historical. It records the readiness conditions that
justified file transport retirement and no longer gates active implementation.

## Not In Scope

- changing REST API behavior
- changing the default environment variables for the current `named_pipe` runtime
- evolving the remaining log-file lifecycle behavior
