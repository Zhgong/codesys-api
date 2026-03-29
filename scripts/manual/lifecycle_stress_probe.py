from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from codesys_api.codesys_process import CodesysProcessManager, ProcessManagerConfig
from codesys_api.named_pipe_transport import NamedPipeScriptTransport
from codesys_api.script_executor import ScriptExecutor


LOCAL_ENV_FILE = REPO_ROOT / ".env.real-codesys.local"
PERSISTENT_SCRIPT = REPO_ROOT / "src" / "codesys_api" / "assets" / "PERSISTENT_SESSION.py"
SCRIPT_LIB_DIR = REPO_ROOT / "src" / "codesys_api" / "assets" / "ScriptLib"
REQUIRED_ENV_VARS = (
    "CODESYS_API_CODESYS_PATH",
    "CODESYS_API_CODESYS_PROFILE",
)
DEFAULT_CYCLES = 12

# Minimal IronPython 2.7 script: round-trips through the pipe without touching projects.
HEALTH_CHECK_SCRIPT = "result = {'success': True, 'message': 'health-check'}\n"


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError("Invalid env line without '=': {0}".format(stripped))
        name, value = stripped.split("=", 1)
        env[name] = value
    return env


def build_logger() -> logging.Logger:
    logger = logging.getLogger("lifecycle_stress_probe")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def run_cycle(
    cycle: int,
    process_manager: CodesysProcessManager,
    script_executor: ScriptExecutor,
    logger: logging.Logger,
) -> tuple[bool, str]:
    t0 = time.monotonic()
    print(f"\n[lifecycle-stress] cycle {cycle}: starting CODESYS", flush=True)

    ok = process_manager.start()
    t1 = time.monotonic()
    if not ok:
        msg = f"start() returned False after {t1 - t0:.1f}s"
        print(f"[lifecycle-stress] cycle {cycle}: FAILED - {msg}", flush=True)
        return False, msg

    print(f"[lifecycle-stress] cycle {cycle}: CODESYS up ({t1 - t0:.1f}s), running health-check", flush=True)
    result = script_executor.execute_script(HEALTH_CHECK_SCRIPT, timeout=30)
    t2 = time.monotonic()

    print(f"[lifecycle-stress] cycle {cycle}: stopping CODESYS", flush=True)
    process_manager.stop()
    t3 = time.monotonic()

    if not result.get("success"):
        msg = f"script failed: {result} (start={t1 - t0:.1f}s, script={t2 - t1:.1f}s)"
        print(f"[lifecycle-stress] cycle {cycle}: FAILED - {msg}", flush=True)
        return False, msg

    print(
        f"[lifecycle-stress] cycle {cycle}: OK  "
        f"start={t1 - t0:.1f}s  script={t2 - t1:.1f}s  stop={t3 - t2:.1f}s",
        flush=True,
    )
    return True, ""


