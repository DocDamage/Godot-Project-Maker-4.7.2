from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from rpggen.core import godot

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]


def test_template_project_imports(godot_exe: Path, tmp_path: Path) -> None:
    project = tmp_path / "templates"
    shutil.copytree(
        REPO / "godot_templates", project, ignore=shutil.ignore_patterns(".godot", "results.json")
    )
    run = godot.import_project(godot_exe, project, tmp_path / "logs")
    assert run.returncode == 0, run.stdout
    assert not run.timed_out
    errors = [ln for ln in run.stdout.splitlines() + run.stderr.splitlines() if "ERROR:" in ln]
    assert errors == []
    # Godot must not rewrite the hand-written starter project.godot.
    original = (REPO / "godot_templates" / "project.godot").read_text(encoding="utf-8")
    assert (project / "project.godot").read_text(encoding="utf-8") == original


# T14.01: the real-time combat primitives, shared by the action RPG and the metroidvania
REALTIME = "addons/rpg_runtime/combat/realtime"
OLD_HOME = "addons/rpg_runtime/archetypes/arpg"
MOVED = {
    "damage_info": "RpgDamageInfo",
    "hitbox": "RpgHitbox",
    "hurtbox": "RpgHurtbox",
    "health": "RpgHealth",
    "projectile": "RpgProjectile",
    "state_machine": "RpgStateMachine",
    "pickup": "RpgPickup",
    "screen_feedback": "RpgScreenFeedback",
}


def _class_names() -> dict[str, list[str]]:
    """class name -> the template scripts that define it."""
    found: dict[str, list[str]] = {}
    templates = REPO / "godot_templates"
    for script in sorted(templates.rglob("*.gd")):
        if ".godot" in script.parts:
            continue
        match = re.search(r"^class_name\s+(\w+)", script.read_text(encoding="utf-8"), re.M)
        if match:
            found.setdefault(match.group(1), []).append(script.relative_to(templates).as_posix())
    return found


def test_every_class_name_is_defined_once() -> None:
    twice = {name: where for name, where in _class_names().items() if len(where) > 1}
    assert twice == {}


def test_the_realtime_classes_live_in_the_shared_folder_and_the_old_paths_are_shims() -> None:
    classes = _class_names()
    templates = REPO / "godot_templates"
    for stem, name in MOVED.items():
        assert classes[name] == [f"{REALTIME}/{stem}.gd"]
        shim = (templates / OLD_HOME / f"{stem}.gd").read_text(encoding="utf-8")
        code = [ln for ln in shim.splitlines() if ln.strip() and not ln.startswith("#")]
        assert code == [f'extends "res://{REALTIME}/{stem}.gd"'], stem
        assert "2.0" in shim and f"{REALTIME}/{stem}.gd" in shim


def test_the_shared_combat_folder_names_no_archetype_class() -> None:
    """A metroidvania project has no archetypes/arpg/ folder: the shared set must not need it."""
    arpg_only = {
        name
        for name, where in _class_names().items()
        if where[0].startswith(("addons/rpg_runtime/archetypes/", "builder/recipes/"))
    }
    for script in sorted((REPO / "godot_templates" / REALTIME).glob("*.gd")):
        words = set(re.findall(r"Rpg\w+", script.read_text(encoding="utf-8")))
        assert words & arpg_only == set(), script.name
