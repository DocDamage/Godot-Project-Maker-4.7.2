"""Milestone M17, the farm (T17.04, T17.05): the top-down sample pack, which has nothing made
for the kind, as a farm with the crops, soil and tools of the drawn farm kit, and the synthetic `ranch` pack, whose
growth strips are its crops."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import features, jsonio, paths, schema
from rpggen.core import config, crop_plan, ledger, orchestrator, profiles, world_plan

pytestmark = [pytest.mark.integration, pytest.mark.farm]

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
RANCH = REPO / "test_packs" / "synthetic" / "ranch"
# the farm's own steps, after the shared top-down sequence
STEPS = [
    "farm_is_there",
    "till_a_cell",
    "plant_a_seed",
    "water_it",
    "a_night_grows_it",
    "crop_ripens",
    "harvest",
]
TOOLS = ("hoe", "watering_can", "sickle", "farm_axe")
FILES = [
    "generated/scenes/combat/combat_mode.tscn",
    "generated/scenes/actors/player.tscn",
    "generated/tilesets/farm_soil.tres",
    "generated/data/crops.json",
    "game/data/crops.json",
    "game/maps/starter_map.tscn",
]


def _config(source: Path, pack_id: str) -> config.GeneratorConfig:
    return config.default_for(
        "Green Acre", [config.pack_ref_from_source(source, pack_id)], archetype="farm"
    )


def _errors(result) -> list[str]:
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value != "info"]


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(folder)
    try:
        yield folder
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


@pytest.fixture(scope="module")
def plain(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    target = tmp_path_factory.mktemp("m17_plain") / "out"
    result = orchestrator.run_in_memory(_config(SAMPLE, "sample_pack"), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


@pytest.fixture(scope="module")
def ranch(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m17_ranch") / "out"
    result = orchestrator.run_in_memory(_config(RANCH, "ranch"), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _text(target: Path, rel: str) -> str:
    return (target / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------- the top-down sample as a farm


def test_the_kind_is_generated_but_not_offered(plain) -> None:
    target, _result = plain
    assert features.FARM_AVAILABLE is False, "the wizard does not offer it until its gate"
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "farm" and "starter_map" not in saved
    assert saved["features"]["combat"] is False and saved["features"]["dialogue"] is True
    bindings = saved["input"]
    assert bindings["use"]["keys"] == ["Space", "J"] and bindings["use"]["joy_buttons"] == [0]
    assert bindings["interact"] == {"keys": ["E"], "joy_buttons": [2]}
    assert {"next_item", "prev_item", *(f"hotbar_{n}" for n in range(1, 11))} <= set(bindings)


def test_the_sample_pack_is_a_farm_that_passes_its_smoke_run(plain) -> None:
    target, _result = plain
    names = _smoke(target)
    assert names[-len(STEPS) :] == STEPS
    # the shared top-down sequence ran before them, as it does for the other top-down kinds
    assert names[0] == "title_new_game" and names.index("pause_menu") < names.index(STEPS[0])
    assert "npc_dialogue" in names and "enter_building" in names
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    assert "SCRIPT ERROR" not in log


def test_the_project_has_the_farm_code_and_no_other_kinds(plain) -> None:
    target, _result = plain
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["farm"]
    for name in ("farm_mode", "farmer", "tool", "hotbar", "energy", "field", "crop", "crop_data"):
        assert (archetypes / "farm" / f"{name}.gd").is_file(), name
    assert sorted(p.stem for p in (archetypes / "farm/tools").glob("*.gd")) == [
        "axe",
        "hoe",
        "sickle",
        "watering_can",
    ]
    recipes = target / "generated/builder/recipes"
    assert sorted(p.name for p in recipes.iterdir() if p.is_dir()) == ["farm"]
    smoke = sorted(p.name for p in (target / "generated/builder/smoke").glob("smoke_steps_*.gd"))
    assert smoke == [
        "smoke_steps_farm.gd",
        "smoke_steps_m1.gd",
        "smoke_steps_m4.gd",
        "smoke_steps_m6.gd",
    ]
    for rel in FILES:
        assert (target / rel).is_file(), rel
    # nothing of a fight: no enemy, no battle data, no action HUD
    assert not (target / "generated/scenes/enemies").exists()
    assert not (target / "generated/scenes/ui/hud_arpg.tscn").exists()
    assert not (target / "game/data/battle_commands").exists()
    strings = _text(target, "game/i18n/strings.tsv")
    assert "FARM_TIRED\t" in strings and "ITEM_HOE_NAME\t" in strings
    assert "ARPG_QUICK_EMPTY" not in strings and "ARC_GAME_OVER" not in strings


def test_the_recipe_writes_the_farmer_for_the_top_down_sample(plain) -> None:
    target, _result = plain
    player = _text(target, "generated/scenes/actors/player.tscn")
    assert "archetypes/farm/farmer.gd" in player and "actors/actor.gd" not in player
    for part in ('name="TileFrame"', 'name="ToolIcon"', 'name="PlayerInput"', 'name="Interaction"'):
        assert part in player, part
    assert "sprite_frames/sample_pack." in player, "the hero of the pack is the farmer"
    assert 'groups=["player"]' in player
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "archetypes/farm/farm_mode.gd" in mode and "archetypes/farm/ui/farm_hud.gd" in mode
    assert mode.count('type="PanelContainer"') == 10, "ten slots"
    assert 'name="EnergyBar"' in mode
    # a new game starts with the tools and the seeds of the first crop, the first slots
    new_game = _text(target, "game/data/new_game.tres")
    first = jsonio.read(target / "game/data/crops.json")["crops"][0]
    order = [new_game.index(f'"{item}"') for item in (*TOOLS, first["seed"], "potion")]
    assert order == sorted(order)
    for tool in TOOLS:
        item = _text(target, f"game/data/items/{tool}.tres")
        picture = "axe" if tool == "farm_axe" else tool
        assert f'id = &"{tool}"' in item
        assert f"generated/farm_kit/{picture}.png" in item, "the icon of the drawn farm kit"
    files = ledger.Ledger.load(target / paths.LEDGER).files
    assert files["game/data/items/hoe.tres"].owner == "user_seed"
    assert files["game/data/crops.json"].owner == "user_seed"
    assert files["generated/data/crops.json"].owner == "generated"


def test_a_pack_without_crops_gets_the_drawn_ones_and_a_plot_to_grow_them_on(plain) -> None:
    target, _result = plain
    stored = world_plan.load(target)
    assert stored is not None and stored["areas"] == []
    section = stored["farm"]
    kit = {
        "crops": [
            {"asset": f"rpggen_farm_kit.{name}", "name": name, "stages": 5}
            for name in ("berry", "carrot", "turnip")
        ]
    }
    assert section == crop_plan.plan({}, 12345, kit), "the plan of the seed, of the kit's crops"
    assert sorted(c["id"] for c in section["crops"]) == ["berry", "carrot", "turnip"]
    assert crop_plan.check(section) == []
    listed = jsonio.read(target / "game/data/crops.json")
    schema.validate("crops", listed)
    assert listed == jsonio.read(target / "generated/data/crops.json")
    assert listed == crop_plan.crops_file(
        section,
        {c["id"]: f"res://generated/scenes/farm/crops/{c['id']}.tscn" for c in section["crops"]},
    ), "the builder writes what the planner says"
    for crop in listed["crops"]:
        scene = _text(target, f"generated/scenes/farm/crops/{crop['id']}.tscn")
        assert "archetypes/farm/crop.gd" in scene and f'crop_id = "{crop["id"]}"' in scene
        assert f"generated/farm_kit/{crop['id']}.png" in scene and "hframes = 5" in scene
        assert 'type="Polygon2D"' not in scene, "the strip of the farm kit, five stages"
        for item in (crop["seed"], crop["produce"]):
            assert f'id = &"{item}"' in _text(target, f"game/data/items/{item}.tres")
    # the stand-in map: the starter map with a Soil layer, the field and a plot
    starter = _text(target, "game/maps/starter_map.tscn")
    assert "tilesets/farm_soil.tres" in starter and "archetypes/farm/field.gd" in starter
    assert (
        starter.index('name="Soil"')
        < starter.index('name="Field"')
        < starter.index('name="YSorted"')
    ), "the soil lies under what stands on the map"
    soil = _text(target, "generated/tilesets/farm_soil.tres")
    assert '"tillable"' in soil and '"water"' in soil
    assert soil.count("custom_data_0 = true") == 1, "one tile says it can be tilled"
    # tilled and watered soil are the tiles of the farm kit, each a source of its own
    assert "generated/farm_kit/soil.png" in soil and "generated/farm_kit/watered.png" in soil
    assert "tilled_source = 1" in starter and "watered_source = 2" in starter
    kit_notes = [i for i in _result.issues if i.code == "ASSET-031"]
    assert len(kit_notes) >= 9, "three crops, two tiles, four tools and more: each drawn, each said"
    # the tile set of the map is what a turn-based game of the pack has: nothing was added to it
    overworld = _text(target, "generated/tilesets/overworld.tres")
    assert "tillable" not in overworld


def test_a_second_run_changes_nothing(plain, godot_exe: Path) -> None:
    target, _result = plain
    crops = [f"generated/scenes/farm/crops/{name}.tscn" for name in ("berry", "carrot", "turnip")]
    kept = {
        rel: (target / rel).read_bytes()
        for rel in [*FILES, *crops, "game/data/new_game.tres", world_plan.PLAN_FILE, paths.LEDGER]
    }
    again = orchestrator.run_in_memory(_config(SAMPLE, "sample_pack"), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


# ---------------------------------------------------------------- the ranch pack


def test_the_growth_strips_of_the_ranch_pack_are_its_crops(ranch) -> None:
    target, _result = ranch
    assert _smoke(target)[-len(STEPS) :] == STEPS
    section = world_plan.load(target)["farm"]
    assert sorted(c["id"] for c in section["crops"]) == ["corn", "pumpkin", "tomato", "wheat"]
    assert section["notes"] == []
    by_id = {c["id"]: c for c in section["crops"]}
    assert (by_id["wheat"]["stages"], by_id["corn"]["stages"], by_id["tomato"]["stages"]) == (
        5,
        8,
        12,
    )
    assert (by_id["wheat"]["days"], by_id["corn"]["days"], by_id["tomato"]["days"]) == (4, 7, 11)
    assert crop_plan.check(section) == []
    schema.validate("crops", jsonio.read(target / "game/data/crops.json"))
    corn = _text(target, "generated/scenes/farm/crops/corn.tscn")
    assert "crops/corn_16x32_8frames.png" in corn and "hframes = 8" in corn
    assert 'type="Polygon2D"' not in corn, "the picture of the pack, not a stand-in"
    assert "crops/corn_16x32_8frames.png" in _text(target, "game/data/items/crop_corn.tres")
    # the tools of the pack are the icons of the items
    assert "tools/hoe_16x16.png" in _text(target, "game/data/items/hoe.tres")
    assert "tools/sickle_16x16.png" in _text(target, "game/data/items/sickle.tres")
    assert "tools/water_16x16.png" in _text(target, "game/data/items/watering_can.tres")
    assert "generated/farm_kit/axe.png" in _text(target, "game/data/items/farm_axe.tres"), (
        "the pack has no axe: the farm kit's"
    )
    # the pumpkin is one picture: the kit grew a strip of five stages that ends in it
    by_id = {c["id"]: c for c in section["crops"]}
    assert by_id["pumpkin"]["asset"] == "rpggen_farm_kit.grown.pumpkin_16x16"
    assert by_id["pumpkin"]["stages"] == 5
    assert "farm_kit/grown/pumpkin_16x16.png" in _text(
        target, "generated/scenes/farm/crops/pumpkin.tscn"
    )
    # the soil is the pack's own terrain sheets: of each, the tile that joins on every side
    soil = _text(target, "generated/tilesets/farm_soil.tres")
    assert "autotiles/01_soil_tilled" in soil or "soil_tilled" in soil
    assert "farm_kit/soil.png" not in soil
    starter = _text(target, "game/maps/starter_map.tscn")
    assert "tilled_source = 1" in starter and "tilled_tile = Vector2i(9, 2)" in starter


def test_the_recipe_writes_the_farmer_for_the_ranch_pack(ranch) -> None:
    target, _result = ranch
    player = _text(target, "generated/scenes/actors/player.tscn")
    assert "archetypes/farm/farmer.gd" in player
    assert "sprite_frames/ranch.characters.farmer." in player
    assert 'name="TileFrame"' in player and 'name="ToolIcon"' in player
