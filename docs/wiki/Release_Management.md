# Release Management

This page tracks the strategic roadmap, release history, and quality gates for the Codesys-API project.

## Strategic Roadmap

### Current Phase: Stability & AI Integration (v0.4.x)
- **Goal**: Harden the core primitives and make the tool seamlessly accessible to AI agents.
- **Key Features**: 
  - `codesys-tools doctor` for automated environment diagnostics.
  - MCP Server for direct integration with AI tools (Claude, Cursor).
  - Expanded REST API (18 endpoints).
  - Migration from file-based IPC to **Named Pipes**.

### Future Phase: Visuals & Ecosystem (v0.5.0)
- **Goal**: Improve project visibility and marketing.
- **Planned**: VHS recordings of core workflows (session start -> POU create -> compile) for README demos.

## Release History

### v0.4.0 (In Progress)
- **Summary**: DX Enhancement (Visibility & Readiness).
- **Changes**: 
  - Added `codesys-tools doctor`.
  - Added `AGENT.md` for AI context.
  - Added `examples/` for robust AI automation.
  - Retired file-based transport in favor of Named Pipes.

### v0.3.0 (2026-03-30)
- **Summary**: Workflow reliability hardening based on real-CODESYS validation.
- **Key Changes**:
  - Implementation of `NamedPipeTransport`.
  - Introduction of `proven_primitives.py` as the single source of truth for CODESYS scripts.
  - Fixed HTTP server lifecycle stalls.
  - Redirected CLI logs to `%APPDATA%\codesys-api\logs\`.

### v0.2.1
- **Status**: Baseline established with 170+ passed tests.

## Quality Gates

To ensure stability across releases, the following gates must be passed:

1. **Engineering Gate (Baseline)**:
   - Run `python scripts/run_baseline.py`.
   - Goal: 0 failures, 100% mypy coverage on source files.

2. **Packaging Gate**:
   - Run `python scripts/build_release.py`.
   - Verify `wheel` and `sdist` generation.
   - Run wheel-install smoke tests to ensure assets and entrypoints resolve correctly.

3. **E2E Validation (Real CODESYS)**:
   - Execute `pytest tests/e2e/codesys/` on a Windows machine with a real CODESYS installation.
   - Must cover `http-pipe-stress` and basic project lifecycles.

4. **Publication Gate**:
   - Publish to TestPyPI and verify via `Verify Published Package` workflow.
   - Final release to PyPI.
