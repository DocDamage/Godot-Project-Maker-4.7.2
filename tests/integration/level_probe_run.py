"""Runs the test-only editor plugin tests/integration/level_probe in a copy of an assets-only
project (T17.33): a short level is painted with the Terrain tool's painting and furnished from
the project's Assets dock in a headless editor, and saved; then pictured in a window. Shared by
the tests of the level probe and by the review of real packs."""

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
LEVEL = "res://game/levels/probe_level.tscn"
SHOT_SCENE = """[gd_scene format=3]

[ext_resource type="Script" path="res://rpggen/level_shot.gd" id="1_shot"]

[node name="LevelShot" type="Node"]
script = ExtResource("1_shot")
"""


@dataclass
class LevelRun:
    project: Path
    report: dict
    log: str


def make_level(target: Path, project: Path, godot_exe: Path) -> LevelRun:
    """Copies the assets-only project `target` to `project`, enables the probe beside the tools
    addon and makes the level in a headless editor."""
    if not project.exists():
        shutil.copytree(target, project, ignore=shutil.ignore_patterns(".rpggen_*"))
    shutil.copytree(LEVEL_PROBE, project / "addons" / "zz_level_probe", dirs_exist_ok=True)
    settings = project / "project.godot"
    text = settings.read_text(encoding="utf-8")
    assert ENABLED in text, "the tools addon is the project's one editor plugin"
    probe = ENABLED[:-1] + ', "res://addons/zz_level_probe/plugin.cfg")'
    settings.write_text(text.replace(ENABLED, probe), encoding="utf-8")
    (project / "game" / "levels").mkdir(parents=True, exist_ok=True)
    jsonio.write(project / "rpggen/level_probe_in.json", {"out": LEVEL})
    exe = godot.find_console_exe(godot_exe)
    broken: list[str] = []  # a probe that does not compile or stops at an error would wait

    def watch(line: str) -> None:
        said = "Parse Error" in line or "Failed to load" in line or "at:" in line
        if "zz_level_probe" in line and said:
            broken.append(line)

    run = godot.run_godot(
        exe, project, ["--editor"], timeout_s=900, log_name="level",
        log_dir=project / "rpggen/logs", on_line=watch, is_cancelled=lambda: bool(broken),
    )  # fmt: skip
    log = run.log_path.read_text(encoding="utf-8", errors="replace")
    assert not broken, log[-3000:]
    settings.write_text(text, encoding="utf-8")  # the probe is not left enabled
    (project / "rpggen/level_probe_in.json").unlink(missing_ok=True)
    assert not run.timed_out and run.returncode == 0, log[-3000:]
    report = jsonio.read(project / "rpggen/results/level_probe.json")
    return LevelRun(project, report, log)


def picture_level(project: Path, godot_exe: Path, out: Path) -> tuple[bool, str]:
    """A picture of the probe's level (level_shot.gd), in a window. Returns (it was saved, the
    log)."""
    shutil.copy(LEVEL_PROBE / "level_shot.gd", project / "rpggen" / "level_shot.gd")
    (project / "rpggen" / "level_shot.tscn").write_text(SHOT_SCENE, encoding="utf-8")
    exe = godot.find_console_exe(godot_exe)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    cmd = [str(exe), "--path", str(project), "res://rpggen/level_shot.tscn", "--",
           f"--level={LEVEL}", f"--out={out.resolve().as_posix()}"]  # fmt: skip
    done = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300, errors="replace", env=dict(os.environ)
    )
    for name in ("level_shot.gd", "level_shot.tscn"):
        (project / "rpggen" / name).unlink(missing_ok=True)
    return out.is_file(), done.stdout + done.stderr
