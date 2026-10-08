from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from rpggen import __version__, cli_support
from rpggen.cli_support import Output
from rpggen.errors import Issue, IssueList, RpgGenError


def _tile_size(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if not 8 <= value <= 256:
        raise argparse.ArgumentTypeError(f"{value} is outside 8 to 256")
    return value


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON document on stdout (the human lines go to stderr)",
    )


def _build_parser() -> argparse.ArgumentParser:
    # No abbreviations: "--targ" is an error, not a silent guess.
    parser = argparse.ArgumentParser(prog="rpggen", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("version", help="print the version", allow_abbrev=False)
    gui = sub.add_parser(
        "gui", help="open the graphical wizard (also the default)", allow_abbrev=False
    )
    gui.add_argument("--target", type=Path, help="open the wizard on this generated project")
    gen = sub.add_parser("generate", help="generate a Godot project", allow_abbrev=False)
    gen.add_argument("--config", type=Path, help="generator_config.json")
    gen.add_argument("--pack", type=Path, help="asset pack folder (creates a default config)")
    gen.add_argument("--name", help="project name for --pack")
    gen.add_argument(
        "--tile-size",
        type=_tile_size,
        metavar="N",
        help="base tile size in pixels, 8 to 256 (--pack otherwise reads it from the packs)",
    )
    gen.add_argument(
        "--archetype",
        choices=("turn_based", "arpg"),
        default="turn_based",
        help="combat archetype for --pack (a --config carries its own)",
    )
    gen.add_argument(
        "--preset",
        metavar="NAME",
        help="apply a saved option preset (saved on the wizard's Options page) to the config",
    )
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
        "--confirm",
        action="store_true",
        help="before a regeneration writes anything, print what it will change and ask y/N "
        "(on a terminal; without one the answer is no)",
    )
    gen.add_argument(
        "--git",
        action="store_true",
        help="git init (if needed) and commit the generated project; never pushes",
    )
    gen.add_argument(
        "--dry-run",
        action="store_true",
        help="check the config and the packs, plan the starter map and print what would be made; "
        "nothing is written and Godot is not started",
    )
    gen.add_argument("--verbose", action="store_true")
    _add_json(gen)
    restore = sub.add_parser(
        "restore", help="restore the previous generation from a backup", allow_abbrev=False
    )
    restore.add_argument("--target", type=Path, required=True, help="the generated project")
    restore.add_argument("--backup", help="backup folder name (default: the newest)")
    _add_json(restore)
    diagnose = sub.add_parser(
        "diagnose", help="write a diagnostic bundle (no art) for a bug report", allow_abbrev=False
    )
    diagnose.add_argument("--target", type=Path, required=True, help="project or failed-run folder")
    diagnose.add_argument("--out", type=Path, help="zip to write (default: next to the folder)")
    diagnose.add_argument("--godot", type=Path, help="Godot executable (its version is recorded)")
    _add_json(diagnose)
    from rpggen import analyze_cmd

    analyze = sub.add_parser("analyze", help="analyze an asset pack", allow_abbrev=False)
    analyze_cmd.add_arguments(analyze)
    _add_json(analyze)
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


def _document(
    target: Path,
    issues: list[Issue],
    *,
    failed_phase: str | None = None,
    failed_staging: Path | None = None,
    skipped: dict[str, str] | None = None,
    timings: dict[str, float] | None = None,
    **extra: object,
) -> dict[str, object]:
    """The fields of ``generate --json`` that follow the envelope (``docs/spec/02_SCHEMAS.md``)."""
    return {
        "target": str(target),
        "dry_run": False,
        "cancelled": False,
        "run_id": "",
        "failed_phase": failed_phase,
        "failed_staging": str(failed_staging) if failed_staging else None,
        "skipped": dict(skipped or {}),
        "timings": dict(timings or {}),
        "issues": [cli_support.issue_json(i) for i in issues],
        **extra,
    }


def _not_found(message: str, **detail: Any) -> IssueList:
    issues = IssueList()
    issues.add("ENV-001", message, **detail)
    return issues


