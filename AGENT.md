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

## CLI Command Hierarchy

```text
codesys-tools [--json] <resource> <operation> [options]

resources:
  doctor
  session  (start | status | restart | stop)
  project  (create | open | save | close | list | compile)
  pou      (create | list | code)
```

Examples:

```bash
codesys-tools session start
codesys-tools project create --path C:\work\demo.project
codesys-tools project compile --clean-build
codesys-tools pou create --name MotorController --type FunctionBlock --language ST
codesys-tools pou list --parent-path Application
codesys-tools pou code --path Application\PLC_PRG --implementation-file plc_prg_impl.txt
```

## REST API Reference

### Base URL and Auth
- Base URL: `http://127.0.0.1:8080` (default port `8080`).
- Header: `Authorization: ApiKey <token>`.
- Content type: `application/json`.

### Endpoint to ActionType Mapping

| Method | Path | ActionType |
| --- | --- | --- |
| POST | `/api/v1/session/start` | `session.start` |
| POST | `/api/v1/session/stop` | `session.stop` |
| POST | `/api/v1/session/restart` | `session.restart` |
| GET | `/api/v1/session/status` | `session.status` |
| POST | `/api/v1/project/create` | `project.create` |
| POST | `/api/v1/project/open` | `project.open` |
| POST | `/api/v1/project/save` | `project.save` |
| POST | `/api/v1/project/close` | `project.close` |
| GET | `/api/v1/project/list` | `project.list` |
| POST | `/api/v1/project/compile` | `project.compile` |
| POST | `/api/v1/pou/create` | `pou.create` |
| GET | `/api/v1/pou/list` | `pou.list` |
| POST | `/api/v1/pou/code` | `pou.code` |
| POST | `/api/v1/script/execute` | `script.execute` |
| GET | `/api/v1/system/info` | direct handler (not ActionType) |
| GET | `/api/v1/system/logs` | direct handler (not ActionType) |

Note:
- `doctor` is currently CLI-only (`codesys-tools doctor`), not exposed as a REST endpoint.

### Common JSON Payload Examples

Start session:

```http
POST /api/v1/session/start
Authorization: ApiKey <token>
Content-Type: application/json

{}
```

Compile project:

```http
POST /api/v1/project/compile
Authorization: ApiKey <token>
Content-Type: application/json

{
  "clean_build": true
}
```

Update POU implementation:

```http
POST /api/v1/pou/code
Authorization: ApiKey <token>
Content-Type: application/json

{
  "path": "Application/PLC_PRG",
  "implementation": "PROGRAM PLC_PRG\nVAR\nEND_VAR\n"
}
```

## Error Handling and Resilience

### Success Contract
- Business result is in `body.success` (boolean).
- Do not trust HTTP status code alone; inspect `success` and `error`.

### HTTP Status Usage
- `200`: request handled (can still contain `success: false` in edge cases).
- `400`: invalid/missing parameters.
- `401`: authentication failed.
- `404`: unknown endpoint.
- `500`: runtime or execution failure.
- `501`: action not supported by active engine adapter.

### Runtime Resilience Guidance
- On startup issues:
  1. Run `codesys-tools doctor`.
  2. Check `CODESYS_API_CODESYS_PATH` and dependency checks.
- On transient runtime failures/timeouts:
  1. Query `session status`.
  2. Retry with bounded backoff.
  3. Use `session restart` when pipe/session is stale.
- On compile failures:
  1. Parse `message_counts`.
  2. Treat compile errors as non-retriable until source/config changes.

## AI Prompt Cheatsheet

Use prompts with explicit action, inputs, and output mode:

- "Run `codesys-tools doctor --json`, summarize only FAIL items and concrete fixes."
- "Start a session, create `C:\\work\\demo.project`, compile with clean build, return JSON outputs."
- "List POUs under `Application`, then update `Application/PLC_PRG` implementation from this snippet."
- "When REST call fails, report: endpoint, status code, success flag, error field, and next retry action."
