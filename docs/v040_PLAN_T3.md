# Task T3 Plan: AI Metadata - AGENT.md

## Overview
Create `AGENT.md` in the root directory to serve as a comprehensive guide for AI Agents interacting with the CODESYS API.

## Proposed Content for AGENT.md

### 1. Operations Overview
- **Diagnostic First**: Instructions to always run `doctor` first.
- **Output Formats**: Mentioning `--json` for CLI and standard JSON for REST.

### 2. CLI Command Hierarchy
- Structured list of all `codesys-tools` commands.
- Brief description and example for each.

### 3. REST API Reference
- Base URL and Auth mechanism.
- Mapping of REST endpoints to internal ActionTypes.
- JSON payload examples for common tasks (Start Session, Compile Project, Update POU).

### 4. Error Handling and Resilience
- Explanation of the `success` flag.
- Meaning of HTTP status codes in this context.
- Advice on handling CODESYS-specific bottlenecks (timeouts, busy state).

## Strategy
- Create `AGENT.md` at the root.
- Cross-reference with `cli_entry.py` and `http_server.py` to ensure accuracy.
- Add a "Cheatsheet" section for common AI prompt patterns.

## Acceptance Criteria Check
- [ ] Contains CLI command hierarchy.
- [ ] Contains typical API call examples.
- [ ] Contains error handling advice.
