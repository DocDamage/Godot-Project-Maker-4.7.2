"""A world of connected maps on the sample pack (T13.20): it generates, validates and plays; a
regeneration keeps the stored plan and only builds what is new; a broken door only warns."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import (
    archive,
    catalog,
    config,
    inventory,
    mapping,
    orchestrator,
    profiles,
    world_plan,
)

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
AREAS = [
    {"name": "Village", "biome": "village"},
    {"name": "Meadow", "biome": "field"},
    {"name": "Woods", "biome": "forest", "size": [28, 22], "enemies": 3, "chests": 2},
]


def _config(archetype: str = "turn_based") -> config.GeneratorConfig:
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        "World", [config.pack_ref_from_source(SAMPLE, "sample_pack")], archetype=archetype
    )
    cfg.starter = mapping.default_starter(cat, archetype)
    cfg.starter_map = {"areas": [dict(a) for a in AREAS]}
    return cfg


def _maps(target: Path) -> dict[str, str]:
    folder = target / "game" / "maps"
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*.tscn")}


def test_a_three_area_world_generates_validates_and_plays(
    godot_exe: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    cfg = _config()
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert not [i for i in result.issues if i.code in ("VAL-016", "VAL-017", "VAL-027", "VAL-028")]

    # the maps: the village and one per area; the demo's field is not made
    assert sorted(_maps(target)) == [
        "interior_1.tscn",
        "meadow.tscn",
        "starter_map.tscn",
        "woods.tscn",
    ]
    plan = world_plan.load(target)
    assert plan is not None and world_plan.exists(target)
    assert [a["biome"] for a in plan["areas"]] == ["village", "field", "forest"]
    assert world_plan.check(plan) == {"unreachable": [], "unpaired": []}
    assert sorted(plan["maps"]) == ["meadow", "starter_map", "woods"], "a hash per map it built"
    ledger = jsonio.read(target / "rpggen/ownership_ledger.json")
    assert ledger["files"]["rpggen/world_plan.json"]["owner"] == "generated"
    assert ledger["files"]["game/maps/woods.tscn"]["owner"] == "user_seed"
    for area in ("meadow", "woods"):
        assert plan["maps"][area]["map_hash"] == ledger["files"][f"game/maps/{area}.tscn"]["sha256"]

    # every door of the plan is in its map, with the spawn point the other side arrives at
    for area in plan["areas"]:
        text = (target / area["map"]).read_text(encoding="utf-8")
        for door in area["doors"]:
            assert f'[node name="{door["id"]}" type="Area2D"' in text, door["id"]
            assert f'target_map = "res://{door["to_map"]}"' in text
            assert f'target_spawn = &"{door["to_spawn"]}"' in text
            assert f'spawn_id = &"{door["spawn_id"]}"' in text
    woods = (target / "game/maps/woods.tscn").read_text(encoding="utf-8")
    assert len(re.findall(r'\[node name="Decor\d+"', woods)) == 28, "a forest is full of trees"
    assert len(re.findall(r'\[node name="Enemy\d+"', woods)) == 3
    assert len(re.findall(r'\[node name="Chest\d+"', woods)) == 2
    assert "tree" in woods and 'entity_id = "woods_enemy_003"' in woods

    # the game was played through a door and back
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    assert "world_doors: went to meadow and back" in log
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] and "world_doors" in [i["name"] for i in smoke["items"]]
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "## World" in report and "3 areas: Village, Meadow (field), Woods (forest)" in report

    # ---- regenerating with another seed and a bigger table builds only the new area
    before = _maps(target)
    stored = jsonio.read(target / world_plan.PLAN_FILE)
    bigger = _config()
    bigger.seed = cfg.seed + 1000
    bigger.starter_map = {
        "areas": [*AREAS, {"name": "Old mine", "biome": "cave", "size": [24, 18], "join": "Woods"}]
    }
    # (the repair of T13.24 is switched off here: this test is about what the build itself does)
    again = orchestrator.run_in_memory(bigger, None, target, godot_exe, repair_world=False)
    assert again.ok, [f"{i.code}: {i.message}" for i in again.issues]
    after = _maps(target)
    assert sorted(set(after) - set(before)) == ["old_mine.tscn"]
    assert {k: v for k, v in after.items() if k in before} == before, "no existing map changed"
    new_plan = world_plan.load(target)
    assert new_plan["seed"] == stored["seed"], "the world was not planned again"
    for area in stored["areas"]:
        kept = world_plan.area_of(new_plan, area["id"])
        assert new_plan["grid"][area["id"]] == stored["grid"][area["id"]]
        assert kept["doors"][: len(area["doors"])] == area["doors"]
    assert "old_mine" in new_plan["maps"] and new_plan["maps"]["woods"] == stored["maps"]["woods"]
    # the mine's door leads to the woods, whose map (never rewritten) has no spawn for it yet:
    # a warning, and the build still succeeds (T13.24 mends it)
    warnings = [i for i in again.issues if i.code == "VAL-028"]
    assert len(warnings) == 1 and warnings[0].severity.value == "warning"
    assert "old_mine_door_woods" in warnings[0].message and "from_old_mine" in warnings[0].message
    assert not [i for i in again.issues if i.code in ("VAL-016", "VAL-017")]

    # ---- a door broken by hand only warns too
    meadow = target / "game/maps/meadow.tscn"
    text = meadow.read_text(encoding="utf-8")
    assert 'target_spawn = &"from_meadow"' in text
    meadow.write_text(
        text.replace('target_spawn = &"from_meadow"', 'target_spawn = &"nowhere"'),
        encoding="utf-8",
        newline="\n",
    )
    broken = orchestrator.run_in_memory(bigger, None, target, godot_exe, repair_world=False)
    codes = sorted(i.code for i in broken.issues if i.code.startswith("VAL-02"))
    # the step that walks back through that door would now end somewhere else, so only the
    # validation is asked here
    assert codes.count("VAL-028") == 2, [i.message for i in broken.issues]
    assert all(i.severity.value == "warning" for i in broken.issues if i.code == "VAL-028")


def test_an_action_rpg_world_with_a_locked_cave(
    godot_exe: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    cfg = _config("arpg")
    cfg.starter_map = {
        "areas": [*AREAS, {"name": "Old mine", "biome": "cave", "size": [24, 18]}],
        "size": [48, 32],
    }
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    plan = world_plan.load(target)
    assert plan["areas"][0]["size"] == [48, 32], "the village has the starter map's size"
    key = plan["key"]
    assert key["opens"] == "old_mine"
    item = (target / "game/data/items/cave_key.tres").read_text(encoding="utf-8")
    assert 'id = &"cave_key"' in item and "category = 5" in item
    holder = (target / "game" / "maps" / f"{key['area']}.tscn").read_text(encoding="utf-8")
    assert '"item_id": "cave_key"' in holder, "the key lies in a chest of its area"
    # the gate stands on the door into the mine, and takes the key
    gated = [(a, g) for a in plan["areas"] for g in a.get("gates", [])]
    assert gated
    for area, gate in gated:
        text = (target / area["map"]).read_text(encoding="utf-8")
        assert f'entity_id = "{gate["id"]}"' in text and 'key_item = &"cave_key"' in text
    assert not [i for i in result.issues if i.code in ("VAL-025", "VAL-027", "VAL-028")]


# ------------------------------------------------------------------------ world repair (T13.24)


def test_rpggen_mends_the_maps_it_made_and_yours_when_you_ask(
    godot_exe: Path, tmp_path: Path, monkeypatch
) -> None:
    from rpggen.core import promote, world_repair

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    cfg = _config()
    target = tmp_path / "out"
    first = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert first.ok, [f"{i.code}: {i.message}" for i in first.issues]
    assert first.world_repair is None, "a whole world: Godot is not started for a repair"
    woods = target / "game/maps/woods.tscn"
    built = woods.read_bytes()

    # a fourth area joined to the woods: its door arrives at a spawn point the woods do not have
    bigger = _config()
    bigger.starter_map = {
        "areas": [*AREAS, {"name": "Old mine", "biome": "cave", "size": [24, 18], "join": "Woods"}]
    }
    # ... switched off, the warning stays and nothing is mended
    off = orchestrator.run_in_memory(bigger, None, target, godot_exe, repair_world=False)
    assert off.ok and off.world_repair is None
    assert [i.code for i in off.issues if i.code == "VAL-028"] == ["VAL-028"]
    assert woods.read_bytes() == built

    # ... by default rpggen mends the map it made: the spawn point and a door back
    mended = orchestrator.run_in_memory(bigger, None, target, godot_exe)
    assert mended.ok, [f"{i.code}: {i.message}" for i in mended.issues]
    repair = mended.world_repair
    assert repair is not None and repair.backup is not None
    assert [(line["kind"], line["map"]) for line in repair.repairs] == [
        ("spawn", "game/maps/woods.tscn"),
        ("door", "game/maps/woods.tscn"),
    ]
    assert repair.offered == [] and repair.unfixable == []
    assert not [i for i in mended.issues if i.code in ("VAL-027", "VAL-028")], "mended: no warning"
    text = woods.read_text(encoding="utf-8")
    assert 'spawn_id = &"from_old_mine"' in text
    assert '[node name="woods_door_old_mine" type="Area2D"' in text
    assert 'target_map = "res://game/maps/old_mine.tscn"' in text
    assert 'target_spawn = &"from_woods"' in text
    # what the map had is still there
    for kept in (
        '[node name="woods_door_starter_map"',
        'spawn_id = &"from_starter_map"',
        "Decor28",
    ):
        assert kept in text, kept
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "## World repairs" in report
    assert "game/maps/woods.tscn: added the spawn point from_old_mine" in report
    assert "Restore previous" in report
    stored = jsonio.read(target / world_repair.RESULT_FILE)
    assert [line["kind"] for line in stored["repairs"]] == ["spawn", "door"]
    # the mended map is still rpggen's, and a second look finds nothing to do
    assert "game/maps/woods.tscn" in world_repair.unedited_maps(target)
    again = world_repair.run(target, godot_exe, dry_run=True)
    assert again.repairs == [] and again.unfixable == []

    # Restore previous takes the repair back
    promote.restore(target)
    assert woods.read_bytes() == built
    assert world_repair.run(target, godot_exe, dry_run=True).repairs, "broken again"

    # a map its owner changed is not touched by itself: the repair is offered
    woods.write_bytes(built + b"\n; a note of mine\n")
    mine = woods.read_bytes()
    offered = orchestrator.run_in_memory(bigger, None, target, godot_exe)
    assert offered.ok
    assert offered.world_repair is not None and offered.world_repair.repairs == []
    assert [line["map"] for line in offered.world_repair.offered] == ["game/maps/woods.tscn"] * 2
    assert woods.read_bytes() == mine
    assert [i.code for i in offered.issues if i.code == "VAL-028"] == ["VAL-028"]
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "Not done (game/maps/woods.tscn was changed by you)" in report
    # ... until you ask
    asked = world_repair.run(target, godot_exe)
    assert len(asked.repairs) == 2 and asked.backup is not None
    assert 'spawn_id = &"from_old_mine"' in woods.read_text(encoding="utf-8")
    assert world_repair.run(target, godot_exe, dry_run=True).repairs == []
    assert "game/maps/woods.tscn" not in world_repair.unedited_maps(target), "it is still yours"
