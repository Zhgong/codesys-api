# CODESYS API Strategic Plan

## Summary

This project was forked and already contains a working REST API, a persistent CODESYS session model, and a file-based IPC path between the HTTP server and the CODESYS-hosted script environment. The plan is to preserve that direction, but convert it into an implementation-ready roadmap that supports safe refactoring and future architectural evolution.

The immediate goal is not to replace everything at once. The immediate goal is to make the current codebase safe to change, define the intended target architecture, and create the internal seams needed for later migration to a cleaner execution model, CLI entrypoint, future AI-oriented tooling, and a future CODESYS script engine that may replace the current IronPython-based script engine.

## Target Architecture

The long-term architecture should be organized into five layers:

1. External entrypoints
   - Existing REST API
   - Future CLI
   - Future AI/tool integrations

2. Command and action layer
   - A single internal action model for status, project, POU, compile, and script execution operations
   - Shared request and response semantics regardless of whether the caller is REST, CLI, or future tool integrations

3. Engine adapter layer
   - Encapsulates the current IronPython and `scriptengine` behavior
   - Exposes engine-neutral operations for status, project, compile, POU, and script execution
   - Becomes the only layer that knows about engine-specific syntax, APIs, and capability differences

4. Transport layer
   - Current implementation: file-based IPC
   - Future implementation: a more explicit local IPC transport
   - The action model must remain stable even if the transport changes

5. CODESYS session execution layer
   - Persistent CODESYS-hosted runtime
   - Project lifecycle operations
   - Compile flow
   - POU creation and code updates
   - Script execution

This layering allows the project to keep the current REST interface stable while improving the internals in stages, and prevents the current IronPython engine from leaking into every part of the codebase.

## Current State

The repository already includes:

- A REST server in `HTTP_SERVER.py`
- A persistent CODESYS session runner in `PERSISTENT_SESSION.py`
- File-based IPC using request, result, status, and termination files
- Existing script-driven test utilities such as `test_server.py` and `api_test_suite.py`

This means the project is not starting from zero. The work is a reorganization and hardening effort, not a greenfield build.

The current weaknesses are primarily:

- Logic concentrated in large root-level modules
- Hard-coded configuration paths and values
- File-based IPC semantics spread across several files and status artifacts
- Limited automated regression coverage for safe migration
- Internal execution behavior coupled tightly to the current HTTP layer
- IronPython and `scriptengine` assumptions embedded directly in the execution path

## Execution Strategy

The implementation order must be:

1. Define the target architecture clearly
2. Map the current implementation against that architecture
3. Create a regression safety net
4. Introduce a shared internal action model
5. Introduce an engine adapter boundary around the current IronPython implementation
6. Refactor internals gradually behind the existing REST interface
7. Add CLI and future integrations after the internal seams are stable

The key principle is to avoid changing transport, public interface, engine implementation, and internal execution logic all at the same time.

## Phase 1: Architecture and Baseline

### Goals

- Freeze the intended system boundaries before large refactors
- Understand the current behavior in detail
- Prepare the codebase for safe change

### Core Tasks

- Document the current request flow from REST handler to script execution
- Identify responsibilities currently mixed inside `HTTP_SERVER.py`
- Identify responsibilities currently mixed inside `PERSISTENT_SESSION.py`
- List all current public endpoints and expected behaviors
- Identify duplicated logic, hard-coded configuration, and unstable error paths
- Normalize documentation and encoding issues in project docs

### Deliverables

- A clear architecture description
- A current-state gap analysis
- A list of migration-safe boundaries for later extraction
- A clear list of IronPython-specific responsibilities that must move behind an adapter boundary

## Phase 2: Test Baseline and Safety Net

### Goals

- Make behavior measurable before refactoring
- Reduce migration risk

### Core Tasks

- Keep existing script-based testing, but reorganize it as a baseline regression suite
- Define a minimum black-box API regression set for:
  - `system/info`
  - `session/status`
  - `session/start`
  - `session/stop`
  - `session/restart`
  - `project/create`
  - `project/open`
  - `project/compile`
  - `pou/create`
  - `pou/code`
- Add failure-path checks for:
  - Unauthorized requests
  - Invalid parameters
  - Execution timeout
  - Session not ready
  - CODESYS-side execution failure
- Add behavior tests for the current file-based IPC path:
  - Request creation
  - Result collection
  - Status updates
  - Timeout handling
  - Recovery from stale artifacts

### Deliverables

- A repeatable regression suite
- A documented baseline for current API behavior

## Phase 3: Internal Action Model

### Goals

- Separate public entrypoints from execution semantics
- Create a stable internal model that future transports and tools can reuse

