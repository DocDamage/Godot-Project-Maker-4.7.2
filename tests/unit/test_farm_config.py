"""T17.04: what the Python side knows of the farm: its config, its controls, what is switched
off, its smoke steps, what is installed for it, and that the wizard does not offer it yet."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import errors_table, features, paths, schema
from rpggen.core import (
    catalog as catalog_mod,
)
from rpggen.core import (
    config,
    farm_plan,
    map_preview,
    orchestrator,
    people_plan,
    requirements,
    staging,
    world_plan,
)
from rpggen.errors import IssueList

MONEY = ("starting_money", "pass_out_loss")  # T17.08
FIELD = ("farm_size", "plot", "animals", "difficulty", "added_maps")  # T17.06
FISHING = ("fishing",)  # T17.10
CALENDAR = ("days_per_season", "day_length")  # T17.16
FESTIVALS = ("festivals",)  # T17.25
MARRIAGE = ("courtable",)  # T17.26
EXHAUSTION = ("exhaustion", "cooking", "children")  # T18.11, T18.16, T18.17
FARM_RECIPES = paths.templates_root() / "builder" / "recipes" / "farm"
FARM_RUNTIME = paths.templates_root() / "addons" / "rpg_runtime" / "archetypes" / "farm"


def _cfg(**changes) -> config.GeneratorConfig:
    ref = config.PackRef("ranch", "ranch", "0" * 64, "folder")
    cfg = config.default_for("Green Acre", [ref], archetype="farm")
    for key, value in changes.items():
        setattr(cfg, key, value)
    return cfg


def test_the_config_of_a_farm_is_valid_and_its_map_is_the_top_down_one() -> None:
    cfg = _cfg()
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["archetype"] == "farm"
    # a new farm writes what it chose that an older one lacks (M18); the rest is the default
    assert data["starter_map"] == {
        **config.starter_map_defaults("farm"),
        **config.NEW_FARM_OPTIONS,
    }
    # the village of a farm is the starter map of every top-down game; its money (T17.08) and
    # its own map (T17.06) are keys of their own in the same section
    defaults = config.starter_map_defaults("farm")
    assert {
        k: v
        for k, v in defaults.items()
        if k not in (*MONEY, *FIELD, *FISHING, *CALENDAR, *FESTIVALS, *MARRIAGE, *EXHAUSTION)
    } == config.starter_map_defaults("turn_based")
    assert {k: defaults[k] for k in MONEY} == {"starting_money": 100, "pass_out_loss": True}
    assert {k: defaults[k] for k in FIELD} == farm_plan.defaults()
    assert {k: defaults[k] for k in FISHING} == {"fishing": True}
    assert {k: defaults[k] for k in CALENDAR} == {"days_per_season": 28, "day_length": "normal"}
    assert {k: defaults[k] for k in FESTIVALS} == {"festivals": True}
    assert {k: defaults[k] for k in MARRIAGE} == {"courtable": 2}
    again = config.GeneratorConfig.from_json(data)
    assert again.to_json() == data
    for kind in ("orchard",):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "archetype": kind})
    assert features.FARM_AVAILABLE is True, "the wizard offers it since the gate of 1.5"
    assert "farm" in staging.ARCHETYPES


def test_the_controls_of_a_farm() -> None:
    bindings = config.default_input("farm")
    assert bindings["use"] == {"keys": ["Space", "J"], "mouse_buttons": [1], "joy_buttons": [0]}
    assert bindings["interact"] == {"keys": ["E"], "joy_buttons": [2]}, "Space uses, E talks"
    assert bindings["next_item"] == {"keys": ["R"], "joy_buttons": [10]}
    assert bindings["prev_item"] == {"keys": ["Q"], "joy_buttons": [9]}
    slots = [bindings[f"hotbar_{n}"]["keys"] for n in range(1, config.FARM_HOTBAR_SLOTS + 1)]
    assert slots == [[str(n)] for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)], "0 is the tenth slot"
    for action in ("move_up", "move_down", "move_left", "move_right", "menu", "confirm", "cancel"):
        assert bindings[action] == config.default_input("turn_based")[action], action
    assert _cfg().input == bindings
    own = {"use", "next_item", "prev_item", "hotbar_1", "hotbar_10"}
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        assert not own & set(config.default_input(older)), older
    # no two actions of a farm share a key, but the ones that never meet (a menu and the map)
    taken: dict[str, str] = {}
    for action in ("use", "interact", "next_item", "prev_item", "move_up", "move_down",
                   "move_left", "move_right", *(f"hotbar_{n}" for n in range(1, 11))):  # fmt: skip
        for key in bindings[action]["keys"]:
            assert key not in taken, f"{key}: {action} and {taken.get(key)}"
            taken[key] = action


def test_combat_is_off_for_a_farm_and_the_older_kinds_are_as_they_were() -> None:
    feats = _cfg().features
    assert [k for k, on in feats.items() if not on] == ["combat", "navigation"]
    assert feats["dialogue"] and feats["save"] and feats["demo"]
    older = {k: k != "navigation" for k in config.FEATURE_KEYS}
    for kind in ("turn_based", "arpg"):
        assert config.default_features(kind) == older, kind
    # crafting (T18.14) is for the kinds with a bag to craft into
    assert config.default_features("metroidvania") == {**older, "crafting": False}
    for kind in config.ARCADE_KINDS:
        assert [k for k, on in config.default_features(kind).items() if not on] == [
            "dialogue",
            "navigation",
            "progression",
            "crafting",
        ], kind
    # what a farm needs of the packs is what a top-down game needs
    assert requirements.REQUIRED.get("farm", requirements.REQUIRED["turn_based"]) == [
        "PLAYER",
        "GROUND",
    ]


def test_the_smoke_steps_and_the_installed_files_of_a_farm(tmp_path: Path) -> None:
    # a new game of a farm starts in the farmhouse: its file takes the shared top-down steps
    # and runs them in the village, between its own
    assert orchestrator.smoke_steps_for("farm") == orchestrator.SMOKE_STEPS_FARM
    farm_steps = (templates_smoke() / "smoke_steps_farm.gd").read_text(encoding="utf-8")
    assert 'preload("smoke_steps_m6.gd")' in farm_steps and "_shared.steps()" in farm_steps
    assert orchestrator.smoke_steps_for("turn_based").count(",") == 1
    assert "farm" not in orchestrator.smoke_steps_for("arpg")
    info = errors_table.CODES["SMOKE-013"]
    assert info.severity == "error" and "{step}" in info.message and "{detail}" in info.message
    templates = paths.templates_root()
    written = staging.install_templates(staging.create_staging(tmp_path / "s"), templates, "farm")
    folders = {w.split("/")[3] for w in written if w.startswith("addons/rpg_runtime/archetypes/")}
    assert folders == {"farm"}
    recipes = {
        w.split("/")[3]
        for w in written
        if w.startswith("generated/builder/recipes/") and w.count("/") > 3
    }
    assert recipes == {"farm"}
    smoke = sorted(
        w.rsplit("/", 1)[-1] for w in written if "/smoke/smoke_steps_" in w and w.endswith(".gd")
    )
    assert smoke == [
        "smoke_steps_farm.gd",
        "smoke_steps_m1.gd",
        "smoke_steps_m4.gd",
        "smoke_steps_m6.gd",
    ]
    # the calendar is shared (world/): a farm has it, and so has every other kind, inert
    assert "addons/rpg_runtime/world/calendar.gd" in written
    for name in ("farm_mode", "farmer", "field", "crop", "crop_data", "hotbar", "energy", "tool"):
        assert f"addons/rpg_runtime/archetypes/farm/{name}.gd" in written, name
    for name in ("shipping_bin", "bed", "day_end", "farm_shop", "ui/day_summary"):  # T17.08
        assert f"addons/rpg_runtime/archetypes/farm/{name}.gd" in written, name
    for name in ("farm_build", "farmer_recipe", "mode_recipe", "crop_recipes", "field_recipe"):
        assert f"generated/builder/recipes/farm/{name}.gd" in written, name
    for name in ("home_recipe", "shop_recipe"):  # T17.08
        assert f"generated/builder/recipes/farm/{name}.gd" in written, name
    for name in ("farm_map_recipe", "people_recipes"):  # T17.06, T17.09
        assert f"generated/builder/recipes/farm/{name}.gd" in written, name
    assert "addons/rpg_runtime/archetypes/farm/water_source.gd" in written
    assert "addons/rpg_runtime/actors/schedule.gd" in written
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        other = staging.install_templates(
            staging.create_staging(tmp_path / older), templates, older
        )
        assert not [w for w in other if "farm" in w], older


def templates_smoke() -> Path:
    return paths.templates_root() / "builder" / "smoke"


def test_the_options_of_the_farms_own_map() -> None:
    """T17.06: the size of the field and of the plot, the animal houses, the difficulty and the
    added maps are keys of ``starter_map``, with the planner's own defaults."""
    assert farm_plan.defaults() == {
        "farm_size": "medium",
        "plot": "medium",
        "animals": "none",
        "difficulty": "normal",
        "added_maps": [],
    }
    chosen = {
        "farm_size": "large",
        "plot": "small",
        "animals": "coop_and_barn",
        "difficulty": "hard",
        "added_maps": [{"name": "Beach"}],
    }
    cfg = _cfg(starter_map=dict(chosen))
    data = cfg.to_json()
    schema.validate("config", data)
    assert {k: data["starter_map"][k] for k in FIELD} == chosen
    assert config.GeneratorConfig.from_json(data).to_json() == data
    assert farm_plan.normalized(cfg.starter_map_options())["animals"] == "coop_and_barn"
    wrong_values = (
        {"farm_size": "huge"},
        {"plot": 12},
        {"animals": "zoo"},
        {"difficulty": "brutal"},
        {"added_maps": ["Beach"]},
        {"added_maps": [{"name": ""}]},
    )
    for wrong in wrong_values:
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": {**data["starter_map"], **wrong}})
    for older in ("turn_based", "arpg", "metroidvania"):
        assert not {"farm_size", "plot", "animals", "added_maps"} & set(
            config.starter_map_defaults(older)
        ), older


