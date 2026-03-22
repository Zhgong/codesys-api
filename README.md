# codesys-tools

Windows-first, experimental local automation tooling for CODESYS.

`codesys-tools` provides:

- a local CLI: `codesys-tools`
- a local HTTP server: `codesys-tools-server`
- a persistent CODESYS runtime built around `named_pipe`

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

The CLI and server both use the same runtime wiring and packaged assets.

## Quick Start

CLI:

```powershell
codesys-tools --help
codesys-tools session start
codesys-tools project create --path C:\work\demo.project
codesys-tools project compile
codesys-tools project close
codesys-tools session stop
```

Server:

```powershell
codesys-tools-server --help
python HTTP_SERVER.py
```

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
