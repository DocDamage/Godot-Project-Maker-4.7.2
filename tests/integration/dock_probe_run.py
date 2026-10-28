"""Runs the test-only editor plugin tests/integration/dock_probe in a copy of a generated project:
the project's own Assets dock places library scenes in a headless editor, undoes and redoes each
and saves the map (T17.27). Shared by the dock tests on squares (test_m8_sample.py) and on
diamonds (test_m17_isometric.py), with the checks of the dock's three old faults, mended:

1. Ctrl+Z after a double click set properties back on a node already out of the tree, and the
   editor logged "No path can be resolved between the nodes ... (not inside tree)";
2. a double click was saved with ``type=`` and a copy of its scene root's properties, not as an
   instance of its scene;
3. a second copy of one asset dropped into the entities was named ``@StaticBody2D@<n>``.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from rpggen import jsonio
from rpggen.core import godot

DOCK_PROBE = Path(__file__).resolve().parent / "dock_probe"
ENABLED = 'enabled=PackedStringArray("res://addons/rpg_project_tools/plugin.cfg")'
# what the editor logged for each property set back on a node out of the tree (fault 1)
NOT_IN_TREE = "not inside tree"
NO_PATH = "No path can be resolved"


def can_open_a_window() -> bool:
    """A windowed editor can be run here: Windows and macOS have a desktop, Linux a display
    (``xvfb-run`` in CI)."""
    import os
    import sys

    return sys.platform != "linux" or bool(os.environ.get("DISPLAY"))


def check_mouse_drops(report: dict, raised: int = 0) -> None:
    """What a real drag and drop placed (T18.18): on the cell the mouse let go over, one step of
    the scene's history that one Ctrl+Z takes away and redo brings back."""
    mouse = [seen for seen in report["places"] if seen["how"] == "mouse"]
    assert mouse, "the probe dragged with the mouse"
    for seen in mouse:
        assert "error" not in seen, seen
        assert seen["action"].startswith("Place ") and seen["one_step"] is True, (
            "the editor's drop and the dock's fixing up are one step"
        )
        assert seen["undo_ok"] is True and seen["undone_in_tree"] is False, "one Ctrl+Z"
        assert seen["redo_ok"] is True
        assert seen["status"].startswith("Placed "), seen["status"]
        if raised and seen.get("raised"):
            assert seen["placed"]["parent"].startswith("YSorted/Entities/Raised")
        else:
            assert seen["placed"]["parent"] == "YSorted/Entities"


@dataclass
class ProbeRun:
    project: Path
    report: dict
    log: str


def run_probe(
    target: Path, project: Path, godot_exe: Path, wanted: dict, *, windowed: bool = False
) -> ProbeRun:
    """Copies the generated project `target` to `project`, enables the probe beside the tools
    addon, and runs the editor headless with `wanted` (see dock_probe/plugin.gd); `windowed`
    opens the editor's window, for a drag and drop of the mouse (T18.18)."""
    shutil.copytree(target, project, ignore=shutil.ignore_patterns(".rpggen_*"))
    shutil.copytree(DOCK_PROBE, project / "addons" / "zz_dock_probe")
    settings = project / "project.godot"
    text = settings.read_text(encoding="utf-8")
    assert ENABLED in text, "the tools addon is the project's one editor plugin"
    probe = ENABLED[:-1] + ', "res://addons/zz_dock_probe/plugin.cfg")'
    settings.write_text(text.replace(ENABLED, probe), encoding="utf-8")
    jsonio.write(project / "rpggen/dock_probe_in.json", wanted)
    exe = godot.find_console_exe(godot_exe)
    broken: list[str] = []  # a probe that stops at an error leaves the editor open: end it

    def watch(line: str) -> None:
        if "zz_dock_probe" in line and ("Parse Error" in line or "at:" in line):
            broken.append(line)

    run = godot.run_godot(
        exe,
        project,
        ["--editor"],
        timeout_s=600,
        log_name="dock",
        log_dir=project / "rpggen/logs",
        on_line=watch,
        is_cancelled=lambda: bool(broken),
        headless=not windowed,
    )
    log = run.log_path.read_text(encoding="utf-8", errors="replace")
    assert not broken, log[-3000:]
    assert not run.timed_out and run.returncode == 0, log[-3000:]
    assert "SCRIPT ERROR" not in log, log[-3000:]
    report = jsonio.read(project / "rpggen/results/dock_probe.json")
    assert report["ok"] is True and report["error"] == "", report
    assert report["dock"] is True, "the project's own Assets dock did the drops"
    return ProbeRun(project, report, log)


def saved_node(scene: str, name: str, parent: str = "YSorted/Entities") -> tuple[str, str]:
    """The header line of the node `name` under `parent` in a saved .tscn, and its body."""
    head = re.search(
        rf'^\[node name="{re.escape(name)}" parent="{re.escape(parent)}".*\]$', scene, re.M
    )
    assert head, f"{name} is saved under {parent}"
    rest = scene[head.end() :]
    following = re.search(r"^\[", rest, re.M)
    return head.group(0), rest[: following.start()] if following else rest


def check_the_faults_are_mended(run: ProbeRun, map_rel: str) -> None:
    """The three faults of the module's docstring, on what the probe placed and saved."""
    # 1. Ctrl+Z sets nothing on a node out of the tree
    assert NOT_IN_TREE not in run.log and NO_PATH not in run.log, [
        line for line in run.log.splitlines() if NOT_IN_TREE in line or NO_PATH in line
    ][:5]
    assert run.report["undo_order"] == ["do 1", "do 2", "undo 1", "undo 2"] * 2, (
        "the scene's history undoes an action's operations in the order they were added"
    )
    places = run.report["places"]
    names = [seen["placed"]["name"] for seen in places]
    # 3. readable names, distinct, the same after undo and redo
    assert len(set(names)) == len(names), names
    for seen in places:
        name = seen["placed"]["name"]
        assert "@" not in name and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name), name
        assert seen["redone"]["name"] == name, "redo gives it the same name"
    # 2. every placed node is saved as an instance of its scene, double click as drop
    scene = (run.project / map_rel).read_text(encoding="utf-8")
    for seen in places:
        head, body = saved_node(scene, seen["placed"]["name"])
        assert "instance=ExtResource(" in head and " type=" not in head, (seen["how"], head)
        assert "metadata/" not in body and "script = " not in body, (seen["how"], body)
