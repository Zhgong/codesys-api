# Repository Guidelines

## Project Structure & Module Organization
This repository is a flat Windows-first Python project. Core runtime files live at the repo root: `HTTP_SERVER.py` exposes the REST API, `PERSISTENT_SESSION.py` runs inside CODESYS, and `windows_service.py` wraps the server as a Windows service. Client, debug, and integration scripts such as `example_client.py`, `api_test_suite.py`, and `debug_*.py` also live at the root. `ScriptLib/Stubs/scriptengine/` contains CODESYS stub files; `requests/` and `results/` are runtime IPC directories and should not hold hand-written source.

## Build, Test, and Development Commands
Install dependencies with `pip install requests pywin32`.

- `python HTTP_SERVER.py` or `run_server.bat`: start the real API server.
- `python test_server.py` or `run_test_server.bat`: start a mock server without CODESYS.
- `python example_client.py`: run the basic end-to-end client flow.
- `python api_test_suite.py`: run the broader API regression script.
- `python simplified_debug.py`: collect local diagnostics.
- `install.bat`: install and start the Windows service as administrator.

## Coding Style & Naming Conventions
Use 4-space indentation, module docstrings, and clear logging around process, file, and API failures. Match the existing naming in each area: root service/server modules use uppercase filenames, helper and test scripts use lowercase snake_case. Keep Python 3 syntax in server, client, and test scripts. Only use Python 2.7/IronPython-compatible syntax in `PERSISTENT_SESSION.py`.

## Testing Guidelines
There is no formal pytest suite; testing is script-driven. Name new checks `test_*.py` or `debug_*.py` to match the current pattern. For fast validation, run `python test_server.py` and hit `/api/v1/system/info`. For CODESYS-backed changes, also run `python example_client.py` or `python api_test_suite.py` and note any required local setup.

## Commit & Pull Request Guidelines
Recent commits use short imperative subjects such as `Fix threading issue...`, `Add project compilation endpoint`, and `Revert ...`. Follow that style, keep subjects specific, and separate unrelated fixes. PRs should include a short summary, affected endpoints or scripts, manual test steps, and any Windows/CODESYS version assumptions. Include log excerpts or screenshots only when they clarify service or API behavior.

## Configuration & Safety Notes
Do not commit machine-specific secrets or local paths. `HTTP_SERVER.py` contains `SERVER_PORT` and `CODESYS_PATH`; document local overrides in the PR instead of hard-coding personal values unless the repository intentionally updates its defaults.