def _generate(args: argparse.Namespace) -> int:
    from rpggen import logging_setup, paths
    from rpggen.core import config as config_mod
    from rpggen.core import orchestrator

    out = Output("generate", args.json)
    if args.target is None or (args.config is None and args.pack is None):
        return out.usage("--target and one of --config / --pack are required")
    exe = _resolve_godot(args.godot)
    if exe is None and not args.dry_run:
        issues = _not_found("Godot was not found; pass --godot or set RPGGEN_GODOT.", path="")
        out.issues(issues)
        return out.done(cli_support.INPUT, **_document(args.target, issues))
    logging_setup.configure(paths.log_dir(), args.verbose)  # the wizard's folder too
    with tempfile.TemporaryDirectory(prefix="rpggen_cfg_") as tmp:
        cfg_path = args.config
        try:
            if cfg_path is None:
                if not args.pack.exists():
                    raise RpgGenError(
                        "ARCH-001", path=str(args.pack), reason="no such file or folder"
                    )
                name = args.name or args.pack.name
                cfg = orchestrator.default_config_for_pack(
                    args.pack, name, tile_size=args.tile_size or 16, archetype=args.archetype
                )
                cfg_path = Path(tmp) / "generator_config.json"
                config_mod.save(cfg, cfg_path)
            if args.preset:
                from rpggen.core import app_settings, options

                preset = app_settings.get().option_presets.get(args.preset)
                if preset is None:
                    return out.usage(f"there is no saved preset called {args.preset!r}")
                try:
                    cfg = options.apply_preset(config_mod.load(cfg_path), preset)
                except ValueError as exc:
                    return out.usage(f"the preset does not fit this config: {exc}")
                cfg_path = Path(tmp) / "preset_config.json"
                config_mod.save(cfg, cfg_path)
        except RpgGenError as exc:  # a pack or a config that cannot be read
            out.issues([exc.issue])
            return out.done(
                cli_support.exit_code_for([exc.issue]), **_document(args.target, [exc.issue])
            )
        # a --pack run without --tile-size reads the size from the packs
        derive = args.config is None and args.tile_size is None
        if args.dry_run:
            return _dry_run(args, out, cfg_path, exe, derive)
        return _run(args, out, cfg_path, exe, derive)


def _ask_promotion(out: Output) -> Any:
    """``--confirm``: print the summary of a regeneration, then ask y/N on a terminal (no terminal,
    no answer: the run is cancelled rather than going on unasked)."""

    def ask(summary: Any) -> bool:
        out.say(
            f"This regeneration will update {len(summary.write)} file(s), write "
            f"{len(summary.conflicts)} .rpggen-new copy(ies) beside files you changed, delete "
            f"{len(summary.delete)} and leave {len(summary.skipped_deleted)} you deleted alone. "
            f"The old versions are saved in {summary.backup}."
        )
        for rel in summary.conflicts:
            out.say(f"  conflict: {rel}")
        if not sys.stdin.isatty():
            out.say("No terminal to ask on: not regenerating.")
            return False
        try:
            return input("Regenerate? [y/N] ").strip().lower() in ("y", "yes")
        except EOFError:
            return False

    return ask


def _run(
    args: argparse.Namespace, out: Output, cfg_path: Path, exe: Path | None, derive: bool
) -> int:
    from rpggen.core import orchestrator

    assert exe is not None  # only a dry run goes on without Godot

    def show(text: str) -> None:
        # Godot's own lines (a screenful per second) only with --verbose
        if args.verbose or not text.startswith("[godot] "):
            out.say(text)

    with cli_support.interruptible() as is_cancelled:
        result = orchestrator.run(
            cfg_path,
            args.target,
            exe,
            orchestrator.Callbacks(
                on_log=show,
                is_cancelled=is_cancelled,
                confirm_promotion=_ask_promotion(out) if args.confirm else (lambda summary: True),
            ),
            placeholders=[r.upper() for r in args.placeholder],
            force_while_open=args.force_while_open,
            accept_runtime_upgrade=args.accept_runtime_upgrade,
            git_message="rpggen: generate project" if args.git else None,
            derive_tile_size=derive,
        )
    document = _document(
        result.target,
        result.issues,
        failed_phase=result.failed_phase,
        failed_staging=result.failed_staging,
        skipped=result.skipped,
        timings=result.timings,
    )
    document.update(cancelled=result.cancelled, run_id=result.run_id)
    out.issues(result.issues)
    if result.ok:
        out.say(f"OK: project generated in {result.target}")
        return out.done(cli_support.OK, **document)
    if result.cancelled:
        out.say("CANCELLED: nothing was delivered")
        return out.done(cli_support.CANCELLED, **document)
    out.say("FAILED: generation did not succeed")
    if result.failed_staging:
        out.say(f"        kept for inspection: {result.failed_staging}")
    return out.done(cli_support.exit_code_for(result.issues), **document)


