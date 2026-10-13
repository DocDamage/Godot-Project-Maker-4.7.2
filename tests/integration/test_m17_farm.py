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
    animal_plan,
    config,
    crop_plan,
    farm_plan,
    forage_plan,
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
    "forage_on_the_farm",
    "catch_a_fish",
]
# the steps of the animals (T17.07), after all the others: in a farm without an animal house each
# passes with a note
ANIMAL_STEPS = [
    "buy_a_hen",
    "hen_in_the_coop",
    "feed_at_the_trough",
    "pet_the_hen",
    "egg_in_the_morning",
    "ship_the_egg",
]
TOOLS = ("hoe", "watering_can", "sickle", "farm_axe", "fishing_rod")
START_TOOLS = ("hoe", "watering_can")  # the others are bought at the shop (T17.08, T17.10)
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
    "generated/data/forage.json",
    "game/data/forage.json",
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
    assert names[-len(STEPS + ANIMAL_STEPS) :] == STEPS + ANIMAL_STEPS
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
        "rod",
        "sickle",
        "watering_can",
    ]
    for name in ("forage", "forage_pickup", "fishing", "ui/fishing_bar"):  # T17.10
        assert (archetypes / "farm" / f"{name}.gd").is_file(), name
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
    crops_only = {k: v for k, v in section.items() if k not in ("map", "people", "forage")}
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
    assert _smoke(target)[-len(STEPS + ANIMAL_STEPS) :] == STEPS + ANIMAL_STEPS
    section = world_plan.load(target)["farm"]
    assert sorted(c["id"] for c in section["crops"]) == ["corn", "pumpkin", "tomato", "wheat"]
    # the pack has nobody but the farmer (its strips of the farmer hoeing and watering are
    # animations of the farmer, not villagers) and no building object: the people's plan says so
    assert section["notes"] == [
        "The packs have no NPC: 3 people share the stand-in.",
        "The village has no house: everybody lives in house 1.",
    ]
    assert [p["asset"] for p in section["people"]] == ["", "", ""]
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


# ---------------------------------------------------------------- fishing and foraging (T17.10)


def _forage_markers(target: Path) -> list[tuple[int, int]]:
    """The cells of the markers ``Forage/Spot<n>`` of the farm's map, by their number."""
    lines = _text(target, "game/maps/farm.tscn").splitlines()
    assert any(line.startswith('[node name="Forage" type="Node2D" parent="."') for line in lines)
    found: dict[int, tuple[int, int]] = {}
    for at, line in enumerate(lines):
        if line.startswith('[node name="Spot') and 'parent="Forage"' in line:
            assert 'type="Marker2D"' in line
            x, y = lines[at + 1].removeprefix("position = Vector2(").rstrip(")").split(", ")
            assert float(x) % 16 == 8 and float(y) % 16 == 8, "the middle of a cell"
            found[int(line.split('"')[1].removeprefix("Spot"))] = (
                int(float(x)) // 16,
                int(float(y)) // 16,
            )
    assert sorted(found) == list(range(1, len(found) + 1))
    return [found[n] for n in sorted(found)]