def test_a_farm_key_does_not_change_the_village_of_the_preview() -> None:
    """The preview's planner and the builder's (``MapBuild.is_default``) agree on what a default
    village is: the village's own keys. A farm with another field keeps the default village."""
    options = _cfg(starter_map={"animals": "coop", "starting_money": 5}).starter_map_options()
    assert map_preview.is_default(options, "farm")
    assert map_preview.plan(options, 12345, {}, "farm")["is_default"] is True
    assert not map_preview.is_default({**options, "npcs": 3}, "farm")
    assert not map_preview.is_default({**options, "size": [48, 30]}, "farm")
    assert set(map_preview.VILLAGE_KEYS) == set(config.starter_map_defaults("turn_based"))
    builder = (paths.templates_root() / "builder/lib/map_build.gd").read_text(encoding="utf-8")
    for key in map_preview.VILLAGE_KEYS:
        assert f'"{key}"' in builder, key
    # the other kinds: as before
    for kind in ("turn_based", "arpg"):
        assert map_preview.is_default(config.starter_map_defaults(kind), kind)
        assert not map_preview.is_default({**config.starter_map_defaults(kind), "chests": 3}, kind)


class _Staging:
    def __init__(self, root: Path) -> None:
        self.staging = root
        self.regenerate = False


class _Callbacks:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def on_log(self, line: str) -> None:
        self.lines.append(line)


