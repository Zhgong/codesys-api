# Installation Guide

## Summary

`codesys-api` is a Windows-first local package for automating CODESYS through:

- `codesys-cli`
- `codesys-api-server`

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
- Python 3.14+
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
python -m pip install dist\codesys_api-*.whl
```

Upgrade an existing installation:

```powershell
python -m pip install --upgrade dist\codesys_api-*.whl
```

## Verify The Installation

CLI:

```powershell
codesys-cli --help
codesys-cli --json session status
```

Server:

```powershell
codesys-api-server --help
```

Repo-local compatibility entrypoints:

```powershell
python codesys_cli.py --help
python HTTP_SERVER.py --help
```

## Minimal Local Smoke

```powershell
codesys-cli session start
codesys-cli project create --path C:\work\demo.project
codesys-cli project compile
codesys-cli project close
codesys-cli session stop
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
