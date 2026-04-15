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

## MCP Server

For AI-native workflows (Claude Code, Claude Desktop, Cursor), use the MCP server instead of HTTP:

```powershell
# Repo-local (dev)
python MCP_SERVER.py

# After pip install
codesys-tools-mcp
```

**Remote access** (Claude Code on another machine):
```json
{
  "mcpServers": {
    "codesys": {
      "url": "http://<this-machine-IP>:8001/sse"
    }
  }
}
```

**Local access** (Claude Desktop on the same machine):
```json
{
  "mcpServers": {
    "codesys": {
      "command": "powershell",
      "args": ["-File", "C:\\path\\to\\codesys-api\\start-mcp.ps1"]
    }
  }
}
```

The MCP server exposes all 15 CODESYS operations as native tools. No `Authorization` header needed — MCP transport handles security.

**MCP environment variables** (set in `.env.real-codesys.local`):

| Variable | Default | Description |
| --- | --- | --- |
| `CODESYS_API_MCP_TRANSPORT` | `sse` | `sse` for network access, `stdio` for local Claude Desktop |
| `CODESYS_API_MCP_HOST` | `0.0.0.0` | Bind address |
| `CODESYS_API_MCP_PORT` | `8001` | SSE port |

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

### Session

| Method | Path | Body params | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/session/start` | — | Launch CODESYS process and open IPC session. |
| POST | `/api/v1/session/stop` | — | Stop the CODESYS process and close the session. |
| POST | `/api/v1/session/restart` | — | Stop then restart the CODESYS process. |
| GET  | `/api/v1/session/status` | — | Return process and IPC liveness state. |

### Project

| Method | Path | Body params | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/project/create` | `path` (required) | Create a new project at the given path and open it. |
| POST | `/api/v1/project/open` | `path` (required) | Open an existing `.project` file. |
| POST | `/api/v1/project/save` | — | Save the currently open project. |
| POST | `/api/v1/project/close` | — | Close the currently open project. |
| GET  | `/api/v1/project/list` | — | List projects known to the active session. |
| POST | `/api/v1/project/compile` | — | Build the active project; returns CODESYS message-store counts. |
| POST | `/api/v1/project/import-xml` | `xml_path` (required) | Import a PLCopen XML file into the active project. |

### POU

| Method | Path | Body params | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/pou/create` | `name`, `type`, `language` (all required) | Create a new POU. `type`: `FunctionBlock`/`Function`/`Program`. `language`: `ST`/`FBD`/`LD`/`IL`/`CFC`. |
| POST | `/api/v1/pou/code` | `path` (required), plus at least one of `declaration`, `implementation`, `code` | Set POU declaration and/or implementation text. `path` is the scriptengine tree path, e.g. `Application\MyFB`. Declaration must omit the POU header line. |
| GET  | `/api/v1/pou/list` | — | List POUs in the active project. |

### Script

| Method | Path | Body params | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/script/execute` | `script` (required) | Execute arbitrary IronPython 2.7 code inside CODESYS. Use with caution. |

### System

| Method | Path | Body params | Description |
| --- | --- | --- | --- |
| GET | `/api/v1/system/info` | — | Return server and CODESYS process metadata. |
| GET | `/api/v1/system/logs` | — | Return recent log entries from the server. |

## Deployment as Windows Service
The system can be wrapped as a Windows Service for persistent background operation.
- **Install**: `install.bat` (Run as Admin).
- **Uninstall**: `uninstall.bat` (Run as Admin).
- **Service Logic**: Managed by `windows_service.py`, handles auto-recovery and logging.

## Security
- **API Keys**: Stored in `%APPDATA%\codesys-api\api_keys.json`.
- **Default Key**: `admin` (Use for initial setup/testing).
- **Restriction**: The CLI and Server currently only support `named_pipe` for local IPC.
