# Operations & Usage

This guide covers the installation, configuration, and day-to-day operation of the Codesys-API.

## Prerequisites
- **OS**: Windows (Required).
- **Python**: 3.13+.
- **Software**: CODESYS 3.5+ installed locally.
- **Environment Variables**:
  - `CODESYS_API_CODESYS_PATH`: Path to `CODESYS.exe`.
  - `CODESYS_API_CODESYS_PROFILE`: Name of the CODESYS profile.
  - `CODESYS_API_CODESYS_PROFILE_PATH`: Path to the profile XML.
  - `CODESYS_API_TRANSPORT`: Set to `named_pipe` (only supported transport).

## Installation
### From Source
```powershell
pip install .
```

### From Wheel (Release Build)
```powershell
python scripts\build_release.py
pip install dist\codesys_tools-*.whl
```

## CLI Reference
The CLI provides a convenient way to execute single actions or manage the server.

- **Help**: `codesys-tools --help`
- **Doctor (Preflight)**: `codesys-tools doctor` (Check environment health).
- **Server**: `codesys-tools-server` (Start the persistent REST API server).
- **Session**:
  - `codesys-tools session start`
  - `codesys-tools session status`
  - `codesys-tools session stop`
- **Project**:
  - `codesys-tools project create --path C:\work\demo.project`
  - `codesys-tools project compile --clean-build`
- **POU**:
  - `codesys-tools pou create --name MyFB --type FunctionBlock --language ST`
  - `codesys-tools pou code --path Application\MyFB --implementation-file code.txt`

## REST API Reference
The HTTP server defaults to port `8080`. All requests require `Authorization: ApiKey <token>`.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/session/start` | Launch CODESYS and start IPC session. |
| GET | `/api/v1/session/status` | Check if CODESYS and IPC are alive. |
| POST | `/api/v1/project/create` | Create and open a new project. |
| POST | `/api/v1/project/compile` | Trigger a build and return message counts. |
| POST | `/api/v1/pou/code` | Update POU declaration and implementation. |
| POST | `/api/v1/script/execute` | Execute arbitrary IronPython code in CODESYS. |

## Deployment as Windows Service
The system can be wrapped as a Windows Service for persistent background operation.
- **Install**: `install.bat` (Run as Admin).
- **Uninstall**: `uninstall.bat` (Run as Admin).
- **Service Logic**: Managed by `windows_service.py`, handles auto-recovery and logging.

## Security
- **API Keys**: Stored in `%APPDATA%\codesys-api\api_keys.json`.
- **Default Key**: `admin` (Use for initial setup/testing).
- **Restriction**: The CLI and Server currently only support `named_pipe` for local IPC.
