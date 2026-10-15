"""Runs the test-only editor plugin tests/integration/level_probe in a copy of a generated
project (T17.33): a short level is painted with the Terrain tool's painting and furnished from the
project's Assets dock in a headless editor, saved, and then played by the game's smoke harness.
Shared by the tests of the level probe and by the review of real packs (a window and pictures
when ``window`` is true)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rpggen import jsonio
from rpggen.core import godot

LEVEL_PROBE = Path(__file__).resolve().parent / "level_probe"
ENABLED = 'enabled=PackedStringArray("res://addons/rpg_project_tools/plugin.cfg")'
LEVEL = "res://game/maps/probe_level.tscn"


@dataclass
class LevelRun:
    project: Path
    report: dict
    log: str


def make_level(target: Path, project: Path, godot_exe: Path, template: str) -> LevelRun:
    """Copies the generated project `target` to `project`, enables the probe beside the tools
    addon and makes the level from `template` (a map of the project) in a headless editor."""
    if not project.exists():
        shutil.copytree(target, project, ignore=shutil.ignore_patterns(".rpggen_*"))
    shutil.copytree(LEVEL_PROBE, project / "addons" / "zz_level_probe", dirs_exist_ok=True)
    settings = project / "project.godot"
    text = settings.read_text(encoding="utf-8")
    assert ENABLED in text, "the tools addon is the project's one editor plugin"
    probe = ENABLED[:-1] + ', "res://addons/zz_level_probe/plugin.cfg")'
    settings.write_text(text.replace(ENABLED, probe), encoding="utf-8")
    jsonio.write(project / "rpggen/level_probe_in.json", {"template": template, "out": LEVEL})
    exe = godot.find_console_exe(godot_exe)
    run = godot.run_godot(
        exe, project, ["--editor"], timeout_s=900, log_name="level", log_dir=project / "rpggen/logs"
    )
    log = run.log_path.read_text(encoding="utf-8", errors="replace")
    settings.write_text(text, encoding="utf-8")  # the probe is not left enabled
    (project / "rpggen/level_probe_in.json").unlink(missing_ok=True)
    assert not run.timed_out and run.returncode == 0, log[-3000:]
    report = jsonio.read(project / "rpggen/results/level_probe.json")
    return LevelRun(project, report, log)


def play_level(project: Path, godot_exe: Path, out_prefix: Path | None = None) -> tuple[bool, str]:
    """Plays the probe's level with the game's smoke harness (level_steps.gd): headless, or in
    a window with two pictures (``<out_prefix>_play.png``, ``<out_prefix>_whole.png``) when
    `out_prefix` is given. Returns (the smoke run passed, its log)."""
    steps = project / "rpggen" / "level_steps.gd"
    shutil.copy(LEVEL_PROBE / "level_steps.gd", steps)
    exe = godot.find_console_exe(godot_exe)
    user_args = [
        "--rpg-smoke",
        "--rpg-smoke-steps=res://rpggen/level_steps.gd",
        f"--rpg-level={LEVEL}",
    ]
    if out_prefix is None:
        run = godot.run_godot(
            exe, project, ["--", *user_args], timeout_s=300, log_name="level_play",
            log_dir=project / "rpggen/logs",
        )  # fmt: skip
        log = run.log_path.read_text(encoding="utf-8", errors="replace")
        code = run.returncode
    else:
        cmd = [str(exe), "--path", str(project), "--", *user_args,
               f"--rpg-level-out={out_prefix.resolve().as_posix()}"]  # fmt: skip
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, errors="replace", env=dict(os.environ)
        )
        log = done.stdout + done.stderr
        code = done.returncode
    steps.unlink(missing_ok=True)
    return code == 0 and "SCRIPT ERROR" not in log, log
