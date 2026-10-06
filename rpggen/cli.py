from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from rpggen import __version__
from rpggen.errors import Severity


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rpggen")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("version", help="print the version")
    gen = sub.add_parser("generate", help="generate a Godot project")
    gen.add_argument("--config", type=Path, help="generator_config.json")
    gen.add_argument("--pack", type=Path, help="asset pack folder (creates a default config)")
    gen.add_argument("--name", help="project name for --pack")
    gen.add_argument("--target", type=Path, help="output folder")
    gen.add_argument("--godot", type=Path, help="Godot 4.7.2 executable")
    gen.add_argument("--verbose", action="store_true")
    sub.add_parser("analyze", help="analyze an asset pack")
    return parser


def _resolve_godot(arg: Path | None) -> Path | None:
    if arg is not None:
        return arg
    env = os.environ.get("RPGGEN_GODOT")
    if env:
        return Path(env)
    from rpggen.core import godot

    found = godot.auto_find_godot()
    return found[0] if found else None


def _generate(args: argparse.Namespace) -> int:
    from rpggen import logging_setup
    from rpggen.core import config as config_mod
    from rpggen.core import orchestrator

    if args.target is None or (args.config is None and args.pack is None):
        print("rpggen generate: --target and one of --config / --pack are required")
        return 2
    exe = _resolve_godot(args.godot)
    if exe is None:
        print("rpggen generate: Godot not found; pass --godot or set RPGGEN_GODOT")
        return 2
    logging_setup.configure(Path(tempfile.gettempdir()) / "rpggen_cli_logs", args.verbose)
    with tempfile.TemporaryDirectory(prefix="rpggen_cfg_") as tmp:
        cfg_path = args.config
        if cfg_path is None:
            name = args.name or args.pack.name
            cfg = orchestrator.default_config_for_pack(args.pack, name)
            cfg_path = Path(tmp) / "generator_config.json"
            config_mod.save(cfg, cfg_path)
        cb = orchestrator.Callbacks(on_log=print)
        result = orchestrator.run(cfg_path, args.target, exe, cb)
    for issue in result.issues:
        print(f"{issue.severity.value.upper():7} {issue.code}: {issue.message}")
        if issue.severity is Severity.ERROR:
            print(f"        fix: {issue.fix}")
    if result.ok:
        print(f"OK: project generated in {result.target}")
        return 0
    print("FAILED: generation did not succeed")
    if result.failed_staging:
        print(f"        kept for inspection: {result.failed_staging}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args, _rest = parser.parse_known_args(argv)
    if args.command == "version":
        print(f"rpggen {__version__}")
        return 0
    if args.command == "generate":
        return _generate(args)
    if args.command == "analyze":
        print("rpggen analyze: not implemented")
        return 2
    parser.print_help()
    return 2
