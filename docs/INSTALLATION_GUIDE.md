# Installation Guide

## Summary

`codesys-tools` is a Windows-first local package for automating CODESYS through:

- `codesys-tools`
- `codesys-tools-server`

It assumes a local CODESYS installation is already present.

## Support Boundary

Current public-facing support level:

- Windows-only
- experimental
- local CODESYS environment required
- `named_pipe` only

This guide does not cover:

- PyPI publishing
- non-Windows platforms
- installer-based deployment

## Prerequisites

- Windows
- Python 3.13+
- CODESYS installed locally
- a valid CODESYS profile available on disk

Required runtime environment variables:

- `CODESYS_API_CODESYS_PATH`
- `CODESYS_API_CODESYS_PROFILE`
- `CODESYS_API_CODESYS_PROFILE_PATH`

Optional:

- `CODESYS_API_CODESYS_NO_UI=1`

## Install From Source

```powershell
pip install .
```

## Install From Wheel

```powershell
python scripts\build_release.py
python -m pip install dist\codesys_tools-*.whl
```

Upgrade an existing installation:

```powershell
python -m pip install --upgrade dist\codesys_tools-*.whl
```

## Verify The Installation

CLI:

```powershell
codesys-tools --help
codesys-tools --json session status
```

Server:

```powershell
codesys-tools-server --help
```

Repo-local compatibility entrypoints:

```powershell
python codesys_cli.py --help
python HTTP_SERVER.py --help
```

## Minimal Local Smoke

```powershell
codesys-tools session start
codesys-tools project create --path C:\work\demo.project
codesys-tools project compile
codesys-tools project close
codesys-tools session stop
```

## Common Setup Problems

- `CODESYS profile is not configured`
  - set `CODESYS_API_CODESYS_PROFILE` or `CODESYS_API_CODESYS_PROFILE_PATH`
- `CODESYS executable not found`
  - fix `CODESYS_API_CODESYS_PATH`
- `Unsupported transport`
  - only `named_pipe` is supported

## API Keys

Default API key storage is user-local:

- `%APPDATA%\codesys-api\api_keys.json`

The install location does not need to be writable.

## Related Docs

- [CLI_USAGE.md](CLI_USAGE.md)
- [PACKAGING.md](PACKAGING.md)
- [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md)