def run_cycle_with_project_ops(
    cycle: int,
    actions_service: object,
) -> tuple[bool, str]:
    """Each cycle mirrors the HTTP test: session/start + project/create + pou/code + session/stop."""
    from codesys_api.action_layer import ActionRequest, ActionType

    t0 = time.monotonic()
    print(f"\n[lifecycle-stress] cycle {cycle}: session/start", flush=True)

    result = actions_service.execute(  # type: ignore[attr-defined]
        ActionRequest(action=ActionType.SESSION_START, params={}, request_id=str(uuid.uuid4()))
    )
    t1 = time.monotonic()
    if not result.body.get("success"):
        return False, f"session/start failed ({t1 - t0:.1f}s): {result.body}"

    project_path = str(
        Path(tempfile.gettempdir())
        / f"lifecycle_probe_{cycle}_{uuid.uuid4().hex[:8]}.project"
    )
    result = actions_service.execute(  # type: ignore[attr-defined]
        ActionRequest(
            action=ActionType.PROJECT_CREATE,
            params={"path": project_path},
            request_id=str(uuid.uuid4()),
        )
    )
    t2 = time.monotonic()
    if not result.body.get("success"):
        return False, f"project/create failed ({t2 - t1:.1f}s): {result.body}"

    result = actions_service.execute(  # type: ignore[attr-defined]
        ActionRequest(
            action=ActionType.POU_CODE,
            params={
                "path": "Application/PLC_PRG",
                "implementation": f"x_{cycle} : INT := {cycle};",
            },
            request_id=str(uuid.uuid4()),
        )
    )
    t3 = time.monotonic()
    if not result.body.get("success"):
        return False, f"pou/code failed ({t3 - t2:.1f}s): {result.body}"

    print(f"[lifecycle-stress] cycle {cycle}: session/stop", flush=True)
    result = actions_service.execute(  # type: ignore[attr-defined]
        ActionRequest(action=ActionType.SESSION_STOP, params={}, request_id=str(uuid.uuid4()))
    )
    t4 = time.monotonic()
    if not result.body.get("success"):
        return False, f"session/stop failed ({t4 - t3:.1f}s): {result.body}"

    print(
        f"[lifecycle-stress] cycle {cycle}: OK  "
        f"start={t1 - t0:.1f}s  create={t2 - t1:.1f}s  "
        f"pou={t3 - t2:.1f}s  stop={t4 - t3:.1f}s",
        flush=True,
    )
    return True, ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Lifecycle stress probe: start -> ops -> stop, N times.\n"
            "Bypasses HTTP server and pytest entirely.\n\n"
            "Modes:\n"
            "  (default)      health-check only (1 pipe op/cycle)\n"
            "  --project-ops  session/start + project/create + pou/code + session/stop\n"
            "                 (mirrors HTTP test scenario, adds ActionService layer)\n\n"
            "Interpretation:\n"
            "  Fails -> fault is at or below the tested layer\n"
            "  Passes -> fault is above the tested layer (closer to HTTP)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=DEFAULT_CYCLES,
        help=f"Number of start/stop cycles to run (default: {DEFAULT_CYCLES})",
    )
    parser.add_argument(
        "--no-ui",
        dest="no_ui",
        action="store_true",
        default=None,
        help="Force --noUI mode (overrides env).",
    )
    parser.add_argument(
        "--ui",
        dest="no_ui",
        action="store_false",
        help="Force UI mode, no --noUI flag (overrides env). Matches HTTP test conditions.",
    )
    parser.add_argument(
        "--project-ops",
        dest="project_ops",
        action="store_true",
        default=False,
        help=(
            "Each cycle: session/start + project/create + pou/code + session/stop. "
            "Uses ActionService directly (same as HTTP server). "
            "Default: health-check only (process manager + pipe, no ActionService)."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not LOCAL_ENV_FILE.exists():
        print(f"Missing local env file: {LOCAL_ENV_FILE}", file=sys.stderr)
        return 2

    file_env = load_env_file(LOCAL_ENV_FILE)
    merged_env = dict(os.environ)
    merged_env.update(file_env)

    missing = [v for v in REQUIRED_ENV_VARS if not merged_env.get(v)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    logger = build_logger()
    pipe_name = f"lifecycle_stress_{uuid.uuid4().hex[:8]}"

    # _build_launch_env() uses os.environ.copy() — inject pipe name so CODESYS inherits it.
    os.environ["CODESYS_API_PIPE_NAME"] = pipe_name
    os.environ["CODESYS_API_TRANSPORT"] = "named_pipe"

    config = ProcessManagerConfig(
        codesys_path=Path(merged_env["CODESYS_API_CODESYS_PATH"]),
        script_path=PERSISTENT_SCRIPT,
        script_lib_dir=SCRIPT_LIB_DIR,
        profile_name=merged_env.get("CODESYS_API_CODESYS_PROFILE"),
        profile_path=Path(merged_env["CODESYS_API_CODESYS_PROFILE_PATH"])
        if merged_env.get("CODESYS_API_CODESYS_PROFILE_PATH")
        else None,
        no_ui=args.no_ui if args.no_ui is not None else merged_env.get("CODESYS_API_CODESYS_NO_UI", "0") == "1",
        transport_name="named_pipe",
        pipe_name=pipe_name,
    )
    process_manager = CodesysProcessManager(config, logger=logger)
    transport = NamedPipeScriptTransport(pipe_name=pipe_name)
    script_executor = ScriptExecutor(transport, logger=logger)

    actions_service = None
    if args.project_ops:
        from codesys_api.action_layer import ActionService
        from codesys_api.ironpython_script_engine import IronPythonScriptEngineAdapter
        engine_adapter = IronPythonScriptEngineAdapter(
            codesys_path=config.codesys_path, logger=logger
        )
        actions_service = ActionService(
            process_manager=process_manager,
            script_executor=script_executor,
            engine_adapter=engine_adapter,
            logger=logger,
            now_fn=time.time,
            script_dir=REPO_ROOT / "src" / "codesys_api" / "assets",
        )

    mode_label = "project-ops (ActionService layer)" if args.project_ops else "health-check only (pipe layer)"
    print(f"\nLifecycle stress probe: {args.cycles} cycles", flush=True)
    print(f"Mode: {mode_label}", flush=True)
    print(f"Pipe name: {pipe_name}", flush=True)
    print(f"CODESYS: {config.codesys_path}", flush=True)
    print(f"Profile: {config.profile_name}", flush=True)
    print(f"no_ui: {config.no_ui}\n", flush=True)

    failures: list[tuple[int, str]] = []
    for cycle in range(args.cycles):
        if args.project_ops:
            assert actions_service is not None
            ok, msg = run_cycle_with_project_ops(cycle, actions_service)
        else:
            ok, msg = run_cycle(cycle, process_manager, script_executor, logger)
        if not ok:
            failures.append((cycle, msg))
            print(f"\nFirst failure at cycle {cycle} - stopping probe.", flush=True)
            break

    print(f"\n{'=' * 60}", flush=True)
    if not failures:
        print(f"PASSED all {args.cycles} lifecycle cycles.", flush=True)
        if args.project_ops:
            print(
                "ActionService layer is clean. "
                "Fault is above ActionService -> in HTTP server (CodesysApiHandler / BaseHTTPRequestHandler).",
                flush=True,
            )
        else:
            print(
                "Process manager + pipe layer is clean. "
                "Fault is above this layer (ActionService or HTTP server).",
                flush=True,
            )
        return 0
    else:
        cycle_num, reason = failures[0]
        print(f"FAILED at cycle {cycle_num}: {reason}", flush=True)
        if args.project_ops:
            print(
                "Fault triggered at or below ActionService layer. "
                "Project operations are involved. Investigate process teardown or CODESYS cleanup.",
                flush=True,
            )
        else:
            print(
                "Fault IS in process management / pipe / Windows resource layer.",
                flush=True,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
