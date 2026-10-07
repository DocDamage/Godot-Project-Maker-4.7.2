"""Milestone M8: the editor tools addon, content checks, in-editor rebuild and terrains on the
sample pack."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import (
    archive,
    catalog,
    config,
    godot,
    inventory,
    ledger,
    mapping,
    orchestrator,
    profiles,
)

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
PLUGIN = "res://addons/rpg_project_tools/plugin.cfg"


@pytest.fixture(scope="module")
def sample(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
        inv = inventory.build_inventory(opened)
        cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
        cfg = config.default_for("M8 Game", [config.pack_ref_from_source(SAMPLE, "sample_pack")])
        cfg.starter = mapping.default_starter(cat, "turn_based")
        target = tmp_path_factory.mktemp("m8") / "out"
        result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
        assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
        yield target
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


def test_tools_addon_is_installed_and_enabled(sample: Path) -> None:
    for rel in (
        "plugin.cfg",
        "plugin.gd",
        "dock/asset_dock.gd",
        "dock/placement.gd",
        "tools/content_checks.gd",
        "tools/rebuild.gd",
    ):
        assert (sample / "addons/rpg_project_tools" / rel).is_file(), rel
    project = (sample / "project.godot").read_text(encoding="utf-8")
    assert "editor_plugins" in project
    assert PLUGIN in project
    led = ledger.Ledger.load(sample / paths.LEDGER)
    assert "addons/rpg_project_tools/plugin.cfg" in led.files


def test_index_files_for_the_dock(sample: Path) -> None:
    characters = jsonio.read(sample / "rpggen/character_index.json")
    assert characters
    assert all(
        v.startswith("res://generated/scenes/actors/characters/") for v in characters.values()
    )
    demo = jsonio.read(sample / "rpggen/demo_entities.json")
    assert "starter_map_npc_001" in demo["entities"]
    assert jsonio.read(sample / "rpggen/object_index.json")


def test_validation_includes_the_content_checks(sample: Path) -> None:
    results = jsonio.read(sample / paths.RESULTS_VALIDATE)
    assert any(i["check"] == "content_checks" and i["ok"] for i in results["items"])
    assert not [i for i in results["issues"] if i["code"] in ("VAL-008", "VAL-016", "VAL-017")]


def test_terrain_sets_reach_the_tileset(sample: Path) -> None:
    tilesets = "".join(
        p.read_text(encoding="utf-8") for p in (sample / "generated/tilesets").glob("*.tres")
    )
    assert "terrain_set_0/mode" in tilesets
    assert "terrain_set_0/terrain_0/name" in tilesets
    assert "peering_bit/" in tilesets
    assert list((sample / "generated/terrain_atlases").glob("*.png"))


def test_editor_plugin_loads_in_the_editor(sample: Path, godot_exe: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    shutil.copytree(sample, project, ignore=shutil.ignore_patterns(".godot", ".rpggen_*"))
    exe = godot.find_console_exe(godot_exe)
    subprocess.run(
        [str(exe), "--headless", "--path", str(project), "--import"],
        capture_output=True,
        timeout=600,
        check=False,
    )
    run = subprocess.run(
        [str(exe), "--headless", "--editor", "--path", str(project), "--quit-after", "60"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    output = run.stdout + run.stderr
    assert "SCRIPT ERROR" not in output, output[-3000:]
    assert (
        "rpg_project_tools" not in output
        or "ERROR" not in output.split("rpg_project_tools")[-1][:300]
    )


def test_in_editor_rebuild_keeps_the_ledger_current(
    sample: Path, godot_exe: Path, tmp_path: Path
) -> None:
    """The builder run the dock starts (--update-ledger) records the files it wrote."""
    project = tmp_path / "proj"
    shutil.copytree(sample, project, ignore=shutil.ignore_patterns(".rpggen_*"))
    cat_path = project / paths.CATALOG
    cat = jsonio.read(cat_path)
    players = [
        a
        for a in cat["assets"]
        if a["detected"].get("role") == "PLAYER" and "animations" in a["detected"]
    ]
    assert players, "the sample pack has a player sprite"
    anim = sorted(players[0]["detected"]["animations"])[0]
    players[0]["overrides"] = {"animations": {anim: {"fps": 3.0}}}
    jsonio.write(cat_path, cat)
    exe = godot.find_console_exe(godot_exe)
    run = subprocess.run(
        [
            str(exe),
            "--headless",
            "--path",
            str(project),
            "--script",
            "res://generated/builder/build.gd",
            "--",
            "--update-ledger",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    results = jsonio.read(project / paths.RESULTS_BUILD)
    written = [i["output"] for i in results["items"] if i["action"] == "written"]
    assert any(o.startswith("generated/sprite_frames/") for o in written), written
    led = ledger.Ledger.load(project / paths.LEDGER)
    for rel, entry in led.files.items():
        if rel in ledger.MERGE_MANAGED or entry.owner != "generated":
            continue
        state = ledger.classify(project, rel, led)
        assert state is ledger.FileState.UNTOUCHED, (rel, state)
