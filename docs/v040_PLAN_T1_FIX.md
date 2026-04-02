# Task T1-Fix Plan: Complete Doctor Logic Spec

## Overview
Implement the missing checks from `v040_DOCTOR_SPEC.md` into `ActionType.SYSTEM_DOCTOR` in `src/codesys_api/action_layer.py`.

## Proposed Changes

### 1. `src/codesys_api/action_layer.py`
- **Imports**: Add `sys`, `socket`, `urllib.request`, and `urllib.error` if not present. `win32pipe` should be imported safely within the pipe check or at the top level inside a `try...except ImportError`.
- **System Environment**:
  - Add `_check_os_windows()`:
    - Pass: `sys.platform == "win32"`
    - Fail: Suggest "Use a Windows operating system."
- **Static Configuration**:
  - Add `_check_codesys_profile_env()`:
    - Pass: `os.environ.get("CODESYS_API_CODESYS_PROFILE")` is not None.
    - Fail: Suggest "Set CODESYS_API_CODESYS_PROFILE."
  - Add `_check_config_file_validity()`:
    - Logic: Use `load_server_config(Path.cwd(), os.environ)` and catch `ValueError` or `json.JSONDecodeError`.
    - Fail: Suggest "Fix formatting errors in your .env or config file."
- **Enhanced Binary Check**:
  - Modify `_check_codesys_binary()`:
    - In addition to `exists()`, add `os.access(path, os.X_OK)` to verify execution permissions.
    - Fail (No Permission): Suggest "Grant execution permissions to the current user for CODESYS.exe."
- **Runtime Capability (IPC/Named Pipe)**:
  - Replace `_check_runtime_data_dir_write` with `_check_named_pipe_creation()`.
  - Use `import win32pipe` inside the function to test creating `\\.\pipe\codesys_api_doctor_test`.
  - Use `win32pipe.CreateNamedPipe` with basic permissions. Handle `Exception` or `pywintypes.error` to catch failures.
  - Fail: Suggest "Check administrator privileges or Windows pipe permissions."
- **Runtime Capability (Port Availability)**:
  - Add `_check_port_availability()` (default port 8080).
  - Use `socket.socket()` to attempt `bind(('127.0.0.1', 8080))`.
  - Fail: Suggest "Kill the process using port 8080 or change the API port configuration."
- **Connectivity Probe (Server Ping)**:
  - Add `_check_server_connectivity()`.
  - Use `urllib.request.urlopen("http://127.0.0.1:8080/api/v1/system/info", timeout=1.0)`.
  - Status should be `WARN` if it fails (ConnectionRefusedError/URLError), as the user might only want to use CLI without the HTTP server.
  - Warn Suggestion: "Server is not running. Start codesys-tools-server if REST API access is needed."
- **Update Dispatcher**:
  - Update `check_functions` list in `_system_doctor()` to include all new checks in order:
    1. OS Windows check
    2. Python dependency check (pywin32, requests)
    3. CODESYS path env check
    4. CODESYS profile env check
    5. Config file validity check
    6. CODESYS binary check (existence + X_OK)
    7. Named pipe creation check
    8. Port availability check
    9. Server connectivity check

### 2. `tests/unit/test_doctor_logic.py`
- Add mocks (`unittest.mock.patch`) in the test functions for:
  - `sys.platform` to return `"win32"`.
  - `socket.socket` to simulate successful bind.
  - `urllib.request.urlopen` to simulate successful ping.
  - `win32pipe.CreateNamedPipe` to simulate successful pipe creation.
  - `os.access` to return `True` for execution checks.

## Acceptance Criteria
- [ ] OS check correctly verifies `win32`.
- [ ] Named Pipe creation is accurately tested using `win32pipe`.
- [ ] Port 8080 availability is tested.
- [ ] Server ping uses `urllib` or `requests` and returns a WARN if unreachable.
- [ ] Config file validity is verified via `load_server_config`.
- [ ] Binary execution permissions are checked using `os.access`.
- [ ] Tests are updated to pass with mocks.
