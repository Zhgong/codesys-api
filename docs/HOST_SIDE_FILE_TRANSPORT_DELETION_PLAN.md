# Host-Side File Transport Deletion Plan

## Summary

This document defined the explicit host-side deletion phase that followed the
removal-candidate stage.

Status: executed.

The goal of that phase was to remove the host-side `file` transport from the
standard runtime and baseline test surface while preserving:

- REST API v1 behavior
- the `named_pipe` primary transport path
- the existing action-layer and engine-adapter contracts

The document originally excluded the CODESYS-side file request path in
`PERSISTENT_SESSION.py`.

That later CODESYS-side cleanup has now also been executed as a separate step.
The subsequent lifecycle cleanup phase 1 has also been executed:

- `session_status.json` removed
- `terminate.signal` removed
- `session.log` retained

## Entry Conditions

The deletion phase started only after all of the following were true:

1. The readiness criteria in `FILE_TRANSPORT_RETIREMENT.md` remained satisfied.
2. The host-side removal-candidate boundary remained stable in the default gates.
3. No current host-side debugging or recovery workflow still depended on the
   `file` transport baseline.

## Executed Host-Side Deletions

The explicit deletion phase removed or reduced the following host-side items:

- `legacy_file_transport.py`
- file-transport runtime selection from `runtime_transport.py`
- file-transport configuration and diagnostic semantics that only existed to
  support host-side compatibility fallback
- file-specific host-side baseline tests:
  - `tests/integration/test_file_transport_legacy_baseline.py`
  - `tests/unit/test_file_transport_legacy_unit.py`

## Required Compatibility Guarantees

The host-side deletion phase preserved:

- `named_pipe` as the only runtime transport path
- existing REST endpoint shapes
- the existing action-layer and engine-adapter contracts
- the current real CODESYS default acceptance flow under `named_pipe`

Unsupported transport names still fail fast.

## Validation For The Deletion Phase

At the end of the explicit deletion phase, the following remained green:

```powershell
python -m pytest -q
python -m mypy
python -m py_compile HTTP_SERVER.py action_layer.py api_key_store.py codesys_e2e_policy.py codesys_process.py runtime_transport.py server_config.py server_logic.py test_server.py ironpython_script_engine.py engine_adapter.py named_pipe_transport.py session_transport.py transport_result.py tests/e2e/codesys/test_real_codesys_e2e.py tests/integration/test_script_executor.py tests/unit/test_http_server_system_info.py tests/unit/test_http_server_transport_boundary.py tests/unit/test_named_pipe_transport.py tests/unit/test_real_codesys_e2e_policy.py tests/unit/test_runtime_transport.py tests/unit/test_server_config.py tests/unit/test_transport_removal_candidate_boundary.py
```

Real acceptance stayed centered on:

- `named_pipe` fast track
- `named_pipe` full track

## Historical Scope Boundary

This plan covered host-side deletion only.

It did not itself authorize:

- deleting file-based transport from `PERSISTENT_SESSION.py`
- changing REST API v1
- introducing CLI work
- changing the `named_pipe` wire protocol

Those concerns were handled separately afterward.
