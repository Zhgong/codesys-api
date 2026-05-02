# Maintenance Log

## 2026-04-20
- **LINT**: Fixed broken links and outdated paths in `Troubleshooting.md`. Updated `index.md` to reflect `docs/raw` removal and updated sync date. Synchronized endpoint counts in `Release_Management.md`.
- **LINT**: Synchronized REST API endpoint count from 18 to 20 across `AGENT.md` and `Operations.md` based on `http_server.py` implementation (added `import-xml-content` and `import-xml-b64`).
- **UPDATE**: Updated Mermaid diagram in `Architecture.md` to reflect Named Pipe transport.
- **CLEANUP**: Removed 23 legacy files from `docs/raw/` and 4 temporary files from `docs/archive/`.
- **FEAT**: Created `Release_Management.md` in Wiki.

## 2026-04-15
- **FIX**: Updated `scripts/check_public_release.py` to reflect docs restructure — `PUBLIC_RELEASE_DOC` now points to `docs/archive/PUBLIC_RELEASE.md`, `INSTALLATION_GUIDE` to `docs/raw/INSTALLATION_GUIDE.md`.
- **UPDATE**: Expanded REST API reference table in [[Operations]] from 6 to 18 endpoints, grouped by Session / Project / POU / Script / System, with body params and descriptions.
- **FIX**: Corrected IPC mechanism description in [[Architecture]] from file-based to named pipe (file transport was retired).
- **FEAT**: Added MCP server — `src/codesys_api/mcp_server.py`, `MCP_SERVER.py`, `codesys-tools-mcp` entry point, `mcp` dependency. TDD: 19 unit tests in `tests/unit/test_mcp_server.py`. Updated [[Operations]] with MCP server section.
- **FEAT**: MCP server defaults to SSE transport (`0.0.0.0:8001`) for cross-machine access. Configurable via `CODESYS_API_MCP_TRANSPORT/HOST/PORT`. Added `start-mcp.ps1`. Updated [[Operations]] with remote/local config examples and env var table.
- **FIX**: Updated `tests/unit/test_root_layout.py` to filter gitignored files; updated `.gitignore` with probe/test-result/screenshot patterns.

## 2026-04-13
- **INGEST**: Bootstrapped LLM Wiki architecture.
- **INGEST**: Migrated 23 legacy documents to `docs/raw/`.
- **INGEST**: Synthesized `Architecture.md`, `Operations.md`, and `Troubleshooting.md` from raw documents.
- **SCHEMA**: Updated `AGENT.md` with Gardener Schema.