class _FakeState:
    def __init__(self, root: Path, cfg: config.GeneratorConfig) -> None:
        self.staging = _Staging(root)
        self.cfg = cfg
        self.issues = IssueList()
        self.cb = _Callbacks()


def _plan(state: _FakeState) -> dict:
    catalog = catalog_mod.Catalog()
    orchestrator._plan_world(state, catalog)  # type: ignore[arg-type]
    stored = world_plan.load(state.staging.staging)
    assert stored is not None
    return stored


def test_the_orchestrator_plans_the_crops_then_the_map_then_the_people(tmp_path: Path) -> None:
    """One file, one section: the crops make it, the map and the people are put into it, in
    that order, and what is stored is used again."""
    cfg = _cfg(starter_map={"animals": "coop"})
    state = _FakeState(tmp_path, cfg)
    stored = _plan(state)
    farm = stored["farm"]
    assert stored["areas"] == [] and {"crops", "map", "people"} <= set(farm)
    assert farm["map"] and farm["people"]
    said = [line for line in state.cb.lines if line.startswith("farm: ")]
    order = [
        next(i for i, line in enumerate(said) if what in line)
        for what in (" crops: ", "a farm of ", " people: ")
    ]
    assert order == sorted(order), said
    facts = orchestrator.farm_facts(cfg, catalog_mod.Catalog())
    assert facts == {"water": False, "animal_houses": [], "workbench": True}, (
        "no building, no water tile, no animal: the planner's own house, a well"
    )
    assert farm["map"] == farm_plan.plan(cfg.starter_map_options(), cfg.seed, facts)
    assert farm["map"]["water"]["kind"] == "well"
    assert [b["kind"] for b in farm["map"]["animal_houses"]] == ["coop"]
    assert farm_plan.check(farm["map"]) == [] and not state.issues.has_errors()
    assert len(farm["people"]) == people_plan.DRAWN_PEOPLE, "no NPC in the packs: the drawn three"
    assert people_plan.check(farm["people"]) == []
    produce = {crop["produce"] for crop in farm["crops"]}
    liked = {
        item for person in farm["people"] for taste in people_plan.TASTES for item in person[taste]
    }
    assert liked and liked <= produce | {"potion"}, "tastes are for what the crops give"
    assert any("no NPC" in note for note in farm["notes"])

    # again, with another seed and other options: the people stay; the map is planned anew
    # while the project has no farm map yet, and kept once it has
    other = _cfg(starter_map={"animals": "none"}, seed=777)
    again = _plan(_FakeState(tmp_path, other))["farm"]
    assert again["people"] == farm["people"] and again["crops"] == farm["crops"]
    assert again["map"] != farm["map"] and again["map"]["animal_houses"] == []
    (tmp_path / "game" / "maps").mkdir(parents=True)
    (tmp_path / farm_plan.MAP_FILE).write_text("built", encoding="utf-8")
    kept = _plan(_FakeState(tmp_path, cfg))["farm"]
    assert kept["map"] == again["map"], "the map exists: its plan is not made again"


