"""Developer commands: ``python -m rpggen.dev godot-test`` and ``make-fixtures``."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rpggen.core import godot

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "godot_templates"


def resolve_godot(exe: Path | None = None) -> Path:
    """The Godot executable from the argument, $RPGGEN_GODOT, or auto-discovery."""
    if exe is not None:
        return exe
    env = os.environ.get("RPGGEN_GODOT")
    if env:
        return Path(env)
    found = godot.auto_find_godot()
    if not found:
        raise SystemExit("Godot not found: set RPGGEN_GODOT to the Godot 4.7.2 console executable")
    return found[0]


def godot_test(exe: Path | None = None) -> int:
    """Run the template project's GDScript tests headless; returns the process exit code."""
    exe = godot.find_console_exe(resolve_godot(exe))
    with tempfile.TemporaryDirectory(prefix="rpggen_godot_test_") as tmp:
        project = Path(tmp) / "godot_templates"
        shutil.copytree(TEMPLATES, project, ignore=shutil.ignore_patterns(".godot", "results.json"))
        log_dir = Path(tmp) / "logs"
        imp = godot.import_project(exe, project, log_dir)
        if imp.returncode != 0 or imp.timed_out:
            print(imp.stdout)
            print(imp.stderr, file=sys.stderr)
            return 1
        run = godot.run_godot(
            exe,
            project,
            ["--script", "res://tests/run_tests.gd"],
            timeout_s=godot.BUILD_TIMEOUT_S,
            log_name="unit_tests",
            log_dir=log_dir,
        )
        for line in run.stdout.splitlines():
            if line.startswith(("PASS ", "FAIL ", "tests:")):
                print(line)
        if run.returncode != 0:
            print(run.stderr, file=sys.stderr)
        return 1 if run.timed_out else run.returncode


def make_fixtures() -> int:
    tool = REPO_ROOT / "tools" / "make_synthetic_packs.py"
    out = REPO_ROOT / "test_packs" / "synthetic"
    return subprocess.run([sys.executable, str(tool), "--out", str(out)], check=False).returncode


def synthetic_packs() -> list[Path]:
    root = REPO_ROOT / "test_packs" / "synthetic"
    return sorted(p for p in root.iterdir() if p.is_dir() or p.suffix == ".zip")


def update_goldens() -> int:
    """Rewrite tests/golden/<pack>.catalog.json from the current assemble() output."""
    from rpggen import jsonio
    from rpggen.core import archive, catalog, inventory

    golden = REPO_ROOT / "tests" / "golden"
    golden.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rpggen_goldens_") as tmp:
        os.environ["RPGGEN_CACHE_DIR"] = tmp
        for pack_path in synthetic_packs():
            opened = archive.open_pack(pack_path, set())
            inv = inventory.build_inventory(opened)
            cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
            target = golden / f"{pack_path.stem}.catalog.json"
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(jsonio.dumps(cat.to_json()))
            print(f"wrote {pack_path.stem}.catalog.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rpggen.dev")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("godot-test", help="run the template project's GDScript tests")
    sub.add_parser("make-fixtures", help="regenerate test_packs/synthetic")
    sub.add_parser("update-goldens", help="rewrite tests/golden/*.catalog.json")
    args = parser.parse_args(argv)
    if args.command == "godot-test":
        return godot_test()
    if args.command == "update-goldens":
        return update_goldens()
    return make_fixtures()


if __name__ == "__main__":
    raise SystemExit(main())
