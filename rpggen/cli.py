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
    sub.add_parser("gui", help="open the graphical wizard (also the default)")
    gen = sub.add_parser("generate", help="generate a Godot project")
    gen.add_argument("--config", type=Path, help="generator_config.json")
    gen.add_argument("--pack", type=Path, help="asset pack folder (creates a default config)")
    gen.add_argument("--name", help="project name for --pack")
    gen.add_argument("--target", type=Path, help="output folder")
    gen.add_argument("--godot", type=Path, help="Godot 4.7.2 executable")
    gen.add_argument(
        "--placeholder",
        action="append",
        default=[],
        metavar="ROLE",
        help="use a debug placeholder for a missing role (repeatable), e.g. PLAYER",
    )
    gen.add_argument(
        "--force-while-open",
        action="store_true",
        help="regenerate even if a Godot editor seems to have the project open",
    )
    gen.add_argument(
        "--accept-runtime-upgrade",
        action="store_true",
        help="allow regeneration to move the project to a new major runtime version",
    )
    gen.add_argument(
        "--git",
        action="store_true",
        help="git init (if needed) and commit the generated project; never pushes",
    )
    gen.add_argument("--verbose", action="store_true")
    restore = sub.add_parser("restore", help="restore the previous generation from a backup")
    restore.add_argument("--target", type=Path, required=True, help="the generated project")
    restore.add_argument("--backup", help="backup folder name (default: the newest)")
    from rpggen import analyze_cmd

    analyze = sub.add_parser("analyze", help="analyze an asset pack")
    analyze_cmd.add_arguments(analyze)
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
        result = orchestrator.run(
            cfg_path,
            args.target,
            exe,
            cb,
            placeholders=[r.upper() for r in args.placeholder],
            force_while_open=args.force_while_open,
            accept_runtime_upgrade=args.accept_runtime_upgrade,
            git_message="rpggen: generate project" if args.git else None,
        )
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


def _restore(args: argparse.Namespace) -> int:
    from rpggen.core import promote
    from rpggen.errors import RpgGenError

    target: Path = args.target
    backup = None
    if args.backup:
        backup = target / ".rpggen_backups" / args.backup
    try:
        safety = promote.restore(target, backup)
    except RpgGenError as exc:
        print(f"ERROR   {exc.code}: {exc.issue.message}")
        return 1
    print(f"OK: restored; the replaced state was saved to {safety}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args, _rest = parser.parse_known_args(argv)
    if args.command == "version":
        print(f"rpggen {__version__}")
        return 0
    if args.command == "generate":
        return _generate(args)
    if args.command == "restore":
        return _restore(args)
    if args.command == "analyze":
        from rpggen import analyze_cmd

        return analyze_cmd.main(args)
    if args.command in (None, "gui"):
        from rpggen.gui import app

        return app.run_gui()
    parser.print_help()
    return 2
