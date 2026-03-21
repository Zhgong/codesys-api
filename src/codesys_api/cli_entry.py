from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, TextIO, cast

from .action_layer import ActionRequest, ActionResult, ActionType
from .app_runtime import build_app_runtime
from .server_config import load_server_config


logger = logging.getLogger("codesys_api_cli")


class ActionServiceLike(Protocol):
    def execute(self, request: ActionRequest) -> ActionResult: ...


def _build_usage_examples() -> str:
    return (
        "Examples:\n"
        "  codesys session start\n"
        "  codesys project create --path C:\\work\\demo.project\n"
        "  codesys pou create --name MotorController --type FunctionBlock --language ST\n"
        "  codesys project compile --clean-build\n"
        "  codesys --json session status\n\n"
        "Notes:\n"
        "  Transport: named_pipe only\n"
        "  Default output: human-readable text\n"
        "  Structured output: --json\n"
        "  Exit codes: 0=success, 1=business/runtime failure, 2=setup/input error"
    )


def _build_session_help_examples() -> str:
    return (
        "Examples:\n"
        "  codesys session start\n"
        "  codesys session status\n"
        "  codesys session restart\n"
        "  codesys session stop"
    )


def _build_project_help_examples() -> str:
    return (
        "Examples:\n"
        "  codesys project create --path C:\\work\\demo.project\n"
        "  codesys project save\n"
        "  codesys project compile --clean-build\n"
        "  codesys project close"
    )


