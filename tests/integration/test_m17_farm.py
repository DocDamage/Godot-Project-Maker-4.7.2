"""Milestone M17, the farm (T17.04 to T17.09): the top-down sample pack, which has nothing
made for the kind, as a farm with the crops, soil and tools of the drawn farm kit, and the
synthetic `ranch` pack, whose growth strips are its crops. Both wake in the farmhouse, walk to
the village and back, meet a villager, work the plot of the farm's plan, ship a harvest, sleep,
read the morning's summary and buy seeds at the shop."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import features, jsonio, paths, schema
from rpggen.core import (
    config,
    crop_plan,
    farm_plan,
    ledger,
    orchestrator,
    people_plan,
    profiles,
    world_plan,
)

pytestmark = [pytest.mark.integration, pytest.mark.farm]

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
RANCH = REPO / "test_packs" / "synthetic" / "ranch"
# a new game starts in the farmhouse: out of it, and to the village, where the shared top-down
# steps run
HOUSE_STEPS = ["wake_in_the_house", "walk_out_of_the_house", "go_to_the_village"]
# the farm's own steps after them: the people, then the farm
STEPS = [
    "villager_by_the_clock",
    "give_a_gift",
    "back_to_the_farm",
    "farm_is_there",
    "fill_the_can",
    "clear_debris",
    "till_a_cell",
    "plant_a_seed",
    "water_it",
    "a_night_grows_it",
    "crop_ripens",
    "harvest",
    "ship_the_crop",
    "sleep_in_the_bed",
    "morning_summary",
    "buy_seeds_at_the_shop",
    "rain_waters_the_field",
    "hud_shows_the_day",
    "season_turns",
]
TOOLS = ("hoe", "watering_can", "sickle", "farm_axe")
START_TOOLS = ("hoe", "watering_can")  # the other two are bought at the shop (T17.08)
FILES = [
    "generated/scenes/combat/combat_mode.tscn",
    "generated/scenes/actors/player.tscn",
    "generated/tilesets/farm_soil.tres",
    "generated/data/crops.json",
    "game/data/crops.json",
    "game/maps/starter_map.tscn",
    "game/maps/farm.tscn",
    "game/maps/farm_house.tscn",
    "generated/data/people.json",
    "game/data/people.json",
    "generated/scenes/farm/shipping_bin.tscn",
    "generated/scenes/farm/bed.tscn",
    "game/data/shops/village_shop.tres",
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
    assert names[0] == "title_new_game" and names[1:4] == HOUSE_STEPS
    assert names.index("go_to_the_village") < names.index("map_music"), "then the village's steps"
    assert names.index("pause_menu") < names.index(STEPS[0])
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
    # a new game starts with a hoe, a can and the seeds of the first crop, the first slots
    new_game = _text(target, "game/data/new_game.tres")
    first = jsonio.read(target / "game/data/crops.json")["crops"][0]
    order = [new_game.index(f'"{item}"') for item in (*START_TOOLS, first["seed"], "potion")]
    assert order == sorted(order)
    assert '"sickle"' not in new_game and '"farm_axe"' not in new_game
    assert '"qty": 15' in new_game, "fifteen seeds"
    assert f"gold = {config.FARM_STARTING_MONEY}" in new_game, "a little money"
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
    crops_only = {k: v for k, v in section.items() if k not in ("map", "people")}
    assert crops_only == crop_plan.plan({}, 12345, kit), "the plan of the seed, of the kit's crops"
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
    # the farm's own map has the Soil layer, the field and the plot; the village has none
    starter = _text(target, "game/maps/farm.tscn")
    assert "tilesets/farm_soil.tres" in starter and "archetypes/farm/field.gd" in starter
    assert (
        starter.index('name="Soil"')
        < starter.index('name="Field"')
        < starter.index('name="YSorted"')
    ), "the soil lies under what stands on the map"
    village = _text(target, "game/maps/starter_map.tscn")
    assert "farm_soil" not in village and "field.gd" not in village
    soil = _text(target, "generated/tilesets/farm_soil.tres")
    assert '"tillable"' in soil and '"water"' in soil
    assert soil.count("custom_data_0 = true") == 1, "one tile says it can be tilled"
    assert soil.count("custom_data_1 = true") == 2, "two fill the can: drawn water, and a mark"
    # tilled and watered soil are the tiles of the farm kit, each a source of its own
    assert "generated/farm_kit/soil.png" in soil and "generated/farm_kit/watered.png" in soil
    assert "tilled_source = 1" in starter and "watered_source = 2" in starter
    kit_notes = [i for i in _result.issues if i.code == "ASSET-031"]
    assert len(kit_notes) >= 9, "three crops, two tiles, four tools and more: each drawn, each said"
    # the tile set of the map is what a turn-based game of the pack has: nothing was added to it
    overworld = _text(target, "generated/tilesets/overworld.tres")
    assert "tillable" not in overworld


def test_the_bin_the_bed_and_the_shop_of_a_farm(plain) -> None:
    target, _result = plain
    # the two scenes, with the pictures of the drawn farm kit (the sample pack has neither)
    bin_scene = _text(target, "generated/scenes/farm/shipping_bin.tscn")
    assert "archetypes/farm/shipping_bin.gd" in bin_scene and 'type="StaticBody2D"' in bin_scene
    assert "generated/farm_kit/shipping_bin.png" in bin_scene
    bed = _text(target, "generated/scenes/farm/bed.tscn")
    assert "archetypes/farm/bed.gd" in bed and "generated/farm_kit/bed.png" in bed
    # a tile wide and two long, awake in the cell under its foot: the defaults of RpgBed, so
    # the scene does not repeat them
    assert "footprint" not in bed and "wake_offset" not in bed
    assert "size = Vector2(14.4, 28.8)" in bed, "all of the bed blocks"
    for scene in (bin_scene, bed):
        assert "collision_layer = 17" in scene, "the world and the interactables"
    # the bin stands on the farm and the bed in the farmhouse, among the things that Y-sort
    # with the farmer; the village has neither
    farm = _text(target, "game/maps/farm.tscn")
    house = _text(target, "game/maps/farm_house.tscn")
    assert farm.count("scenes/farm/shipping_bin.tscn") == 1
    assert house.count("scenes/farm/bed.tscn") == 1
    assert 'name="ShippingBin" parent="YSorted/Entities"' in farm
    assert 'name="Bed" parent="YSorted/Entities"' in house
    assert "wake_offset = Vector2(16, -8)" in house, "the farmer wakes in the cell east of it"
    village = _text(target, "game/maps/starter_map.tscn")
    assert "scenes/farm/" not in village
    # the village shop is the farm's: hours, the tools a new game lacks, the item's price
    shop = _text(target, "game/data/shops/village_shop.tres")
    assert "archetypes/farm/farm_shop.gd" in shop and 'id = &"village_shop"' in shop
    for item in ("potion", "sickle", "farm_axe"):
        assert f'"item_id": "{item}"' in shop, item
    assert "sell_ratio = 1.0" in shop
    assert "seed_" not in shop, "the seeds of the season are added by the game, from its crops"
    files = ledger.Ledger.load(target / paths.LEDGER).files
    assert files["game/data/shops/village_shop.tres"].owner == "user_seed"
    assert files["generated/scenes/farm/bed.tscn"].owner == "generated"
    # the default option is the default of the mode: its scene does not say it
    assert "pass_out_loss" not in _text(target, "generated/scenes/combat/combat_mode.tscn")
    strings = _text(target, "game/i18n/strings.tsv")
    assert "FARM_SUMMARY_TITLE\t" in strings and "FARM_SHOP_CLOSED_DAY\t" in strings


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


# ---------------------------------------------------------------- the farm's own map (T17.06)


def _nodes(scene: str, prefix: str) -> list[str]:
    """The names of the nodes of a saved scene that begin with ``prefix``."""
    return [
        line.split('"')[1]
        for line in scene.splitlines()
        if line.startswith(f'[node name="{prefix}')
    ]


def test_the_farm_is_built_from_its_stored_plan(plain) -> None:
    target, result = plain
    stored = farm_plan.stored_in(world_plan.load(target))
    assert stored is not None and stored["seed"] == 12345 and stored["map"] == "game/maps/farm.tscn"
    assert farm_plan.check(stored) == []
    assert not [i for i in result.issues if i.code == "VAL-031"]
    assert farm_plan.exists(target)
    defaults = farm_plan.defaults()
    assert [stored[k] for k in ("farm_size", "plot", "animals", "difficulty")] == [
        defaults[k] for k in ("farm_size", "plot", "animals", "difficulty")
    ]
    # the house is the pack's building, on the footprint the plan took from the catalog
    assert stored["house"]["rect"][2:] == [5, 4] and stored["water"]["kind"] == "pond"
    farm = _text(target, "game/maps/farm.tscn")
    assert "world/map_root.gd" in farm and 'map_id = &"farm"' in farm
    assert '[node name="House" parent="YSorted/Entities"' in farm, "an instance of its scene"
    assert 'target_map = "res://game/maps/farm_house.tscn"' in farm
    assert 'spawn_id = &"farm_house_door"' in farm
    # one thing for every thing of the plan (the smoke step `farm_is_there` holds the tillable
    # cells of the scene to the plan's, and `clear_debris` the things to clear)
    debris = [f"Debris_{d['cell'][0]}_{d['cell'][1]}" for d in stored["debris"]]
    assert sorted(_nodes(farm, "Debris_")) == sorted(debris)
    assert farm.count('metadata/farm_clear = "') == len(debris)
    assert farm.count('entity_id = "farm_debris_') == len(debris)
    assert len(_nodes(farm, "Tree")) == len(stored["trees"])
    scenery = [n for kind in ("Bush", "Rock", "Flowers") for n in _nodes(farm, kind)]
    assert len(scenery) == len(stored["scenery"])
    assert len(_nodes(farm, "Cell_")) == len(stored["water"]["cells"]), "the water is solid"
    assert (
        "archetypes/farm/water_source.gd" in farm
        and 'name="WaterFill" type="Marker2D" parent="Markers"' in farm
    )
    assert (
        'name="BinFront" type="Marker2D" parent="Markers"' in farm and 'name="WeatherSign"' in farm
    )
    # the way out and the village's side of it
    assert '[node name="to_village" type="Area2D" parent="Triggers"' in farm
    assert 'target_map = "res://game/maps/starter_map.tscn"' in farm
    assert 'target_spawn = &"from_farm"' in farm and 'spawn_id = &"from_village"' in farm
    village = _text(target, "game/maps/starter_map.tscn")
    assert '[node name="to_farm" type="Area2D" parent="Triggers"' in village
    assert 'target_map = "res://game/maps/farm.tscn"' in village
    assert 'target_spawn = &"from_village"' in village and 'spawn_id = &"from_farm"' in village
    # the farmhouse: the room of the plan, an inside map, where a new game starts
    room = stored["house"]["interior"]
    house = _text(target, "game/maps/farm_house.tscn")
    assert 'map_id = &"farm_house"' in house and "is_interior = true" in house
    assert 'spawn_id = &"start"' in house and 'target_spawn = &"farm_house_door"' in house
    tile = 16
    start = stored["start"]["cell"]
    spot = f"position = Vector2({start[0] * tile + tile // 2}, {start[1] * tile + tile // 2})"
    assert spot in house, "the spawn `start` is on the plan's cell"
    assert stored["start"]["map"] == room["id"] == "farm_house"
    new_game = _text(target, "game/data/new_game.tres")
    assert 'start_map = "res://game/maps/farm_house.tscn"' in new_game
    assert 'start_spawn = &"start"' in new_game
    files = ledger.Ledger.load(target / paths.LEDGER).files
    for rel in ("game/maps/farm.tscn", "game/maps/farm_house.tscn", "game/data/people.json"):
        assert files[rel].owner == "user_seed", rel
    # the picture of the Results page: the farm's plan beside the village
    from PIL import Image

    with Image.open(target / "rpggen/results/starter_map.png") as picture:
        assert picture.width > 2 * 640, "two maps side by side"
    assert (target / "generated/minimaps/game__maps__farm.tres").is_file()


def test_the_people_of_the_village(plain) -> None:
    target, _result = plain
    people = world_plan.load(target)["farm"]["people"]
    assert [p["asset"] for p in people] == ["sample_pack.characters.npc_villager"]
    assert people_plan.check(people) == []
    listed = jsonio.read(target / "game/data/people.json")
    schema.validate("people", listed)
    assert listed == jsonio.read(target / "generated/data/people.json")
    # what the builder writes is the planner's file, each person with the spots that are its own
    expected = []
    for index, person in enumerate(people):
        places = {
            "home": [{"map": "starter_map", "place": _spot("home_1", index % 4)}],
            "square": {"map": "starter_map", "place": _spot("square", index % 6)},
            "work": {"map": "starter_map", "place": "work"},
        }
        scene = "res://generated/scenes/actors/characters/" + person["asset"].replace(".", "__")
        entry = people_plan.people_file([person], places, {person["id"]: scene + ".tscn"})
        expected += entry["people"]
    assert listed == {"people": expected}
    # every place a schedule names is a marker of the village
    village = _text(target, "game/maps/starter_map.tscn")
    named = {e["place"] for p in listed["people"] for e in p["schedule"]}
    assert named and all(e["map"] == "starter_map" for p in listed["people"] for e in p["schedule"])
    for place in named:
        assert f'[node name="{place}" type="Marker2D" parent="Places"' in village, place
        assert f'metadata/place = "{place}"' in village
    assert village.count('groups=["rpg_place"]') == 4 + 1 + 6 + 1, "home, its alias, square, work"
    # one NPC a person, with its schedule and what it says; the demo's villager stays
    for person in listed["people"]:
        who = person["id"]
        assert f'[node name="Person_{who}" parent="YSorted/Entities"' in village
        assert f'entity_id = "person_{who}"' in village and f'person = "{who}"' in village
        assert (
            f'[node name="Schedule" type="Node" parent="YSorted/Entities/Person_{who}"' in village
        )
        talk = _text(target, f"game/data/dialogue/person_{who}.tres")
        assert f"friendship:{who}>=2" in talk and f"not friendship:{who}>=2" in talk
    assert village.count("actors/schedule.gd") == 1
    assert 'entity_id = "starter_map_npc_001"' in village
    assert "archetypes/farm/friendship.gd" not in _text(
        target, "generated/scenes/combat/combat_mode.tscn"
    ), "the mode makes the friendships when the game runs"


def _spot(place: str, index: int) -> str:
    return place if index == 0 else f"{place}_{index + 1}"


def test_a_stored_plan_that_was_broken_by_hand_is_reported(plain, godot_exe: Path) -> None:
    """``VAL-031``: the farm's map exists, so its plan is not made again; what keeps it from
    being worked is said, a line a problem. The smoke run then finds that the map is no longer
    the plan's, and the project stays as it was."""
    target, _result = plain
    plan_file = target / world_plan.PLAN_FILE
    before = plan_file.read_bytes()
    farm_map = (target / "game/maps/farm.tscn").read_bytes()
    broken = jsonio.read(plan_file)
    broken["farm"]["map"]["tillable"] = broken["farm"]["map"]["tillable"][:5]
    jsonio.write(plan_file, broken)
    try:
        again = orchestrator.run_in_memory(_config(SAMPLE, "sample_pack"), None, target, godot_exe)
        found = [i.message for i in again.issues if i.code == "VAL-031"]
        assert found and "the plot has 5 cells, 12 are needed" in found[0]
        smoke = [i.message for i in again.issues if i.code == "SMOKE-013"]
        assert not again.ok and smoke and "is not in the plan" in smoke[0], _errors(again)
        kept = world_plan.load(target)["farm"]["map"]
        assert len(kept["tillable"]) == 5, "the stored plan is reported, not replaced"
        assert (target / "game/maps/farm.tscn").read_bytes() == farm_map, "the map is not rebuilt"
    finally:
        plan_file.write_bytes(before)


