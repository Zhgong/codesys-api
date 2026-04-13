# System Architecture

The Codesys-API provides a persistent RESTful wrapper around the CODESYS automation software, enabling headless control and automation via standard web protocols.

## Execution Pipeline
Every request flows through a three-layer decoupled architecture:

1. **Interface Layer (Host/Python 3)**:
   - **CLI**: `codesys_api.cli_entry` parses user commands.
   - **REST API**: `HTTP_SERVER.py` (BaseHTTPServer) handles incoming HTTP requests.
2. **Action Layer (Host/Python 3)**:
   - Orchestrates high-level logic and state.
   - Performs environment validation via `codesys-tools doctor`.
   - Manages the `CodesysProcessManager` to ensure the IDE is running.
3. **Engine Layer (Guest/IronPython 2.7)**:
   - `PERSISTENT_SESSION.py` runs inside the CODESYS process.
   - Interacts directly with the `scriptengine` COM API.
   - Polls for requests and executes them within the IDE's main thread context.

## IPC Mechanism (File-Based)
Communication between Host (Python 3) and Guest (IronPython 2.7) is asynchronous and file-based to ensure compatibility across runtime boundaries:

- **Requests**: Host writes JSON files to `requests/`.
- **Results**: Guest processes requests and writes JSON results to `results/`.
- **Synchronization**: The Host waits for result files with a configurable timeout.

## Boundary Contract (The Golden Rule)
To maintain stability, the system follows a strict "Boundary Contract":
- **Approved Primitives**: `projects.open()`, `projects.create()`, and raw snippet execution via `/api/v1/script/execute`.
- **Prohibited Primitives**: Direct opening of project templates (e.g., `Standard.project`) is rejected due to multi-threading constraints in the CODESYS IDE.
- **Validation**: New features must be proven via raw probes (`scripts/manual/`) before being integrated into the `Action Layer`.

## Key Components
- **CodesysProcessManager**: Handles lifecycle (start/stop/restart) of the CODESYS process.
- **ScriptExecutionEngine**: Generates and executes IronPython snippets.
- **ApiKeyManager**: Validates authentication tokens stored in `api_keys.json`.
- **MonitoringSystem**: Tracks CPU/Memory usage and API performance metrics.

## Component Diagram (Mermaid)
```mermaid
graph TD
    User([User/Client]) -->|HTTP/CLI| Interface[Interface Layer]
    Interface -->|Logic| Action[Action Layer]
    Action -->|Write Request| ReqDir[(/requests)]
    ReqDir -->|Poll| Engine[Persistent Session - IronPython]
    Engine -->|COM API| IDE[CODESYS IDE]
    IDE -->|Status| Engine
    Engine -->|Write Result| ResDir[(/results)]
    ResDir -->|Read Result| Action
    Action -->|Format| Interface
    Interface -->|Response| User
```
