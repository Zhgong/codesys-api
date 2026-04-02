# Task T1-Fix: Doctor Logic Implementation & Verification

## Goal
Implement and verify enhanced diagnostic checks in the `system.doctor` action to ensure robust environment validation.

## Modification Strategy

### 1. `src/codesys_api/action_layer.py`
- (Already implemented) Ensure `_system_doctor` executes the following checks in order:
    1. OS Compatibility (Windows-only)
    2. Python Dependencies (`pywin32`, `requests`)
    3. CODESYS Environment Variables
    4. Config File Integrity (using `load_server_config`)
    5. CODESYS Binary Existence & Execution Permission
    6. Named Pipe Creation Capability
    7. HTTP Port Availability
    8. Local Server Connectivity (Ping)

### 2. `tests/unit/test_doctor_logic.py` (TDD Standard)
Enhance the existing test suite to cover all failure scenarios using `unittest.mock`.

- **test_doctor_os_fail**:
    - Mock `sys.platform = 'linux'`.
    - Expect `Operating system` check status to be `FAIL`.
- **test_doctor_pipe_permission_denied**:
    - Mock `win32pipe.CreateNamedPipe` to raise `OSError` (Access Denied).
    - Expect `Named pipe creation` check status to be `FAIL`.
- **test_doctor_port_collision**:
    - Mock `socket.socket.bind` to raise `OSError` (Address in use).
    - Expect `HTTP port availability` check status to be `FAIL`.
- **test_doctor_server_offline**:
    - Mock `urllib.request.urlopen` to raise `URLError`.
    - Expect `Server connectivity` check status to be `WARN`.
- **test_doctor_config_corrupted**:
    - Mock `load_server_config` to raise `ValueError`.
    - Expect `Configuration validity` check status to be `FAIL`.
- **test_doctor_execution_permission_fail**:
    - Mock `os.access` to return `False`.
    - Expect `CODESYS binary` check status to be `FAIL`.

## Verification Criteria
- All 10 diagnostic checks must be present in the output of `system.doctor`.
- Each failure scenario must result in the correct status (`FAIL` or `WARN`) and a helpful `suggestion`.
- All tests in `tests/unit/test_doctor_logic.py` must pass on a CI environment without needing actual CODESYS installation.