def _dry_run(
    args: argparse.Namespace, out: Output, cfg_path: Path, exe: Path | None, derive: bool
) -> int:
    from rpggen.core import dry_run

    with cli_support.interruptible() as is_cancelled:
        result = dry_run.run(
            cfg_path,
            args.target,
            godot_exe=exe,
            placeholders=args.placeholder,
            force_while_open=args.force_while_open,
            accept_runtime_upgrade=args.accept_runtime_upgrade,
            derive_tile_size=derive,
            is_cancelled=is_cancelled,
        )
    document = _document(
        result.target,
        result.issues,
        failed_phase=result.failed_phase,
        timings=result.timings,
        summary=result.summary,
    )
    document.update(dry_run=True, cancelled=result.cancelled)
    out.say("Dry run: nothing was written and Godot was not started.")
    for line in dry_run.format_summary(result.summary):
        out.say(line)
    out.issues(result.issues)
    if result.ok:
        out.say("OK: nothing stops a generation")
        return out.done(cli_support.OK, **document)
    if result.cancelled:
        out.say("CANCELLED")
        return out.done(cli_support.CANCELLED, **document)
    out.say(f"FAILED: a generation would stop in the {result.failed_phase} phase")
    return out.done(cli_support.exit_code_for(result.issues), **document)


def _restore(args: argparse.Namespace) -> int:
    from rpggen.core import promote

    out = Output("restore", args.json)
    target: Path = args.target
    backup = None
    if args.backup:
        backup = target / ".rpggen_backups" / args.backup
    fields = {"target": str(target), "backup": args.backup, "saved_state": None}
    try:
        safety = promote.restore(target, backup)
    except RpgGenError as exc:
        out.issues([exc.issue])
        return out.done(
            cli_support.exit_code_for([exc.issue]),
            **fields,
            issues=[cli_support.issue_json(exc.issue)],
        )
    out.say(f"OK: restored; the replaced state was saved to {safety}")
    return out.done(cli_support.OK, **{**fields, "saved_state": str(safety)}, issues=[])


def _diagnose(args: argparse.Namespace) -> int:
    from rpggen.core import diagnostics

    out = Output("diagnose", args.json)
    target: Path = args.target
    if not target.is_dir():
        return out.usage(f"{target} is not a folder")
    bundle = args.out or target.parent / diagnostics.default_bundle_name(target)
    exe = _resolve_godot(args.godot)
    diagnostics.make_bundle(target, bundle, exe)
    out.say(f"OK: diagnostic bundle written to {bundle}")
    return out.done(cli_support.OK, target=str(target), bundle=str(bundle))


def _only_qt_arguments(raw: list[str]) -> bool:
    """True when ``raw`` can only be Qt options (``-platform offscreen``): every word is an option
    or follows one. A word that starts a line, such as a mistyped command, is not."""
    if {"-h", "--help"} & set(raw):
        return False
    for i, word in enumerate(raw):
        if not word.startswith("-") and (i == 0 or not raw[i - 1].startswith("-")):
            return False
    return True


def _gui(target: Path | None, qt_arguments: list[str]) -> int:
    from rpggen.gui import app

    return app.run_gui([sys.argv[0], *qt_arguments], target=target)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "generate":
        return _generate(args)
    if args.command == "restore":
        return _restore(args)
    if args.command == "diagnose":
        return _diagnose(args)
    from rpggen import analyze_cmd

    return analyze_cmd.main(args)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    if raw[:1] != ["version"]:
        from rpggen.core import cache_policy

        cache_policy.migrate()  # settings, drafts and logs of an older version move first
    if _only_qt_arguments(raw):  # no command: the wizard, with every argument left to Qt
        return _gui(None, raw)
    args, rest = parser.parse_known_args(raw)
    if args.command == "gui":  # the one command that forwards unknown arguments (-style, ...)
        return _gui(getattr(args, "target", None), rest)
    if rest:
        parser.parse_args(raw)  # exits with code 2 and "unrecognized arguments"
    if args.command == "version":
        print(f"rpggen {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return cli_support.USAGE
    out = Output(args.command, getattr(args, "json", False))
    try:
        return _dispatch(args)
    except KeyboardInterrupt:  # a second Ctrl+C, or one where no command was listening
        out.say("CANCELLED")
        return out.done(cli_support.CANCELLED, error="cancelled")
    except Exception as exc:  # noqa: BLE001 - a coded exit status, not a traceback
        if getattr(args, "verbose", False):
            traceback.print_exc()
        message = f"{type(exc).__name__}: {exc}"
        out.say(f"INTERNAL ERROR: {message} (run with --verbose for the traceback)")
        return out.done(cli_support.INTERNAL, error=message)
