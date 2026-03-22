from __future__ import annotations

from pathlib import Path

from codesys_api.cli_entry import build_parser


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_cli_bat_invokes_codesys_cli() -> None:
    content = (REPO_ROOT / "run_cli.bat").read_text(encoding="utf-8")

    assert 'python "%~dp0codesys_cli.py" %*' in content


def test_cli_usage_examples_match_parser() -> None:
    parser = build_parser()
    examples = [
        ["session", "start"],
        ["session", "restart"],
        ["session", "status"],
        ["session", "stop"],
        ["project", "create", "--path", r"C:\work\demo.project"],
        ["project", "open", "--path", r"C:\work\demo.project"],
        ["project", "save"],
        ["project", "close"],
        ["project", "list"],
        ["project", "compile"],
        ["project", "compile", "--clean-build"],
        ["pou", "create", "--name", "MotorController", "--type", "FunctionBlock", "--language", "ST"],
        ["pou", "list"],
        ["pou", "list", "--parent-path", "Application"],
        ["pou", "code", "--path", r"Application\PLC_PRG", "--implementation-file", "plc_prg_impl.txt"],
        [
            "pou",
            "code",
            "--path",
            r"Application\MotorController",
            "--declaration-file",
            "decl.txt",
            "--implementation-file",
            "impl.txt",
        ],
    ]

    usage = (REPO_ROOT / "docs" / "CLI_USAGE.md").read_text(encoding="utf-8")

    for args in examples:
        package_command = "codesys-tools " + " ".join(args)
        repo_command = "python codesys_cli.py " + " ".join(args)
        assert package_command in usage or repo_command in usage
        parsed = parser.parse_args(args)
        assert parsed.resource == args[0]
