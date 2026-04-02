# Audit Report: v040_PLAN_T1_FIX

## Overview
This document evaluates the implementation plan for Task T1-Fix (Doctor Logic Enhancement) against the project's engineering standards and the requirement for automated verification.

## Ratings & Analysis

| Criterion | Score | Rationale & Requirements |
| :--- | :---: | :--- |
| **OS Compatibility Check** | 10/10 | Verified via `sys.platform` mock. Critical for a Windows-only tool. |
| **Named Pipe Verification** | 9/10 | Validates IPC capabilities. **Must** handle `ImportError` gracefully in test environments. |
| **Port 8080 Availability** | 9/10 | Prevents startup failures. Test must mock `socket.bind` failures. |
| **Connectivity Probe (Ping)** | 8/10 | Uses `WARN` status correctly. Automated tests must cover `ConnectionRefusedError` and success. |
| **Config Integrity Check** | 9/10 | Reuses `load_server_config`. Essential for catching environment issues early. |
| **Execution Permission Check**| 9/10 | Goes beyond existence check using `os.access`. Tests must simulate `X_OK` failure. |
| **Automated Test Coverage** | 10/10 | **Mandatory**. All new logic must be validated via `unittest.mock` to eliminate the need for manual testing. |

## Automated Verification Strategy
To avoid manual verification, the following test cases will be implemented in `tests/unit/test_doctor_logic.py`:
1.  `test_doctor_os_fail`: Mock `sys.platform = 'linux'` -> Expect `FAIL`.
2.  `test_doctor_pipe_permission_denied`: Mock `win32pipe.CreateNamedPipe` to raise `AccessDenied` -> Expect `FAIL`.
3.  `test_doctor_port_collision`: Mock `socket.socket.bind` to raise `OSError` (Address in use) -> Expect `FAIL`.
4.  `test_doctor_server_offline`: Mock `urllib.request.urlopen` to raise `URLError` -> Expect `WARN`.
5.  `test_doctor_config_corrupted`: Mock `load_server_config` to raise `ValueError` -> Expect `FAIL`.

## Conclusion
The plan is **Approved for Implementation**. The emphasis on mocking Windows-specific APIs ensures that the CI/CD pipeline can verify the fix regardless of the host OS.
