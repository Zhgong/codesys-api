from __future__ import annotations

import argparse
from collections.abc import Sequence

from .http_server import run_server
from .help_text import SERVER_HELP_DESCRIPTION, build_server_help_epilog


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=SERVER_HELP_DESCRIPTION,
        epilog=build_server_help_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(list(argv) if argv is not None else None)
    run_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
