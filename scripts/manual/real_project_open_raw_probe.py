from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import real_compile_error_probe as common
from real_project_create_raw_probe import derive_template_path, escape_script_string


def build_open_only_script(project_path: str, step_name: str) -> str:
    escaped_project_path = escape_script_string(project_path)
    escaped_step_name = escape_script_string(step_name)
    return """
import scriptengine
import json
import sys
import traceback

try:
    project_path = "{0}"
    step_name = "{1}"
    if hasattr(session, 'active_project') and session.active_project is not None:
        try:
            if hasattr(session.active_project, 'close'):
                session.active_project.close()
        except Exception:
            pass
        session.active_project = None

    project = scriptengine.projects.open(project_path)
    if project is None:
        result = {{"success": False, "error": "projects.open returned None", "step": step_name}}
    else:
        session.active_project = project
        top_level_names = []
        if hasattr(project, 'get_children'):
            for child in project.get_children():
                try:
                    if hasattr(child, 'get_name'):
                        top_level_names.append(str(child.get_name(False)))
                    else:
                        top_level_names.append(str(child))
                except Exception:
                    pass
        result = {{
            "success": True,
            "step": step_name,
            "requested_project_path": project_path,
            "actual_project_path": project.path if hasattr(project, 'path') else project_path,
            "project_name": project.name if hasattr(project, 'name') else "",
            "top_level_names": top_level_names,
        }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    result = {{
        "success": False,
        "error": str(error_value),
        "traceback": traceback.format_exc(),
        "step": step_name,
        "requested_project_path": project_path,
    }}
""".format(escaped_project_path, escaped_step_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debug raw scriptengine.projects.open(...) against local CODESYS.",
    )
    parser.add_argument(
        "--mode",
        choices=("template", "existing"),
        required=True,
        help="Whether to open the Standard.project template or an existing saved project.",
    )
    parser.add_argument(
        "--project-path",
        help="Existing .project path to open when --mode existing is used.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to launch HTTP_SERVER.py")
    parser.add_argument("--log-lines", type=int, default=120, help="How many filtered server log lines to print on failure")
    return parser


def resolve_open_target(args: argparse.Namespace, env: dict[str, str]) -> tuple[str, str]:
    if args.mode == "template":
        return derive_template_path(env["CODESYS_API_CODESYS_PATH"]), "open_template_only"

    if not args.project_path:
        raise ValueError("--project-path is required when --mode existing is used")

    project_path = str(Path(args.project_path).expanduser())
    return project_path, "open_existing_project_only"


def print_step_payload(step_name: str, started_at: float, status_code: int, payload: dict[str, object]) -> None:
    elapsed = time.perf_counter() - started_at
    print("[{0:.2f}s] {1}: status={2} success={3}".format(elapsed, step_name, status_code, payload.get("success")))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    identity = common.resolve_windows_identity()
    if common.is_sandbox_identity(identity):
        print(
            "Refusing to run raw project/open probe from sandbox identity '{0}'.".format(identity),
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

    try:
        open_path, step_name = resolve_open_target(args, probe_env)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
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
        print("Mode: {0}".format(args.mode))
        print("Open path: {0}".format(open_path))
        common.wait_for_server(base_url)

        try:
            common.call_json(base_url, "/api/v1/session/stop", method="POST", payload={}, timeout=30)
        except Exception:
            pass

        started_at = time.perf_counter()
        status_code, payload = common.call_json(base_url, "/api/v1/session/start", method="POST", payload={}, timeout=120)
        common.print_step("session/start", started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("session/start failed; stopping.")
            return 1

        started_at = time.perf_counter()
        status_code, payload = common.call_json(
            base_url,
            "/api/v1/script/execute",
            method="POST",
            payload={"script": build_open_only_script(open_path, step_name)},
            timeout=120,
        )
        print_step_payload(step_name, started_at, status_code, payload)
        if not (status_code == 200 and payload.get("success") is True):
            print("Raw project/open probe stopped at step: {0}".format(step_name))
            print("Server log excerpt:")
            print(common.read_log_excerpt(probe_env, max_lines=args.log_lines, started_at=probe_started_at))
            return 1

        print("Raw project/open probe completed successfully.")
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
