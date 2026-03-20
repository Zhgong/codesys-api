# CODESYS API Strategic Plan

## Summary

The repository has already completed the heavy internal transition:

- typed host-side modules
- shared action layer
- engine adapter boundary
- named-pipe-only transport
- lifecycle cleanup phase 2
- baseline phase

The transport, lifecycle, compile-hardening, and local CLI lines are now all substantially complete. The current priority is to formalize the baseline before structural work.

## Current Checkpoint

Completed lines:

- transport retirement is done
- file-based control and status are gone
- file-based logging is gone
- compile hardening is done
- CLI v1 and v2 command coverage are in place
- CLI final polish is in place
- formal baseline documentation and runner are in place

Current CLI coverage now includes:

- `session start|restart|status|stop`
- `project create|open|save|close|list|compile`
- `pou create|list|code`

`/api/v1/system/logs` remains, but it now reads from an in-memory runtime log buffer instead of a file.

## Target Architecture

1. External entrypoints
   - REST API
   - Local CLI
   - Future AI/tool integrations

2. Command and action layer
   - shared internal action semantics
   - no REST-specific business logic leakage

3. Engine adapter layer
   - all CODESYS/IronPython-specific behavior stays here

4. Transport and runtime layer
   - named-pipe only
   - lifecycle control/status/logging file artifacts are gone
   - `/api/v1/system/logs` remains as a runtime log view

5. CODESYS session execution layer
   - persistent runtime
   - project lifecycle
   - compile/generate-code flow
   - POU creation and code updates

## Strategic Direction

### Completed

- architecture and safety-net work
- action layer extraction
- engine abstraction
- runtime hardening
- transport evolution
- lifecycle cleanup phase 2
- compile hardening
- CLI productization and final polish

### Active Phase

Baseline establishment:

- `BASELINE.md` defines the current gates and real acceptance expectations
- `scripts/run_baseline.py` provides the local engineering baseline entrypoint
- the baseline now gates the next two major phases:
  - repo reorganization
  - packaging

### Deferred

- repo reorganization
- packaging for `pip install .`
- broader CLI packaging/distribution
- future AI/tool integration surfaces

## Guidance

- Do not reopen transport design unless a regression forces it.
- Keep REST API v1 stable.
- Keep `named_pipe` as the only supported runtime transport.
- Treat lifecycle cleanup as done unless a regression appears.
- Use the baseline before any repo reorg or packaging work.