# ---------------------------------------------------------------- the ranch pack


def test_the_growth_strips_of_the_ranch_pack_are_its_crops(ranch) -> None:
    target, _result = ranch
    assert _smoke(target)[-len(STEPS) :] == STEPS
    section = world_plan.load(target)["farm"]
    assert sorted(c["id"] for c in section["crops"]) == ["corn", "pumpkin", "tomato", "wheat"]
    # the pack has no building object: the village has no house, and the people's plan says so
    assert section["notes"] == ["The village has no house: everybody lives in house 1."]
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
    farm = _text(target, "game/maps/farm.tscn")
    assert "tilled_source = 1" in farm and "tilled_tile = Vector2i(9, 2)" in farm
    # the pack has no water tile and no building object: a well, and a house that is drawn
    stored = farm_plan.stored_in(world_plan.load(target))
    assert stored["water"]["kind"] == "well" and farm_plan.check(stored) == []
    assert 'kind = "well"' in farm and '[node name="House" type="StaticBody2D"' in farm
    assert '[node name="HouseDoor" type="Area2D" parent="Triggers"' in farm
    schema.validate("people", jsonio.read(target / "game/data/people.json"))


def test_the_recipe_writes_the_farmer_for_the_ranch_pack(ranch) -> None:
    target, _result = ranch
    player = _text(target, "generated/scenes/actors/player.tscn")
    assert "archetypes/farm/farmer.gd" in player
    assert "sprite_frames/ranch.characters.farmer." in player
    assert 'name="TileFrame"' in player and 'name="ToolIcon"' in player


