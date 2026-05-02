# Installation Guide

## Requirements

- Windows 10 or later
- Python 3.13+
- CODESYS installed locally

## Install from wheel

```powershell
python -m pip install dist\codesys_tools-*.whl
```

## Install for local development

```powershell
pip install .
```

## Verify installation

```powershell
codesys-tools --help
codesys-tools-server --help
```

## Required environment variables

Before using the CLI or server, set the following environment variables:

```powershell
$env:CODESYS_API_CODESYS_PATH="C:\Program Files\CODESYS 3.5.20.60\CODESYS\Common\CODESYS.exe"
$env:CODESYS_API_CODESYS_PROFILE="CODESYS V3.5 SP20 Patch 6"
$env:CODESYS_API_CODESYS_PROFILE_PATH="C:\Program Files\CODESYS 3.5.20.60\CODESYS\Profiles\CODESYS V3.5 SP20 Patch 6.profile.xml"
$env:CODESYS_API_CODESYS_NO_UI="1"
```

## Diagnostics

```powershell
codesys-tools doctor
```

Reports missing or misconfigured environment variables and common setup issues.