@pytest.mark.parametrize("which", ["plain", "ranch"])
def test_the_forage_places_are_markers_on_free_cells_of_the_plan(
    which: str, request: pytest.FixtureRequest
) -> None:
    target, _result = request.getfixturevalue(which)
    farm = world_plan.load(target)["farm"]
    section = forage_plan.stored_in(world_plan.load(target))
    assert section is not None and forage_plan.check(section) == []
    spots = [tuple(c) for c in section["spots"]]
    assert len(spots) == forage_plan.SPOTS[farm["map"]["farm_size"]]
    assert _forage_markers(target) == spots, "the markers are the plan's places, in their order"
    free = set(forage_plan.free_cells(farm["map"]))
    walkable = farm_plan.reached_cells(farm["map"])
    taken = {tuple(c) for key in ("tillable", "paths", "trees") for c in farm["map"][key]}
    for spot in spots:
        assert spot in free and spot in walkable and spot not in taken, spot
    assert spots == [tuple(c) for c in forage_plan.spots_for(farm["map"], section["seed"])]
    # the table: the planned file on every build, the user's once, an item for every entry
    planned = jsonio.read(target / "generated/data/forage.json")
    own = jsonio.read(target / "game/data/forage.json")
    schema.validate("forage", planned)
    schema.validate("forage", own)
    assert own == forage_plan.forage_file(section)
    assert planned["spots"] == section["spots"] and planned["map"] == "farm"
    assert planned["fishing"] is section["fishing"]
    files = ledger.Ledger.load(target / paths.LEDGER).files
    assert files["generated/data/forage.json"].owner == "generated"
    assert files["game/data/forage.json"].owner == "user_seed"
    for row in [*section["forage"], *section["fish"]]:
        item = _text(target, f"game/data/items/{row['item']}.tres")
        assert f'id = &"{row["item"]}"' in item and f"value = {row['price']}" in item
        assert row["asset"].startswith("rpggen_farm_kit."), "neither pack has a fish of its own"
        assert f"generated/farm_kit/{row['asset'].split('.', 1)[1]}.png" in item
        assert files[f"game/data/items/{row['item']}.tres"].owner == "user_seed"
    assert len(section["forage"]) == 4 and len(section["fish"]) == 3
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "forage.gd" not in mode and "fishing.gd" not in mode, "the mode makes the two itself"
    strings = _text(target, "game/i18n/strings.tsv")
    assert "FARM_FISH_CAUGHT\t" in strings and "ITEM_FISHING_ROD_NAME\t" in strings


def test_the_rod_is_sold_where_the_farm_has_a_pond_and_not_otherwise(plain, ranch) -> None:
    """The top-down sample has water tiles, so its farm has a pond and its shop the rod; the
    ranch has none, so its farm has a well, no rod in the shop, and its smoke step passes
    without a cast."""
    for (target, _result), kind in ((plain, "pond"), (ranch, "well")):
        farm = world_plan.load(target)["farm"]
        assert farm["map"]["water"]["kind"] == kind
        assert farm["forage"]["fishing"] is (kind == "pond")
        shop = _text(target, "game/data/shops/village_shop.tres")
        assert ('"item_id": "fishing_rod"' in shop) is (kind == "pond"), kind
        # the rod is an item of every farm: only the shop differs
        rod = _text(target, "game/data/items/fishing_rod.tres")
        assert 'id = &"fishing_rod"' in rod and "generated/farm_kit/fishing_rod.png" in rod
        assert "fishing_rod" not in _text(target, "game/data/new_game.tres"), "it is bought"
        log = _text(target, "rpggen/logs/godot_smoke.log")
        assert ("catch_a_fish: the farm has no pond" in log) is (kind == "well")
        assert "catch_a_fish" in _smoke(target)
    assert config.starter_map_defaults("farm")["fishing"] is True


# ---------------------------------------------------------------- the animals (T17.07)


def _animal_farm(source: Path, pack_id: str, animals: str, target: Path, godot_exe: Path):
    cfg = _config(source, pack_id)
    cfg.starter_map["animals"] = animals
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


