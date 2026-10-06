from __future__ import annotations

import argparse

from rpggen import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rpggen")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("version", help="print the version")
    sub.add_parser("generate", help="generate a Godot project")
    sub.add_parser("analyze", help="analyze an asset pack")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args, _rest = parser.parse_known_args(argv)
    if args.command == "version":
        print(f"rpggen {__version__}")
        return 0
    if args.command in ("generate", "analyze"):
        print(f"rpggen {args.command}: not implemented")
        return 2
    parser.print_help()
    return 2
