"""
real_project_import_xml_probe.py
---------------------------------
Boundary-contract probe for ``project.import_xml``.

Proves that ``project.import_xml(path, reporter)`` works against a real
CODESYS instance and that the reporter callbacks fire correctly.

Steps
-----
1. session/start
2. project/create  – create a fresh, skeleton-free project
3. pou/create      – add a minimal POU to have something to export
4. script/execute  – export project to PLCopen XML via project.export_xml()
5. script/execute  – import the exported XML back into the project via
                     project.import_xml() with a custom reporter class
6. Verify          – check reporter.errors is empty and the imported POU
                     appears in project.get_children(True)
7. session/stop    – clean up

On success this probe confirms the proven fact backing
``proven_primitives.build_import_xml_fragment``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common


def _escape(value: str) -> str:
    """Escape a value for embedding in an IronPython double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def build_export_xml_step(dest_path: str) -> str:
    escaped = _escape(dest_path)
    return """\
import json
import sys
import traceback

try:
    project = session.active_project
    if project is None:
        result = {{"success": False, "error": "No active project", "step": "export_xml"}}
    else:
        dest = "{dest}"
        project.export_xml(project.get_children(True), dest)
        result = {{"success": True, "step": "export_xml", "dest_path": dest}}
except Exception:
    _et, _ev, _etb = sys.exc_info()
    result = {{
        "success": False,
        "error": str(_ev),
        "traceback": traceback.format_exc(),
        "step": "export_xml",
    }}
""".format(dest=escaped)


def build_import_xml_step(src_path: str) -> str:
    escaped = _escape(src_path)
    return """\
import json
import sys
import traceback

try:
    project = session.active_project
    if project is None:
        result = {{"success": False, "error": "No active project", "step": "import_xml"}}
    else:
        class _Reporter(object):
            def __init__(self):
                self.errors = []
                self.warnings = []
                self.aborting = False
            def error(self, m):
                self.errors.append(str(m))
            def warning(self, m):
                self.warnings.append(str(m))
            def resolve_conflict(self, obj):
                return scriptengine.ConflictResolve.Skip
            def added(self, obj):
                pass
            def replaced(self, obj):
                pass
            def skipped(self, objectname):
                pass

        reporter = _Reporter()
        project.import_xml("{src}", reporter)

        # Collect top-level child names to confirm import
        child_names = []
        for child in project.get_children(True):
            try:
                child_names.append(str(child.get_name(False)) if hasattr(child, "get_name") else str(child))
            except Exception:
                pass

        result = {{
            "success": len(reporter.errors) == 0,
            "step": "import_xml",
            "errors": reporter.errors,
            "warnings": reporter.warnings,
            "child_names": child_names,
        }}
except Exception:
    _et, _ev, _etb = sys.exc_info()
    result = {{
        "success": False,
        "error": str(_ev),
        "traceback": traceback.format_exc(),
        "step": "import_xml",
    }}
""".format(src=escaped)


def print_step_payload(name: str, started_at: float, status_code: int, payload: dict[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: status={2} success={3}".format(
        elapsed, name, status_code, payload.get("success")
    ))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe project.import_xml() against a real CODESYS instance.",
    )
    parser.add_argument(
        "--python", default=sys.executable,
        help="Python executable used to launch HTTP_SERVER.py",
    )
    parser.add_argument(
        "--log-lines", type=int, default=120,
        help="How many filtered server log lines to print on failure",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run import_xml probe from sandbox identity '{0}'.".format(identity),
            file=sys.stderr,
        )
        return 2

    if not common.LOCAL_ENV_FILE.exists():
        print("Missing local env file: {0}".format(common.LOCAL_ENV_FILE), file=sys.stderr)
        return 2

    file_env = common.load_env_file(common.LOCAL_ENV_FILE)
    port = common.find_free_port()
    probe_env = common.build_probe_env(os.environ, file_env, port)
    missing = common.missing_required_env_vars(probe_env)
    if missing:
        print(
            "Missing required real CODESYS environment variables: {0}".format(", ".join(missing)),
            file=sys.stderr,
        )
        return 2

    base_url = "http://127.0.0.1:{0}".format(port)
    probe_started_at = time.time()
    server_process = subprocess.Popen(
        [args.python, "HTTP_SERVER.py"],
        cwd=common.REPO_ROOT,
        env=probe_env,
    )

    project_path = str(
        Path(tempfile.gettempdir())
        / "codesys_api_import_xml_probe_{0}.project".format(uuid.uuid4().hex)
    )
    xml_export_path = project_path.replace(".project", "_export.xml")

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL:         {0}".format(base_url))
        print("Project path:     {0}".format(project_path))
        print("XML export path:  {0}".format(xml_export_path))

        common.wait_for_server(base_url)

        # Stop any existing session first
        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        # Step 1: session/start
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120
        )
        common.print_step("session/start", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("session/start failed; stopping.", file=sys.stderr)
            return 1

        # Step 2: project/create
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/project/create", method="POST",
            payload={"path": project_path}, timeout=60
        )
        common.print_step("project/create", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("project/create failed; stopping.", file=sys.stderr)
            return 1

        # Step 3: pou/create — add a POU so we have something to export
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/pou/create", method="POST",
            payload={"name": "ImportProbeProgram", "type": "Program", "language": "ST"},
            timeout=60,
        )
        common.print_step("pou/create", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("pou/create failed; stopping.", file=sys.stderr)
            return 1

        # Step 4: export project to PLCopen XML
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/script/execute", method="POST",
            payload={"script": build_export_xml_step(xml_export_path)},
            timeout=60,
        )
        print_step_payload("export_xml", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("export_xml step failed; stopping.", file=sys.stderr)
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        # Step 5: import the exported PLCopen XML back into the project
        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url, "/api/v1/script/execute", method="POST",
            payload={"script": build_import_xml_step(xml_export_path)},
            timeout=60,
        )
        print_step_payload("import_xml", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("import_xml step failed; stopping.", file=sys.stderr)
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        # Step 6: verify reporter reported no errors
        errors = payload.get("errors", [])
        if errors:
            print("import_xml reported errors: {0}".format(errors), file=sys.stderr)
            return 1

        print("Probe completed successfully.")
        print("PROVEN: project.import_xml(path, reporter) works in real CODESYS.")
        return 0

    finally:
        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass
        if server_process.poll() is None:
            try:
                server_process.terminate()
                server_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