@pytest.fixture(scope="module")
def coop(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    """The top-down sample as a farm with a coop: it has no animal, so the kit's hen."""
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    target = tmp_path_factory.mktemp("m17_coop") / "out"
    return _animal_farm(SAMPLE, "sample_pack", "coop", target, godot_exe)


@pytest.fixture(scope="module")
def barn(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    """The ranch pack as a farm with a coop and a barn: its own hens and cows, in three colours."""
    target = tmp_path_factory.mktemp("m17_barn") / "out"
    return _animal_farm(RANCH, "ranch", "coop_and_barn", target, godot_exe)


def _animal_notes(target: Path) -> list[str]:
    """What the animals' smoke steps said of themselves (``INFO <step>: ...``)."""
    log = _text(target, "rpggen/logs/godot_smoke.log")
    return [
        line
        for line in log.splitlines()
        if "[rpggen] INFO " in line and any(f"INFO {step}:" in line for step in ANIMAL_STEPS)
    ]


def _animal_files(target: Path) -> tuple[dict, dict, dict]:
    """(the animals of the plan, the farm's map of the plan, game/data/animals.json), checked
    against each other: the file is what the planner says it is, and the planned copy is the
    same."""
    farm = world_plan.load(target)["farm"]
    animals = farm["animals"]
    assert animal_plan.check(animals) == []
    listed = jsonio.read(target / animal_plan.ANIMALS_FILE)
    schema.validate("animals", listed)
    assert jsonio.read(target / animal_plan.PLANNED_FILE) == listed
    scenes = {
        f"{kind['id']}.{variant['id']}": (
            f"res://generated/scenes/farm/animals/{kind['id']}__{variant['id']}.tscn"
        )
        for kind in animals["kinds"]
        for variant in kind["variants"]
    }
    assert listed == animal_plan.animals_file(animals, animal_plan.houses_of(farm["map"]), scenes)
    files = ledger.Ledger.load(target / paths.LEDGER).files
    assert files[animal_plan.ANIMALS_FILE].owner == "user_seed"
    assert files[animal_plan.PLANNED_FILE].owner == "generated"
    for scene in scenes.values():
        rel = scene.removeprefix("res://")
        assert "archetypes/farm/animal.gd" in _text(target, rel), rel
        assert files[rel].owner == "generated"
    for kind in animals["kinds"]:
        for item, price in (
            (kind["product"], kind["price"]),
            (kind["large"], kind["large_price"]),
            (kind["ticket"], kind["cost"]),
            (animals["feed"]["item"], animals["feed"]["price"]),
        ):
            text = _text(target, f"game/data/items/{item}.tres")
            assert f'id = &"{item}"' in text, item
            # a price of 10 is the default of an item, and a saved resource leaves defaults out
            assert f"value = {price}" in text or price == 10, item
            assert files[f"game/data/items/{item}.tres"].owner == "user_seed"
        # the row of the shop is a key item: it is never in the bag, the bin or a sale
        assert "category = 5" in _text(target, f"game/data/items/{kind['ticket']}.tres")
    return animals, farm["map"], listed


def _house_rooms(target: Path, farm_map: dict) -> None:
    """Every animal house of the plan is on the farm with its yard, and has its room with the
    trough and a marker for every stall."""
    farm = _text(target, "game/maps/farm.tscn")
    for building in farm_map["animal_houses"]:
        kind = building["kind"]
        name = kind.capitalize()
        assert f'[node name="{name}" type="Node2D" parent="Yards"' in farm, kind
        assert f'metadata/house_map = "res://game/maps/farm_{kind}.tscn"' in farm
        assert f"metadata/stalls = {len(building['interior']['stalls'])}" in farm
        assert f'[node name="Gate_{kind}"' in farm
        assert len(_nodes(farm, f"Fence_{kind}_")) == len(building["yard"]["fence"])
        room = _text(target, f"game/maps/farm_{kind}.tscn")
        assert "is_interior = true" in room
        assert '[node name="Trough"' in room
        stalls = len(building["interior"]["stalls"])
        assert _nodes(room, "Stall") == [f"Stall{n + 1}" for n in range(stalls)]
        assert "archetypes/farm/trough.gd" not in room, (
            "the trough is made when the room is entered"
        )


def test_a_farm_with_a_coop_keeps_the_drawn_hen(coop) -> None:
    target, _result = coop
    names = _smoke(target)
    assert names[-len(ANIMAL_STEPS) :] == ANIMAL_STEPS
    assert _animal_notes(target) == [], "every step of the animals did its work"
    animals, farm_map, listed = _animal_files(target)
    assert farm_map["animals"] == "coop"
    assert [b["kind"] for b in farm_map["animal_houses"]] == ["coop"]
    _house_rooms(target, farm_map)
    assert not (target / "game/maps/farm_barn.tscn").exists()
    # the sample pack has no animal: the hen is the farm kit's, in the one colour it is drawn in
    assert [k["id"] for k in animals["kinds"]] == ["hen"]
    hen = animals["kinds"][0]
    assert (hen["house"], hen["product"], hen["collect"]) == ("coop", "egg", "floor")
    assert hen["variants"] == [
        {"id": "hen", "colour": "", "asset": "rpggen_farm_kit.hen", "sleep": ""}
    ]
    assert animals["notes"] == []
    assert listed["houses"] == [
        {
            "kind": "coop",
            "map": "res://game/maps/farm_coop.tscn",
            "yard_map": "res://game/maps/farm.tscn",
            "stalls": farm_plan.STALLS["coop"],
        }
    ]
    scene = _text(target, "generated/scenes/farm/animals/hen__hen.tscn")
    assert 'kind = "hen"' in scene and "sprite_frames/rpggen_farm_kit.hen.tres" in scene
    assert "collision_layer = 16" in scene, "the interactables: found by `interact`, walked through"
    # the egg is the farm kit's picture, the hen's row its first frame
    assert "generated/farm_kit/egg.png" in _text(target, "game/data/items/egg.tres")
    assert "generated/farm_kit/hen.png" in _text(target, "game/data/items/animal_hen.tres")
    # the shop's own file lists neither: the game adds the rows while a house has room
    shop = _text(target, "game/data/shops/village_shop.tres")
    assert "animal_hen" not in shop and '"hay"' not in shop
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "animal_house.gd" not in mode, "the mode makes its part itself"
    readme = _text(target, "README.md")
    assert "### Animals" in readme and "game/data/animals.json" in readme


def test_a_ranch_with_a_coop_and_a_barn_keeps_its_hens_and_cows(barn) -> None:
    target, _result = barn
    names = _smoke(target)
    assert names[-len(ANIMAL_STEPS) :] == ANIMAL_STEPS
    assert _animal_notes(target) == [], "a hen and a cow were bought, fed, petted and gave"
    animals, farm_map, listed = _animal_files(target)
    assert [b["kind"] for b in farm_map["animal_houses"]] == ["coop", "barn"]
    _house_rooms(target, farm_map)
    assert [(k["id"], k["house"], k["collect"]) for k in animals["kinds"]] == [
        ("hen", "coop", "floor"),
        ("cow", "barn", "hand"),
    ]
    assert [h["kind"] for h in listed["houses"]] == ["coop", "barn"]
    for kind, cell in (("hen", "16x16"), ("cow", "32x32")):
        entry = next(k for k in animals["kinds"] if k["id"] == kind)
        # its colour variants, each with the strip it walks in and the one it sleeps in
        assert [v["colour"] for v in entry["variants"]] == ["black", "brown", "white"]
        for variant in entry["variants"]:
            colour = variant["colour"]
            assert variant["id"] == f"{kind}_01_{colour}"
            assert variant["asset"].endswith(f"{kind}_01_{colour}_move_down_{cell}_4frames")
            assert variant["sleep"].endswith(f"{kind}_01_{colour}_sleep_{cell}_2frames")
            scene = _text(target, f"generated/scenes/farm/animals/{kind}__{variant['id']}.tscn")
            assert f'kind = "{kind}"' in scene
            assert '&"walk_down"' in scene and '&"sleep_down"' in scene, variant["id"]
            assert f"{kind}_01_{colour}_move_down_{cell}_4frames.png" in scene
            assert f"{kind}_01_{colour}_sleep_{cell}_2frames.png" in scene
    # the pack draws neither an egg nor milk: the kit's egg, and a drawn bottle of nothing
    assert "generated/farm_kit/egg.png" in _text(target, "game/data/items/egg.tres")
    assert 'id = &"milk"' in _text(target, "game/data/items/milk.tres")
    assert "cow_01_black_move_down_32x32_4frames.png" in _text(
        target, "game/data/items/animal_cow.tres"
    )


def test_a_farm_without_animals_has_nothing_of_them(plain, ranch) -> None:
    """``animals: none``, the default: no house, no plan of animals, no file of theirs; the
    steps of the animals pass with a note each. What such a farm has of this card is the code
    (inert), its lines in the translations and the part of the README."""
    for target, _result in (plain, ranch):
        farm = world_plan.load(target)["farm"]
        assert farm["map"]["animals"] == "none" and farm["map"]["animal_houses"] == []
        assert "animals" not in farm
        for rel in (
            animal_plan.ANIMALS_FILE,
            animal_plan.PLANNED_FILE,
            "generated/scenes/farm/animals",
            "game/maps/farm_coop.tscn",
            "game/maps/farm_barn.tscn",
            "game/data/items/hay.tres",
            "game/data/items/egg.tres",
            "game/data/items/animal_hen.tres",
        ):
            assert not (target / rel).exists(), rel
        assert "Yards" not in _text(target, "game/maps/farm.tscn")
        notes = _animal_notes(target)
        assert len(notes) == len(ANIMAL_STEPS), notes
        assert all("the farm has no animal house, step passes" in line for line in notes)
        assert (target / "addons/rpg_runtime/archetypes/farm/animal_house.gd").is_file()
        assert "FARM_TROUGH_FULL\t" in _text(target, "game/i18n/strings.tsv")
        assert "### Animals" in _text(target, "README.md")


# ---------------------------------------------------------------- Green acre, the sample (T17.17)
#
# The farm's own sample pack, made the way *Try the sample* makes it: the bundled profile, the
# starter the catalog suggests, the default options. It has what a farm works with, so nothing
# is drawn for it and the report has no note; and with a coop and a barn its own hen and cow.

GREEN_ACRE = REPO / "sample_pack_farm"
SAMPLE_NOTES = {"ADAPT-003"}  # what a sample may say: that its profile was found
PACK_CROPS = ("corn", "tomato", "turnip", "wheat")


def _sample_config(**starter_map) -> config.GeneratorConfig:
    from rpggen.core import archive, catalog, inventory, mapping
    from rpggen.gui.models import project_model

    sample = project_model.sample("farm")
    assert (sample.key, sample.archetype, sample.projection) == ("farm", "farm", "top_down")
    pack = REPO / sample.folder
    assert pack == GREEN_ACRE
    profiles.install_profile(pack / sample.profile)
    opened = archive.open_pack(pack, set(), pack_id=sample.folder)
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        sample.name, [config.pack_ref_from_source(pack, sample.folder)], archetype="farm"
    )
    cfg.starter = mapping.default_starter(cat, sample.archetype, sample.projection)
    cfg.starter_map = dict(starter_map)
    return cfg


@pytest.fixture(scope="module")
def green_acre(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m17_acre") / "out"
    result = orchestrator.run_in_memory(_sample_config(), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


@pytest.fixture(scope="module")
def green_acre_animals(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m17_acre_animals") / "out"
    cfg = _sample_config(animals="coop_and_barn")
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _sample_notes(result) -> list[str]:
    """What the report says that a sample may not say (what the computer lacks is not its)."""
    return sorted(
        f"{i.code}: {i.message}"
        for i in result.issues
        if not i.code.startswith("ENV-")
        and (i.severity.value != "info" or i.code not in SAMPLE_NOTES)
    )


def _vacuous(target: Path) -> list[str]:
    """The steps that passed only because the game had nothing of theirs."""
    log = _text(target, "rpggen/logs/godot_smoke.log")
    return [
        line.split("INFO ", 1)[1].split(":", 1)[0]
        for line in log.splitlines()
        if "step passes" in line and "INFO " in line
    ]


def test_green_acre_is_a_farm_that_is_worked_from_seed_to_sale(green_acre) -> None:
    target, result = green_acre
    names = _smoke(target)
    assert names[0] == "title_new_game" and names[1:4] == HOUSE_STEPS
    assert names[-len(STEPS + ANIMAL_STEPS) :] == STEPS + ANIMAL_STEPS
    assert "npc_dialogue" in names and "chest_open" in names and "enter_building" in names
    # every step is played: only the animals' pass with a note, in a farm without their houses
    assert _vacuous(target) == ANIMAL_STEPS
    assert "SCRIPT ERROR" not in _text(target, "rpggen/logs/godot_smoke.log")
    assert _sample_notes(result) == [], "nothing is missing, and nothing is drawn"
    assert not [i for i in result.issues if i.code == "ASSET-031"]
    assert not (target / "generated/farm_kit").exists(), "the kit drew nothing"
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "farm" and "projection" not in saved


def test_green_acre_is_made_of_its_own_pictures(green_acre) -> None:
    target, _result = green_acre
    pack = "res://assets/packs/sample_pack_farm/"
    # the four crops of the pack, each from its strip, two in every season
    farm = world_plan.load(target)["farm"]
    assert sorted(c["id"] for c in farm["crops"]) == list(PACK_CROPS)
    assert crop_plan.per_season(farm) == {"spring": 2, "summer": 2, "autumn": 2, "winter": 2}
    stages = {"corn": "6frames", "tomato": "7frames", "turnip": "4frames", "wheat": "5frames"}
    for crop, frames in stages.items():
        scene = _text(target, f"generated/scenes/farm/crops/{crop}.tscn")
        assert f"{pack}crops/{crop}_16x" in scene and f"_{frames}.png" in scene, crop
    # its soil, dry and watered; its tools; its bin and its bed
    soil = _text(target, "generated/tilesets/farm_soil.tres")
    assert f"{pack}tilesets/soil_tilled.png" in soil and f"{pack}tilesets/soil_watered.png" in soil
    icons = {"hoe": "hoe", "watering_can": "watering_can", "sickle": "sickle", "farm_axe": "axe",
             "fishing_rod": "fishing_rod"}  # fmt: skip
    for item, picture in icons.items():
        assert f"{pack}tools/{picture}.png" in _text(target, f"game/data/items/{item}.tres"), item
    assert f"{pack}props/shipping_bin.png" in _text(
        target, "generated/scenes/farm/shipping_bin.tscn"
    )
    assert f"{pack}props/bed.png" in _text(target, "generated/scenes/farm/bed.tscn")
    # the farmhouse is the house of the pack's sheet, which the planner saw: six cells by four
    plan = farm["map"]
    assert plan["house"]["rect"][2:] == [6, 4] and plan["water"]["kind"] == "pond"
    scene = _text(target, "game/maps/farm.tscn")
    house = "generated/scenes/objects/sample_pack_farm__objects__farmyard__house.tscn"
    assert f'path="res://{house}"' in scene, "the pack's house, not a drawn one"
    for prop in ("tree", "bush", "rock", "stump", "branch", "flowers", "weeds"):
        assert f"{pack}props/{prop}.png" in scene, prop
    # the grass once a season, the fish of the pond and what lies about
    seasons = jsonio.read(target / "generated/data/seasons.json")["groups"]
    assert seasons == {
        "sample_pack_farm.tilesets.spring.grass": {
            season: f"{pack}tilesets/{season}/grass.png"
            for season in ("spring", "summer", "autumn", "winter")
        }
    }
    found = jsonio.read(target / forage_plan.FORAGE_FILE)
    assert [f["id"] for f in found["fish"]] == ["fish_perch"]
    assert sorted(f["id"] for f in found["forage"]) == ["forage_mushroom", "forage_wild_berries"]
    assert f"{pack}items/fish/perch.png" in _text(target, "game/data/items/fish_perch.tres")
    # three villagers of the pack live in the village
    people = jsonio.read(target / people_plan.PEOPLE_FILE)["people"]
    sheets = sorted({p["scene"].rsplit("__", 1)[-1].removesuffix(".tscn") for p in people})
    assert sheets == ["villager_baker", "villager_elder", "villager_smith"]


def test_a_second_run_of_green_acre_changes_nothing(green_acre, godot_exe: Path) -> None:
    target, _result = green_acre
    kept = {
        p.relative_to(target).as_posix(): p.read_bytes()
        for folder in ("generated/scenes", "game/data", "generated/data", "game/maps")
        for p in sorted((target / folder).rglob("*"))
        if p.is_file() and not p.name.endswith(".import")
    }
    kept[world_plan.PLAN_FILE] = (target / world_plan.PLAN_FILE).read_bytes()
    kept[paths.LEDGER] = (target / paths.LEDGER).read_bytes()
    assert len(kept) > 40
    again = orchestrator.run_in_memory(_sample_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE]
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


def test_green_acre_with_a_coop_and_a_barn_keeps_its_hen_and_its_cow(green_acre_animals) -> None:
    target, result = green_acre_animals
    names = _smoke(target)
    assert names[-len(STEPS + ANIMAL_STEPS) :] == STEPS + ANIMAL_STEPS
    assert _vacuous(target) == [], "every step of the farm is played, the animals' too"
    assert _animal_notes(target) == []
    assert _sample_notes(result) == []
    animals, farm_map, listed = _animal_files(target)
    assert [b["kind"] for b in farm_map["animal_houses"]] == ["coop", "barn"]
    _house_rooms(target, farm_map)
    assert [(k["id"], k["house"], k["collect"]) for k in animals["kinds"]] == [
        ("hen", "coop", "floor"),
        ("cow", "barn", "hand"),
    ]
    assert [h["kind"] for h in listed["houses"]] == ["coop", "barn"]
    pack = "res://assets/packs/sample_pack_farm/"
    for kind, cell in (("hen", "16x16"), ("cow", "24x24")):
        entry = next(k for k in animals["kinds"] if k["id"] == kind)
        (variant,) = entry["variants"]
        # one sheet of strips: the walk in four directions and the sleep
        assert variant["asset"].endswith(f"animals.{kind}_move_down_{cell}_4frames")
        assert variant["sleep"] == "", "it sleeps in an animation of the same sheet"
        scene = _text(target, f"generated/scenes/farm/animals/{kind}__{variant['id']}.tscn")
        assert f'kind = "{kind}"' in scene
        frames = f"generated/sprite_frames/{variant['asset']}.tres"
        assert f'path="res://{frames}"' in scene, "the animal shows the frames of its own sheet"
        sheet = _text(target, frames)
        for anim in ("walk_down", "walk_left", "walk_right", "walk_up", "sleep_down"):
            assert f'&"{anim}"' in sheet, (kind, anim)
        assert f"{pack}animals/{kind}_sleep_{cell}_2frames.png" in sheet
    # the egg and the milk are the pack's pictures
    assert f"{pack}items/egg.png" in _text(target, "game/data/items/egg.tres")
    assert f"{pack}items/milk.png" in _text(target, "game/data/items/milk.tres")
    # the coop and the barn of the pack's sheet stand on the farm, each with its fenced yard
    scene = _text(target, "game/maps/farm.tscn")
    for name in ("house", "yard_coop", "yard_barn"):
        rel = f"generated/scenes/objects/sample_pack_farm__objects__farmyard__{name}.tscn"
        assert f'path="res://{rel}"' in scene, name
    assert f"{pack}props/fence.png" in scene
    sizes = {b["kind"]: b["rect"][2:] for b in farm_map["animal_houses"]}
    assert sizes == {"coop": [4, 3], "barn": [6, 4]}
