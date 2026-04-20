# Troubleshooting & Debugging

This page outlines the methodology and specific fixes for common issues in the Codesys-API.

## Core Debugging Methodology
When a multi-layer system fails, follow the **Layer Isolation Protocol**:
1. **Isolate**: Test each layer independently (OS → Service → HTTP).
2. **Probes**: Use minimal, single-purpose probes (`scripts/manual/`) instead of full E2E runs.
3. **Verify**: A probe that passes definitively clears all layers below it.
4. **Calculated Accumulation**: For bugs that appear after $N$ iterations, calculate resource growth (memory, handles, pipe buffers) vs. system limits.

## Common Issues & Fixes

### 1. HTTP Lifecycle Stall (Resolved)
- **Symptom**: Server stops responding after ~7-8 full lifecycles (start/create/stop).
- **Cause**: `BaseHTTPRequestHandler` writes access logs to `stderr`. If the server is started with `stderr=PIPE` and not consumed, the 4KB buffer fills up, causing the server to block.
- **Fix**: Overridden `log_message()` to write to a file logger instead of `stderr`.

### 2. CODESYS Startup Failures
- **Symptom**: CODESYS process starts but terminates immediately or prompts for a profile.
- **Checks**:
  - Run `codesys-tools doctor` to verify `CODESYS_PATH`.
  - Use `scripts/manual/profile_launch_probe.py --mode all` to check launch string compatibility.
  - **Identity**: CODESYS may fail if launched from a service/sandbox identity (e.g., Codex) that lacks access to the AP Installer Event Logs. Use a normal user terminal for authoritative testing.

### 3. "Controls created on one thread..." Error
- **Symptom**: `scriptengine.projects.open()` fails when opening a template (e.g., `Standard.project`).
- **Fact**: CODESYS templates cannot be opened as normal projects via the script engine due to COM threading constraints.
- **Fix**: Use `projects.create(path, True)` to create a new empty project instead of opening a template.

### 4. Orphan Processes
- **Symptom**: Residual CODESYS windows remain after a session stop.
- **Fix**: `CodesysProcessManager` uses `taskkill /T /F` to ensure the entire process tree is terminated.

## Diagnostic Tools
- `codesys-tools doctor`: Environment health check.
- `codesys-tools --json doctor`: Automation-friendly health check.
- `scripts/manual/run_real_codesys_e2e.py`: Main integration test suite.
- `/api/v1/system/logs`: Fetch runtime server logs.

## The "Two-Bug Trap"
**Warning**: After fixing a lower-layer bug (e.g., orphan processes), always re-run the high-level test. Multiple independent bugs often hide behind each other. Don't assume the system is green until the original failing E2E test passes.
