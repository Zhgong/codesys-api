# CODESYS API Strategic Plan

## Summary

The repository has already completed the heavy internal transition:

- typed host-side modules
- shared action layer
- engine adapter boundary
- named-pipe-only transport
- lifecycle cleanup phase 2
- baseline phase
- repo reorganization phase
- packaging phase 1
- root cleanup phase
- packaging phase 2
- internal wheel release flow

The transport, lifecycle, compile-hardening, local CLI, packaging phase 1, root cleanup, packaging phase 2, and internal wheel release flow are now all substantially complete. The current priority is no longer internal cleanup; it is to decide the next outward-facing phase.

## Current Checkpoint

Completed lines:

- transport retirement is done
- file-based control and status are gone
- file-based logging is gone
- compile hardening is done
- CLI v1 and v2 command coverage are in place
- CLI final polish is in place
- formal baseline documentation and runner are in place
- repeatable wheel and sdist generation is in place
- clean wheel-install smoke is in place
- internal release checklist and release notes are in place

Current CLI coverage now includes:

- `session start|restart|status|stop`
- `project create|open|save|close|list|compile`
- `pou create|list|code`

`/api/v1/system/logs` remains, but it now reads from an in-memory runtime log buffer instead of a file.

The repository layout has already shifted away from the flat root:

- core host-side implementation is moving into `src/codesys_api/`
- runtime stub assets are moving into `src/codesys_api/assets/`
- long-lived documents are moving into `docs/`
- debug and diagnostic helpers are moving into `scripts/debug/`
- root entrypoints remain temporarily for compatibility
- installation entrypoints now exist via `codesys-cli` and `codesys-api-server`

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

### Completed

- packaging phase 2:
  - `docs/BASELINE.md` remains the engineering gate
  - `scripts/build_release.py` is the release-artifact gate
  - repeatable `wheel + sdist` generation is validated
  - clean wheel-install smoke is validated
  - packaged console scripts and packaged assets resolve correctly

### Next Decision

- broader product-facing work
- future AI/tool integration surfaces
- broader public release decisions beyond internal distribution flow

### Deferred

- none in the old cleanup/release line; that line is now complete

## Guidance

- Do not reopen transport design unless a regression forces it.
- Keep REST API v1 stable.
- Keep `named_pipe` as the only supported runtime transport.
- Treat lifecycle cleanup as done unless a regression appears.
- Use the baseline continuously during repo reorg.
- Prefer compatibility wrappers over one-shot breaking moves during this phase.
