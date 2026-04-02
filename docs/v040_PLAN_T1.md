# Task T1 Plan: Action Layer Doctor Logic

## Overview
Implement `ActionType.SYSTEM_DOCTOR` to provide environment diagnostics without interacting with the CODESYS process.

## Proposed Changes

### 1. `src/codesys_api/action_layer.py`
- **Enum Update**: Add `SYSTEM_DOCTOR = "system.doctor"` to `ActionType`.
- **Dispatcher Update**: In `ActionService.execute`, route `SYSTEM_DOCTOR` to `self._system_doctor`.
- **New Method `_system_doctor(self, request: ActionRequest) -> ActionResult`**:
    - Implement a list of check functions.
    - **Python Deps**: Test `import win32api`, `import requests`.
    - **CODESYS_PATH**: Check `os.environ`.
    - **Binary Check**: Validate file existence of `CODESYS.exe`.
    - **IPC/Pipe Check**: Test directory write permissions in the runtime data dir.
    - Aggregate results into a `checks` list in the response body.

### 2. `src/codesys_api/runtime_paths.py`
- (Optional) Add a helper to locate the CODESYS executable if not already present.

## TDD Strategy
- **File**: `tests/test_doctor_logic.py`
- **Mocking**: Use `unittest.mock.patch` for `os.environ` and `importlib` to simulate missing dependencies.
- **Assertions**: 
    - Verify `success` is `True` even if some checks `FAIL` (as long as the doctor itself ran).
    - Verify structure of `body['checks']`.

## Acceptance Criteria Check
- [ ] Returns `success` flag.
- [ ] Body contains `checks` list with `status` and `suggestion`.
- [ ] No system state modification (cleanup any temp files).