### Core Tasks

- Define a shared internal request shape with fields such as:
  - `action`
  - `request_id`
  - `params`
  - `timeout`
- Define a shared internal response shape with fields such as:
  - `success`
  - `error`
  - `payload`
  - `timing`
  - `request_id`
- Define a simple internal status lifecycle:
  - `queued`
  - `running`
  - `completed`
  - `failed`
  - `timeout`
- Route existing REST handlers through this action model without breaking REST compatibility
- Prioritize support for:
  - Status operations
  - Project create and open
  - Project compile
  - POU create
  - POU code update
  - Script execution

### Deliverables

- A shared internal action schema
- Reduced coupling between REST handlers and execution details

## Phase 4: Engine Abstraction and Compatibility Boundary

### Goals

- Isolate the current IronPython-based CODESYS script engine from the rest of the application
- Prepare for future migration to a new script engine without rewriting REST, CLI, or the action model

### Core Tasks

- Define an engine-neutral interface for the operations the server needs:
  - session status
  - project create and open
  - project compile
  - POU create
  - POU code update
  - script execution
- Move all IronPython-specific assumptions behind that interface, including:
  - Python 2.7 syntax constraints
  - direct `scriptengine` imports
  - global `scriptengine.system` and `scriptengine.projects` usage
  - engine-specific enum and object access patterns
- Define an engine capability model so that unsupported features can be reported cleanly instead of failing unpredictably
- Treat the current `PERSISTENT_SESSION.py` implementation as the host for the current engine, not as the permanent shape of all future engines

### Deliverables

- A dedicated engine abstraction boundary
- A clear IronPython adapter concept for the current implementation
- A migration path for future engine support without public API churn

## Phase 5: Refactoring and Internal Reorganization

### Goals

- Improve maintainability without unnecessary churn
- Prepare for transport replacement and CLI support

### Core Tasks

- Move configuration handling toward a single configuration entrypoint
- Reduce hard-coded values such as:
  - `CODESYS_PATH`
  - port defaults
  - API key defaults
- Extract logic by responsibility before attempting large directory moves
- Separate:
  - process management
  - action dispatch
  - script generation
  - transport concerns
  - API routing
- Keep the existing REST API stable during this phase

### Deliverables

- Cleaner internal module boundaries
- Lower-risk codebase for later transport evolution

## Phase 6: Transport Evolution

### Goals

- Improve reliability and control of inter-process communication
- Keep public interfaces stable while replacing internal mechanics

### Core Tasks

- Keep file-based IPC as the starting point
- Replace the current transport only after the action model and regression suite are stable
- Ensure transport replacement does not change the public REST contract
- Validate equivalent behavior before and after transport changes

### Intended Outcomes

- Better reliability
- Better observability
- Cleaner request-response correlation
- Lower latency as a secondary benefit

Performance is a benefit, but not the only reason for transport improvement. Reliability, error clarity, and maintainability are higher-priority goals.

## Phase 7: CLI and Future Integrations

### Goals

- Add more suitable entrypoints for local automation and future AI workflows
- Reuse the same internal action model rather than building parallel interfaces

### Core Tasks

- Introduce a future `codesys-cli` that maps directly to existing capabilities
- Ensure CLI and REST both call the same internal action layer
- Avoid creating a second execution model for CLI
- Defer AI-oriented tool definitions until action semantics and testing are stable

### Initial CLI Scope

- `status`
- `open`
- `create`
- `compile`
- `pou create`
- `pou code`
- `execute`

## Testing and Acceptance Criteria

The migration is considered healthy only if:

- Existing REST API behavior remains compatible
- Core workflows still work end-to-end
- Failure cases are consistently represented
- Internal refactors can be verified by repeatable tests
- Transport replacement can be validated against the same regression suite
- Engine-specific changes can be absorbed behind the adapter boundary
- A future script engine can be introduced without changing REST endpoint shapes

## Assumptions

- REST API v1 remains the primary public interface during early phases
- CLI is introduced after internal action boundaries exist
- The current IronPython-based `scriptengine` implementation remains the only engine initially supported
- New script engine support is planned through an adapter boundary, not through direct changes to REST handlers
- Transport replacement happens after tests and action schema are in place
- Large directory reorganization is deferred until responsibilities are clearer
- Existing scripts and docs are treated as useful baseline assets, not discarded by default

## Immediate Next Steps

1. Document the current architecture and execution flow in detail
2. Build the minimum regression suite around current API behavior
3. Define and introduce the internal action schema
4. Define the engine adapter boundary and map current IronPython responsibilities into it
5. Refactor the current server and session logic behind those boundaries
6. Only then begin transport evolution and CLI work