def test_a_stored_farm_that_cannot_be_worked_is_reported_and_kept(tmp_path: Path) -> None:
    """``VAL-031``, a line a problem: a plan somebody changed is not replaced."""
    cfg = _cfg()
    stored = _plan(_FakeState(tmp_path, cfg))
    (tmp_path / "game" / "maps").mkdir(parents=True)
    (tmp_path / farm_plan.MAP_FILE).write_text("built", encoding="utf-8")
    stored["farm"]["map"]["tillable"] = stored["farm"]["map"]["tillable"][:3]
    world_plan.save(tmp_path, stored)
    state = _FakeState(tmp_path, cfg)
    after = _plan(state)
    found = [i for i in state.issues if i.code == "VAL-031"]
    assert len(found) >= 1 and "the plot has 3 cells" in found[0].message
    assert found[0].severity.value == "warning"
    assert after["farm"]["map"]["tillable"] == stored["farm"]["map"]["tillable"]
    assert errors_table.CODES["VAL-031"].severity == "warning"


def test_the_money_options_of_a_farm() -> None:
    """T17.08: ``starting_money`` and ``pass_out_loss`` are keys of ``starter_map``; the section
    is written only when it differs from the defaults, and then whole."""
    cfg = _cfg(starter_map={"starting_money": 250, "pass_out_loss": False})
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["starter_map"]["starting_money"] == 250
    assert data["starter_map"]["pass_out_loss"] is False
    assert data["starter_map"]["size"] == [40, 24], "the whole section"
    assert config.GeneratorConfig.from_json(data).to_json() == data
    for wrong in ({"starting_money": -1}, {"starting_money": 1.5}, {"pass_out_loss": 1}):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": {**data["starter_map"], **wrong}})
    # the other kinds do not have the keys
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        assert not set(MONEY) & set(config.starter_map_defaults(older)), older
    # the builder's own default is the config's (a project without the section)
    build = (FARM_RECIPES / "farm_build.gd").read_text(encoding="utf-8")
    assert f"const START_MONEY := {config.FARM_STARTING_MONEY}\n" in build


def test_the_calendar_options_of_a_farm() -> None:
    """T17.16: ``days_per_season`` and ``day_length`` are keys of ``starter_map``; the mode's
    recipe sets them on the mode, which gives them to the calendar."""
    cfg = _cfg(starter_map={"days_per_season": 7, "day_length": "long"})
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["starter_map"]["days_per_season"] == 7
    assert data["starter_map"]["day_length"] == "long"
    assert config.GeneratorConfig.from_json(data).to_json() == data
    for wrong in ({"days_per_season": 10}, {"days_per_season": "7"}, {"day_length": "endless"}):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": {**data["starter_map"], **wrong}})
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        assert not set(CALENDAR) & set(config.starter_map_defaults(older)), older
    # one table in the config, the builder and the runtime
    from rpggen.core import calendar_math

    assert config.FARM_SEASON_DAYS == calendar_math.SEASON_LENGTHS
    assert config.FARM_DAYS_PER_SEASON == calendar_math.DAYS_PER_SEASON
    build = (FARM_RECIPES / "farm_build.gd").read_text(encoding="utf-8")
    lengths = ", ".join(f'"{k}": {v}' for k, v in config.FARM_DAY_LENGTHS.items())
    assert f"const DAY_LENGTHS := {{{lengths}}}" in build
    assert config.FARM_DAY_LENGTHS[config.FARM_DAY_LENGTH] == 0.7  # RpgCalendar.MINUTE_S
    recipe = (FARM_RECIPES / "mode_recipe.gd").read_text(encoding="utf-8")
    for name in ("days_per_season", "minute_s"):
        assert f'root.set("{name}", FarmBuild.{name}(ctx))' in recipe
        assert f"@export var {name}:" in (FARM_RUNTIME / "farm_mode.gd").read_text("utf-8")


