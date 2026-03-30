from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common


TARGET_PATH = "Application/PLC_PRG"
EXPECTED_IMPLEMENTATION = "MissingVar := TRUE;"


def escape_script_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def build_readback_script(requested_path: str) -> str:
    escaped_path = escape_script_string(requested_path)
    return """
import json
import sys
import traceback

try:
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session"}}
    else:
        project = session.active_project
        raw_path = "{0}"
        normalized_path = raw_path.replace("\\\\", "/")
        windows_path = normalized_path.replace("/", "\\\\")
        target_name = normalized_path.split("/")[-1]
        requested_paths = []
        for candidate in [raw_path, normalized_path, windows_path, target_name]:
            if candidate not in requested_paths:
                requested_paths.append(candidate)
        target = None
        matched_path = None
        resolved_via = None
        application_children = []
        session_created_pous = []
        if hasattr(session, 'created_pous') and session.created_pous:
            try:
                session_created_pous = sorted([str(name) for name in session.created_pous.keys()])
            except Exception:
                session_created_pous = []
            try:
                target = session.created_pous.get(target_name)
            except Exception:
                target = None
            if target is not None:
                matched_path = target_name
                resolved_via = "session.created_pous"
        application = project.find("Application")
        if application is not None and hasattr(application, 'get_children'):
            try:
                for child in application.get_children():
                    if hasattr(child, 'name'):
                        application_children.append(str(child.name))
            except Exception:
                pass

        if target is None:
            for search_term in requested_paths:
                search_result = project.find(search_term)
                if search_result is None:
                    continue
                if hasattr(search_result, 'textual_implementation') or hasattr(search_result, 'textual_declaration'):
                    target = search_result
                    matched_path = search_term
                    resolved_via = "project.find"
                    break
                if hasattr(search_result, '__iter__'):
                    for candidate in search_result:
                        if hasattr(candidate, 'textual_implementation') or hasattr(candidate, 'textual_declaration'):
                            target = candidate
                            matched_path = search_term
                            resolved_via = "project.find"
                            break
                    if target is not None:
                        break

        if target is None:
            result = {{
                "success": False,
                "error": "POU not found: " + raw_path,
                "requested_path": raw_path,
                "requested_paths": requested_paths,
                "session_created_pous": session_created_pous,
                "application_children": application_children,
                "resolved_via": resolved_via
            }}
        else:
            declaration_doc = getattr(target, 'textual_declaration', None)
            implementation_doc = getattr(target, 'textual_implementation', None)
            declaration_text = declaration_doc.text if hasattr(declaration_doc, 'text') else ""
            implementation_text = implementation_doc.text if hasattr(implementation_doc, 'text') else ""
            result = {{
                "success": True,
                "project_path": project.path,
                "requested_path": raw_path,
                "requested_paths": requested_paths,
                "matched_path": matched_path,
                "resolved_via": resolved_via,
                "resolved_name": getattr(target, 'name', target_name),
                "resolved_type": target.__class__.__name__,
                "session_created_pous": session_created_pous,
                "application_children": application_children,
                "implementation_contains_missing_var": "MissingVar" in implementation_text,
                "implementation_preview": implementation_text[:200],
                "declaration_preview": declaration_text[:200]
            }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{"success": False, "error": str(error_value), "traceback": traceback.format_exc()}}
""".format(escaped_path)


def is_expected_roundtrip_response(status_code: int, payload: Mapping[str, object]) -> bool:
    return (
        status_code == 200
        and payload.get("success") is True
        and payload.get("implementation_contains_missing_var") is True
    )


def extract_pou_names(payload: Mapping[str, object]) -> list[str]:
    pous = payload.get("pous")
    if not isinstance(pous, list):
        return []
    names: list[str] = []
    for item in pous:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            names.append(name)
    return names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write invalid PLC_PRG code through HTTP and read it back via script/execute.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--log-lines", type=int, default=80, help="How many filtered server log lines to print")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run real POU roundtrip probe from sandbox identity '{0}'.".format(identity),
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

    try:
        print("Windows identity: {0}".format(identity))
        print("Base URL: {0}".format(base_url))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        project_path = str(Path(tempfile.gettempdir()) / f"codesys_api_roundtrip_probe_{uuid.uuid4().hex}.project")

        started_at = time.perf_counter()
        status_code, payload = common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        common.print_step("session/start", started_at, status_code, payload)

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/project/create",
            method="POST",
            payload={"path": project_path},
            timeout=120,
        )
        common.print_step("project/create", started_at, status_code, payload)

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/pou/list",
            method="GET",
            payload={"parentPath": "Application"},
            timeout=120,
        )
        common.print_step("pou/list (before)", started_at, status_code, payload)
        print("POUs before write: {0}".format(", ".join(extract_pou_names(payload)) or "<none>"))

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/pou/code",
            method="POST",
            payload={"path": TARGET_PATH, "implementation": EXPECTED_IMPLEMENTATION},
            timeout=120,
        )
        common.print_step("pou/code", started_at, status_code, payload)

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/pou/list",
            method="GET",
            payload={"parentPath": "Application"},
            timeout=120,
        )
        common.print_step("pou/list (after)", started_at, status_code, payload)
        print("POUs after write: {0}".format(", ".join(extract_pou_names(payload)) or "<none>"))

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/script/execute",
            method="POST",
            payload={"script": build_readback_script(TARGET_PATH)},
            timeout=120,
        )
        common.print_step("script/execute", started_at, status_code, payload)
        print("Roundtrip response JSON:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        if is_expected_roundtrip_response(status_code, payload):
            return 0

        print("Unexpected readback response; expected PLC_PRG implementation to contain MissingVar.")
        print("Server log excerpt:")
        print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
        return 1
    finally:
        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass
        if server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
