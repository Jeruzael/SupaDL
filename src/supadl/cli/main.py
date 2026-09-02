"""Minimal command-line interface for the M0 foundation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from supadl import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser without performing application side effects."""
    parser = argparse.ArgumentParser(
        prog="supadl",
        description="SupaDL download manager (M0 foundation)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and return a process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    parser.parse_args(arguments)
    if not arguments:
        parser.print_help()
    return 0


def entrypoint() -> None:
    """Console-script adapter."""
    raise SystemExit(main())
