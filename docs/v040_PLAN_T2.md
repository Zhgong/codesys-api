# Task T2 Plan: CLI Integration - Doctor Command

## Overview
Register the `doctor` command in the CLI and map it to the `SYSTEM_DOCTOR` action. Ensure proper formatting and exit codes.

## Proposed Changes

### 1. `src/codesys_api/cli_entry.py`
- **Parser Update**: 
    - In `build_parser()`, add `doctor` as a new top-level subparser.
    - Add a description: "Check system environment and dependencies."
- **Request Mapping**:
    - Update `_build_action_request()` to map `args.resource == 'doctor'` to `ActionType.SYSTEM_DOCTOR`.
- **Formatting Logic**:
    - Update `_format_human_result()` to handle `SYSTEM_DOCTOR`.
    - Format the `checks` list:
        - `[PASS] Python dependencies`
        - `[FAIL] CODESYS_PATH environment variable -> Set CODESYS_PATH to your CODESYS installation directory.`
- **Exit Code Logic**:
    - In `run_cli()`, ensure that if `request.action == ActionType.SYSTEM_DOCTOR`, we check if any individual check has `status == 'FAIL'`. If so, return exit code `1` even if the action itself "succeeded" in running.

## TDD Strategy
- **File**: `tests/integration/test_cli_doctor.py`
- **Scenarios**:
    - **Success**: All checks PASS -> Exit Code 0, all output to stdout.
    - **Partial Failure**: Some checks FAIL -> Exit Code 1, FAIL items to stderr.
    - **JSON Mode**: `--json doctor` -> returns raw JSON.

## Acceptance Criteria Check
- [ ] `codesys-tools doctor` command exists and shows report.
- [ ] Exit code is 1 if any check fails.
- [ ] Output includes suggestions for non-PASS items.
