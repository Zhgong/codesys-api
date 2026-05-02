# AGENT.md

## Operations Overview

### Diagnostic First
Run diagnostics before session/project operations:

```bash
codesys-tools doctor
```

Automation-safe mode:

```bash
codesys-tools --json doctor
```

Behavior:
- `doctor` is read-only.
- Exit code `0`: no `FAIL` checks.
- Exit code `1`: at least one `FAIL` check.
- `FAIL` lines include a remediation suggestion.

### Output Formats
- CLI human mode: plain text.
- CLI JSON mode: `--json` prints raw result JSON.
- REST mode: JSON response body for every endpoint.
- MCP mode: Structured tool responses for AI agents.

## Architecture & Execution Pipeline (For AI Context)

### The Flow
Every command follows a three-layer execution path:
1.  **Interface Layer** (`src/codesys_api/cli_entry.py` / `http_server.py` / `mcp_server.py`): Entry points for CLI, REST API, and Model Context Protocol.
2.  **Action Layer** (`src/codesys_api/action_layer.py`): The core orchestrator. Handles business logic, state management, and environment validation.
3.  **Engine Layer** (`PERSISTENT_SESSION.py`): Low-level executor running inside CODESYS (IronPython 2.7).

### IPC Communication Mechanism (Named Pipe)
The **Action Layer** and **Engine Layer** communicate via a Windows **Named Pipe**:
- **Transport**: `src/codesys_api/named_pipe_transport.py`.
- **Reliability**: Replaced the legacy file-based transport for higher performance and stability.
- **Bi-directional**: Supports direct command sending and JSON result retrieval.

### MCP Server (AI Integration)
The project includes a built-in MCP server for direct integration with AI tools:
- Entry point: `codesys-tools-mcp`
- Default: SSE transport on `0.0.0.0:8001`.
- Configuration: `CODESYS_API_MCP_PORT`, `CODESYS_API_MCP_HOST`.

### Debugging for AI Agents
1.  **Environment Issues**: Run `codesys-tools doctor`.
2.  **Session Issues**: Check `session status`. If stale, use `session restart`.
3.  **Logic Errors**: Inspect the `error` field in JSON responses.

## CLI Command Hierarchy

```text
codesys-tools [--json] <resource> <operation> [options]

resources:
  doctor
  session  (start | status | restart | stop)
  project  (create | open | save | close | list | compile)
  pou      (create | list | code)
  system   (info | logs)
```

## REST API Reference

### Base URL and Auth
- Base URL: `http://127.0.0.1:8080` (default).
- Header: `Authorization: ApiKey <token>`.

### Key Endpoints (20 Total)

| Category | Endpoints |
| --- | --- |
| **Session** | `/api/v1/session/start`, `/stop`, `/restart`, `/status` |
| **Project** | `/api/v1/project/create`, `/open`, `/save`, `/close`, `/list`, `/compile` |
| **POU** | `/api/v1/pou/create`, `/list`, `/code` (GET/POST) |
| **Script** | `/api/v1/script/execute` |
| **System** | `/api/v1/system/info`, `/logs`, `/health` |

## Error Handling and Resilience

### Success Contract
- Inspect `body.success` (boolean) and `error` (string).
- HTTP 500 typically indicates an Engine Layer exception inside CODESYS.

## AI Prompt Cheatsheet
- "Run `codesys-tools doctor --json` and fix any FAILs."
- "Start session and compile project `C:\path\to\proj`."
- "Execute this raw snippet via script/execute."

## LLM Wiki Gardener Schema
Documentation is split into `docs/raw/` (sources) and `docs/wiki/` (AI-maintained synthesis). Use `docs/wiki/index.md` as your primary knowledge map.
