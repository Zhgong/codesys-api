# codesys-tools

Windows-first, experimental local automation tooling for CODESYS.

`codesys-tools` provides:

- a local CLI: `codesys-tools`
- a local HTTP server: `codesys-tools-server`
- a persistent CODESYS runtime built around `named_pipe`

## Product Goal

This project is optimized for user-facing utility, not for any single transport or hosting mechanism.

The goal is to give users a reliable way to work with one persistent CODESYS session across multiple steps, so they can:

- keep a CODESYS session alive across separate commands
- operate on the same project incrementally instead of rebuilding state every time
- get trustworthy results from each step, especially for compile/build flows

From the product perspective, `CLI`, `HTTP`, `named_pipe`, background services, threads, and process boundaries are implementation details.
They are only acceptable if they preserve the core utility above without introducing false success, false failure, duplicate IDE instances, or UI-thread crashes.

## Support Boundary

This project is currently published as:

- Windows-only
- experimental
- intended for local CODESYS installations

Current assumptions:

- CODESYS must already be installed on the target machine
- supported Python versions are 3.13 and 3.14
- the runtime transport is `named_pipe` only
- the package does not include a bundled CODESYS runtime
- public release prep is in place, but the project is not yet committed to cross-platform support

## Installation

For local development:

```powershell
pip install .
```

For release artifacts:

```powershell
python scripts\build_release.py
python -m pip install dist\codesys_tools-*.whl
```

## Required Environment

At minimum, local CODESYS usage requires:

- `CODESYS_API_CODESYS_PATH`
- `CODESYS_API_CODESYS_PROFILE`
- `CODESYS_API_CODESYS_PROFILE_PATH`
- `CODESYS_API_CODESYS_NO_UI=1` for headless project workflows to avoid the WinForms crash on `project/create`

The CLI and server both use the same runtime wiring and packaged assets.

## Quick Start

Server:

```powershell
codesys-tools-server --help
python HTTP_SERVER.py
```

HTTP is the primary product surface for persistent multi-step workflows.

CLI:

```powershell
codesys-tools --help
```

CLI notes:

- each `codesys-tools` invocation executes one action
- reuse the same `CODESYS_API_PIPE_NAME` when you want later CLI commands to attach to the same CODESYS session
- use `codesys-tools-server` when you want the primary persistent-session workflow

## HTTP Workflow Example

Start the server with the required environment:

```powershell
$env:CODESYS_API_CODESYS_PATH="C:\Program Files\CODESYS 3.5.20.60\CODESYS\Common\CODESYS.exe"
$env:CODESYS_API_CODESYS_PROFILE="CODESYS V3.5 SP20 Patch 6"
$env:CODESYS_API_CODESYS_PROFILE_PATH="C:\Program Files\CODESYS 3.5.20.60\CODESYS\Profiles\CODESYS V3.5 SP20 Patch 6.profile.xml"
$env:CODESYS_API_CODESYS_NO_UI="1"
codesys-tools-server
```

Then send authenticated requests with:

- `Authorization: ApiKey admin`

Example workflow:

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/v1/session/start -Headers @{ Authorization = "ApiKey admin" }
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/v1/project/create -Headers @{ Authorization = "ApiKey admin" } -ContentType "application/json" -Body '{"path":"C:\\work\\demo.project"}'
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/v1/pou/create -Headers @{ Authorization = "ApiKey admin" } -ContentType "application/json" -Body '{"name":"CounterFB","type":"FunctionBlock","language":"ST"}'
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/v1/pou/code -Headers @{ Authorization = "ApiKey admin" } -ContentType "application/json" -Body '{"path":"Application\\CounterFB","declaration":"VAR_INPUT`n    Enable : BOOL;`nEND_VAR","implementation":"Output := Enable;"}'
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/v1/project/save -Headers @{ Authorization = "ApiKey admin" }
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/v1/project/close -Headers @{ Authorization = "ApiKey admin" }
```

Compile note:

- `project/compile` runs against the active persistent session and returns CODESYS message-store results
- POU declarations sent via `pou/code` must omit the `FUNCTION_BLOCK` / `PROGRAM` header line; start at the `VAR` sections

Repo-local compatibility entrypoints remain available:

- `python codesys_cli.py ...`
- `python HTTP_SERVER.py`
- `run_cli.bat ...`

## What It Does

- starts and stops a local persistent CODESYS session
- creates, opens, saves, closes, and compiles projects
- creates and edits POUs
- exposes the same core actions through both CLI and HTTP entrypoints

Compile validation currently uses:

- build
- generate code

## Validation Status

Current local engineering baseline:

- `python scripts\run_baseline.py`
- latest expected result: `170 passed, 8 skipped`

Current release validation:

- `python scripts\build_release.py`
- clean wheel-install smoke
- packaged asset lookup smoke
- GitHub Actions CI and manual release workflows

## Documentation

- [docs/CLI_USAGE.md](docs/CLI_USAGE.md): CLI commands and examples
- [docs/INSTALLATION_GUIDE.md](docs/INSTALLATION_GUIDE.md): installation and local setup
- [docs/PACKAGING.md](docs/PACKAGING.md): build and wheel verification flow
- [docs/RELEASE.md](docs/RELEASE.md): internal wheel release checklist
- [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md): public release preparation checklist
- [docs/BASELINE.md](docs/BASELINE.md): baseline gates and validation commands
- [.github/workflows](.github/workflows): CI, release-build, and manual publish workflows

## Not Included

This project does not currently provide:

- a hosted/cloud service
- cross-platform support
- a bundled CODESYS installation
- an installer
- public API stability guarantees beyond the current local tooling contract

## License

MIT. See [LICENSE](LICENSE).