def _build_pou_help_examples() -> str:
    return (
        "Examples:\n"
        "  codesys pou create --name MotorController --type FunctionBlock --language ST\n"
        "  codesys pou list --parent-path Application\n"
        "  codesys pou code --path Application\\PLC_PRG --implementation-file plc_prg_impl.txt"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="codesys-tools command line interface (named_pipe only)",
        epilog=_build_usage_examples(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output structured JSON")
    subparsers = parser.add_subparsers(dest="resource", required=True)

    session_parser = subparsers.add_parser(
        "session",
        help="Session operations",
        description="Manage the local CODESYS session.",
        epilog=_build_session_help_examples(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    session_subparsers = session_parser.add_subparsers(dest="operation", required=True)
    session_subparsers.add_parser("start", help="Start the session")
    session_subparsers.add_parser("restart", help="Restart the session")
    session_subparsers.add_parser("status", help="Show session status")
    session_subparsers.add_parser("stop", help="Stop the session")

    project_parser = subparsers.add_parser(
        "project",
        help="Project operations",
        description="Create, open, save, close, list, and compile projects.",
        epilog=_build_project_help_examples(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    project_subparsers = project_parser.add_subparsers(dest="operation", required=True)
    project_create = project_subparsers.add_parser("create", help="Create a project")
    project_create.add_argument("--path", required=True)
    project_open = project_subparsers.add_parser("open", help="Open a project")
    project_open.add_argument("--path", required=True)
    project_subparsers.add_parser("save", help="Save the active project")
    project_subparsers.add_parser("close", help="Close the active project")
    project_subparsers.add_parser("list", help="List recent projects")
    project_compile = project_subparsers.add_parser("compile", help="Compile the active project")
    project_compile.add_argument("--clean-build", action="store_true", default=False)

    pou_parser = subparsers.add_parser(
        "pou",
        help="POU operations",
        description="Create POUs, list them, and update their code.",
        epilog=_build_pou_help_examples(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pou_subparsers = pou_parser.add_subparsers(dest="operation", required=True)
    pou_create = pou_subparsers.add_parser("create", help="Create a POU")
    pou_create.add_argument("--name", required=True)
    pou_create.add_argument("--type", required=True)
    pou_create.add_argument("--language", required=True)
    pou_list = pou_subparsers.add_parser("list", help="List POUs")
    pou_list.add_argument("--parent-path", default="Application")
    pou_code = pou_subparsers.add_parser("code", help="Set POU code")
    pou_code.add_argument("--path", required=True)
    pou_code.add_argument("--declaration-file")
    pou_code.add_argument("--implementation-file")

    return parser


def _validate_runtime_configuration(config: object) -> str | None:
    transport_name = getattr(config, "transport_name", None)
    transport_is_supported = getattr(config, "transport_is_supported", False)
    if transport_name and not transport_is_supported:
        return (
            "Unsupported transport '{0}'. The CLI currently supports named_pipe only."
        ).format(transport_name)

    profile_name = getattr(config, "codesys_profile_name", None)
    if profile_name is None:
        return (
            "CODESYS profile is not configured. Set CODESYS_API_CODESYS_PROFILE or "
            "CODESYS_API_CODESYS_PROFILE_PATH."
        )

    profile_path = getattr(config, "codesys_profile_path", None)
    if isinstance(profile_path, Path) and not profile_path.exists():
        return "CODESYS profile file not found: {0}".format(profile_path)

    codesys_path = getattr(config, "codesys_path", None)
    if isinstance(codesys_path, Path) and not codesys_path.exists():
        return "CODESYS executable not found: {0}".format(codesys_path)

    return None


def _read_optional_file(file_path: str | None) -> str | None:
    if not file_path:
        return None
    return Path(file_path).read_text(encoding="utf-8")


def _build_action_request(args: argparse.Namespace) -> ActionRequest:
    if args.resource == "session":
        action = {
            "start": ActionType.SESSION_START,
            "restart": ActionType.SESSION_RESTART,
            "status": ActionType.SESSION_STATUS,
            "stop": ActionType.SESSION_STOP,
        }[args.operation]
        return ActionRequest(action=action, params={})

    if args.resource == "project":
        if args.operation == "create":
            return ActionRequest(action=ActionType.PROJECT_CREATE, params={"path": args.path})
        if args.operation == "open":
            return ActionRequest(action=ActionType.PROJECT_OPEN, params={"path": args.path})
        if args.operation == "save":
            return ActionRequest(action=ActionType.PROJECT_SAVE, params={})
        if args.operation == "close":
            return ActionRequest(action=ActionType.PROJECT_CLOSE, params={})
        if args.operation == "list":
            return ActionRequest(action=ActionType.PROJECT_LIST, params={})
        return ActionRequest(
            action=ActionType.PROJECT_COMPILE,
            params={"clean_build": bool(args.clean_build)},
        )

    if args.operation == "create":
        return ActionRequest(
            action=ActionType.POU_CREATE,
            params={"name": args.name, "type": args.type, "language": args.language},
        )
    if args.operation == "list":
        return ActionRequest(action=ActionType.POU_LIST, params={"parentPath": args.parent_path})

    declaration = _read_optional_file(args.declaration_file)
    implementation = _read_optional_file(args.implementation_file)
    params: dict[str, object] = {"path": args.path}
    if declaration is not None:
        params["declaration"] = declaration
    if implementation is not None:
        params["implementation"] = implementation
    return ActionRequest(action=ActionType.POU_CODE, params=params)


def _format_human_result(action: ActionType, body: Mapping[str, object]) -> str:
    success = body.get("success") is True
    if action == ActionType.SESSION_STATUS:
        status = body.get("status")
        if isinstance(status, Mapping):
            process = status.get("process")
            session = status.get("session")
            if isinstance(process, Mapping) and isinstance(session, Mapping):
                return (
                    "Process: {state} | Session active: {active} | Project open: {project_open}".format(
                        state=process.get("state", "unknown"),
                        active=session.get("session_active", False),
                        project_open=session.get("project_open", False),
                    )
                )
        return "Session status unavailable"

    if action == ActionType.PROJECT_COMPILE:
        counts = body.get("message_counts")
        if isinstance(counts, Mapping):
            summary = "errors={0}, warnings={1}, infos={2}".format(
                counts.get("errors", 0),
                counts.get("warnings", 0),
                counts.get("infos", 0),
            )
        else:
            summary = "message counts unavailable"
        if success:
            return "Compile succeeded ({0})".format(summary)
        return "Compile failed: {0} ({1})".format(body.get("error", "unknown error"), summary)

    if action == ActionType.PROJECT_LIST:
        projects = body.get("projects")
        if isinstance(projects, list):
            project_lines: list[str] = []
            for project in projects:
                if isinstance(project, Mapping):
                    path = project.get("path")
                    name = project.get("name")
                    if isinstance(path, str) and path:
                        project_lines.append(path)
                    elif isinstance(name, str) and name:
                        project_lines.append(name)
            return "\n".join(project_lines) if project_lines else "No recent projects"
        return "Project list unavailable"

    if action == ActionType.POU_LIST:
        pous = body.get("pous")
        container = body.get("container")
        if isinstance(pous, list):
            pou_lines: list[str] = []
            for pou in pous:
                if not isinstance(pou, Mapping):
                    continue
                name = pou.get("name")
                pou_type = pou.get("type")
                language = pou.get("language")
                if not isinstance(name, str) or not name:
                    continue
                line = name
                if isinstance(pou_type, str) and pou_type:
                    line += " [{0}]".format(pou_type)
                if isinstance(language, str) and language and language != "Unknown":
                    line += " <{0}>".format(language)
                pou_lines.append(line)
            if pou_lines:
                return "\n".join(pou_lines)
            location = container if isinstance(container, str) and container else "Application"
            return "No POUs found under {0}".format(location)
        return "POU list unavailable"

    if success and isinstance(body.get("message"), str):
        return str(body["message"])

    if success and isinstance(body.get("project"), Mapping):
        project = cast(Mapping[str, object], body["project"])
        return "Project ready: {0}".format(project.get("path", project.get("name", "unknown project")))

    if success and isinstance(body.get("pou"), Mapping):
        pou = cast(Mapping[str, object], body["pou"])
        return "POU ready: {0}".format(pou.get("name", "unknown"))

    error_message = body.get("error")
    if isinstance(error_message, str) and error_message:
        return error_message
    message = body.get("message")
    if isinstance(message, str) and message:
        return message
    return "Action failed"


def run_cli(
    argv: Sequence[str],
    *,
    action_service: ActionServiceLike | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    base_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            args = parser.parse_args(list(argv))
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    if args.resource == "pou" and args.operation == "code":
        if not args.declaration_file and not args.implementation_file:
            print(
                "At least one of --declaration-file or --implementation-file is required",
                file=stderr,
            )
            return 2

    try:
        request = _build_action_request(args)
    except FileNotFoundError as exc:
        print(str(exc), file=stderr)
        return 2

    runtime_service = action_service
    if runtime_service is None:
        resolved_base_dir = base_dir or Path.cwd()
        resolved_env = env or os.environ
        config = load_server_config(resolved_base_dir, resolved_env)
        config_error = _validate_runtime_configuration(config)
        if config_error is not None:
            print(config_error, file=stderr)
            return 2
        try:
            runtime = build_app_runtime(config, logger=logger)
        except ValueError as exc:
            print(str(exc), file=stderr)
            return 2
        runtime_service = cast(ActionServiceLike, runtime.actions_service)

    result = runtime_service.execute(request)
    body = result.body

    if args.as_json:
        print(json.dumps(body), file=stdout)
    else:
        success_value = body.get("success")
        success = success_value if isinstance(success_value, bool) else False
        target = stdout if result.status_code < 400 and success else stderr
        print(_format_human_result(request.action, body), file=target)

    success_value = body.get("success")
    success = success_value if isinstance(success_value, bool) else False
    if result.status_code >= 400 or not success:
        return 1
    return 0


def main() -> int:
    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