# ---------------------------------------------------------------- the weather and the HUD (T17.11)


def test_the_mode_has_the_weather_and_the_hud_and_the_project_its_readme(plain) -> None:
    target, _result = plain
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "archetypes/farm/weather.gd" in mode and 'name="Weather"' in mode
    assert "enabled = true" in mode, "the weather of a generated farm is switched on"
    assert "generated/farm_kit/rain.png" in mode, "the pack has no rain: the farm kit's"
    for part in ("Clock", "Date", "Weather", "WeatherIcon", "Money", "EnergyBar", "Slots"):
        assert f'name="{part}"' in mode, part
    # the sample has no sheet once a season: the table is there and empty
    assert jsonio.read(target / "generated/data/seasons.json") == {"groups": {}, "version": 1}
    sign = _text(target, "generated/scenes/farm/weather_sign.tscn")
    assert "archetypes/farm/weather_sign.gd" in sign and "collision_layer = 17" in sign
    strings = _text(target, "game/i18n/strings.tsv")
    assert "FARM_WEATHER_RAIN\t" in strings and "FARM_FORECAST\t" in strings
    readme = _text(target, "README.md")
    assert "**This game is a farm**" in readme
    assert "## 22. Days, crops, the shop and the people (farm)" in readme
    assert readme.count("## 22.") == 1
    crops = {c["id"]: c for c in jsonio.read(target / "game/data/crops.json")["crops"]}
    shown = json.loads(readme.split("```json\n")[1].split("\n```")[0])
    assert crops[shown["id"]] == shown, "the crop the README shows is a crop of this game"