def test_the_shop_is_closed_on_the_day_the_shopkeeper_has_off() -> None:
    """One place decides the day: ``people_plan.SHOP_CLOSED_DAY``. The recipe that makes the
    shop and the default of the shop's script are held to it."""
    from rpggen.core import people_plan

    day = people_plan.SHOP_CLOSED_DAY
    recipe = (FARM_RECIPES / "shop_recipe.gd").read_text(encoding="utf-8")
    assert f"const CLOSED_WEEKDAY := {day}\n" in recipe
    shop = (FARM_RUNTIME / "farm_shop.gd").read_text(encoding="utf-8")
    assert f"@export var closed_weekday: int = {day}\n" in shop
    assert "const OPENS := 9\n" in recipe and "const CLOSES := 17\n" in recipe


def test_how_many_can_be_courted_when_the_config_does_not_say() -> None:
    """T17.26: one number, ``people_plan.COURTABLE_DEFAULT``: the config's default and the
    builder's fallback are held to it, and a farm's defaults have it."""
    from rpggen.core import people_plan

    count = people_plan.COURTABLE_DEFAULT
    build = (FARM_RECIPES / "farm_build.gd").read_text(encoding="utf-8")
    assert f"const COURTABLE_DEFAULT := {count}\n" in build
    assert config.starter_map_defaults("farm")["courtable"] == count
    assert "courtable" not in config.starter_map_defaults("turn_based")


def test_the_orchestrator_plans_the_fish_and_the_forage_after_the_map(tmp_path: Path) -> None:
    """T17.10: ``farm.forage`` is planned once, after the map its places lie on, and kept; the
    places follow a map that is planned again, and ``fishing`` follows the option."""
    from rpggen.core import forage_plan

    cfg = _cfg()
    state = _FakeState(tmp_path, cfg)
    farm = _plan(state)["farm"]
    forage = farm["forage"]
    schema.validate("world_plan", world_plan.load(tmp_path))
    assert forage == forage_plan.plan(cfg.starter_map_options(), cfg.seed, None, farm["map"])
    assert forage_plan.check(forage) == [] and len(forage["spots"]) == 8
    assert farm["map"]["water"]["kind"] == "well" and forage["fishing"] is False
    said = [line for line in state.cb.lines if line.startswith("farm: ")]
    assert any("things to forage at 8 places, 3 fish (no fishing)" in line for line in said)
    assert any("drawn" in line for line in said), "an empty catalog: the drawn ones, noted"
    # another seed before the map is built: the map is planned anew and the places with it;
    # the fish and the things stay what they were
    other = _cfg(seed=777)
    again = _plan(_FakeState(tmp_path, other))["farm"]
    assert again["map"] != farm["map"]
    assert again["forage"]["fish"] == forage["fish"]
    assert again["forage"]["forage"] == forage["forage"]
    free = set(forage_plan.free_cells(again["map"]))
    assert {tuple(c) for c in again["forage"]["spots"]} <= free
    # once the map exists nothing of it moves, whatever the seed
    (tmp_path / "game" / "maps").mkdir(parents=True)
    (tmp_path / farm_plan.MAP_FILE).write_text("built", encoding="utf-8")
    kept = _plan(_FakeState(tmp_path, cfg))["farm"]
    assert kept["forage"] == again["forage"] and kept["map"] == again["map"]
    # a pond and the option: the plan's `fishing` is what the shop's recipe reads
    stored = world_plan.load(tmp_path)
    stored["farm"]["map"]["water"]["kind"] = "pond"
    world_plan.save(tmp_path, stored)
    assert _plan(_FakeState(tmp_path, cfg))["farm"]["forage"]["fishing"] is True
    off = _cfg(starter_map={"fishing": False})
    assert _plan(_FakeState(tmp_path, off))["farm"]["forage"]["fishing"] is False
    shop = (FARM_RECIPES / "shop_recipe.gd").read_text(encoding="utf-8")
    assert '{"item_id": "fishing_rod", "price": 150}' in shop and "FarmBuild.fishing()" in shop
    build = (FARM_RECIPES / "farm_build.gd").read_text(encoding="utf-8")
    assert 'forage().get("fishing", false)' in build
