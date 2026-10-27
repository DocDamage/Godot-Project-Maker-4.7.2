"""The animals of a farm (T17.07): the planner, the kinds and their houses, the colour variants,
the stored plan and what the game reads of it."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import schema
from rpggen.core import animal_plan, archive, catalog, crop_plan, farm_kit, farm_plan, inventory
from rpggen.errors import RpgGenError

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
RANCH = REPO / "test_packs" / "synthetic" / "ranch"
BOTH = ["coop", "barn"]


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _catalog(pack: Path, pack_id: str) -> catalog.Catalog:
    opened = archive.open_pack(pack, set(), pack_id=pack_id)
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


def _fact(asset: str, colour: str = "", walk: bool = True, sleep: bool = False) -> dict:
    return {
        "asset": asset,
        "kind": animal_plan.kind_of(asset),
        "breed": animal_plan.breed_of(asset),
        "colour": colour,
        "walk": walk,
        "sleep": sleep,
    }


def _facts(houses: list[str] = BOTH) -> dict:
    """Two hens in two colours each, a cow, a duck and a horse."""
    return {
        "houses": list(houses),
        "animals": [
            _fact("p.animals.hen_01_black_move_down_16x16_4frames", "black"),
            _fact("p.animals.hen_01_black_sleep_16x16_2frames", "black", walk=False, sleep=True),
            _fact("p.animals.hen_01_white_move_down_16x16_4frames", "white"),
            _fact("p.animals.hen_02_black_move_down_16x16_4frames", "black", sleep=True),
            _fact("p.animals.cows.cow_32x32", ""),
            _fact("p.animals.duck_walk_16x16", ""),
            _fact("p.animals.horse_01_brown_move_down_32x32_4frames", "brown"),
        ],
    }


# ------------------------------------------------------------------------ kinds and houses


@pytest.mark.parametrize(
    ("asset", "tags", "kind", "house"),
    [
        ("rpggen_farm_kit.hen", ["animal", "farm_kit", "hen"], "hen", "coop"),
        ("ranch.animals.chickens.hen_01.black.move.hen_01_black_move_down", ["animal"], "hen", "coop"),
        ("p.chickens.chicken_walk", [], "chicken", "coop"),
        ("p.birds.ducks_16x16", [], "duck", "coop"),
        ("ranch.animals.cows.cow_01.brown.sleep.cow_01_brown_sleep_32x32", ["animal"], "cow", "barn"),
        ("p.farm.sheep_walk_down", [], "sheep", "barn"),
        ("p.farm.goats", [], "goat", "barn"),
        ("p.farm.pig_01_pink_move", ["colour:pink"], "pig", "barn"),
        # the tag counts before the name, the name before the folder
        ("p.cows.bessie_walk", ["animal", "cow"], "cow", "barn"),
        ("p.cows.hen_walk", [], "hen", "coop"),
        # an animal nobody knows lives in the barn, under the first word of its name
        ("p.animals.horse_01_brown_move_down_32x32_4frames", ["animal"], "horse", "barn"),
        ("p.animals.walk_down_4frames", ["animal"], "animal", "barn"),
    ],
)  # fmt: skip
def test_the_kind_and_the_house_of_an_animal(asset, tags, kind, house) -> None:
    assert animal_plan.kind_of(asset, tags) == kind
    assert animal_plan.house_of(kind) == house


def test_the_breed_is_the_animals_own_name() -> None:
    assert animal_plan.breed_of("p.cows.cow_01.brown.move.cow_01_brown_move_down") == "cow_01"
    assert animal_plan.breed_of("rpggen_farm_kit.hen") == "hen"
    assert animal_plan.breed_of("p.sheep_walk") == "sheep"


# ------------------------------------------------------------------------ the plan


def test_the_plan_is_the_same_for_the_same_seed_and_the_seed_gives_the_names() -> None:
    facts = _facts()
    first = animal_plan.plan({}, 4711, facts)
    assert animal_plan.plan({}, 4711, copy.deepcopy(facts)) == first
    # the order the packs list their pictures in does not count
    shuffled = {"houses": ["barn", "coop"], "animals": list(reversed(facts["animals"]))}
    assert animal_plan.plan({}, 4711, shuffled) == first
    assert first["plan_version"] == animal_plan.PLAN_VERSION and first["seed"] == 4711
    assert sorted(first["names"]) == sorted(animal_plan.NAMES)
    orders = {tuple(animal_plan.plan({}, seed, facts)["names"]) for seed in range(6)}
    assert len(orders) > 1, "another seed calls the first animal something else"
    # the options are not read
    assert animal_plan.plan({"difficulty": "hard", "animals": "none"}, 4711, facts) == first
    assert animal_plan.check(first) == [] and first["notes"] == []
    assert first["feed"] == animal_plan.FEED


def test_the_kinds_their_houses_products_and_prices() -> None:
    section = animal_plan.plan({}, 1, _facts())
    kinds = {k["id"]: k for k in section["kinds"]}
    # the coop's kinds first, then the barn's
    assert list(kinds) == ["duck", "hen", "cow", "horse"]
    assert [k["house"] for k in section["kinds"]] == ["coop", "coop", "barn", "barn"]
    hen, cow, horse = kinds["hen"], kinds["cow"], kinds["horse"]
    assert (hen["product"], hen["price"], hen["large"], hen["large_price"]) == (
        "egg",
        25,
        "egg_large",
        37,
    )
    assert (hen["ticket"], hen["cost"], hen["collect"]) == ("animal_hen", 150, "floor")
    assert (cow["product"], cow["price"], cow["large_price"], cow["cost"]) == ("milk", 60, 90, 360)
    assert cow["collect"] == "hand" and kinds["duck"]["collect"] == "floor"
    assert (horse["product"], horse["price"], horse["name"]) == ("horse_product", 40, "Horse")
    for kind in section["kinds"]:
        assert kind["large_price"] > kind["price"], "a friend's product is worth more"
        assert kind["cost"] == kind["price"] * animal_plan.COST_FACTOR


def test_the_variants_of_a_kind_are_its_animals_in_their_colours() -> None:
    section = animal_plan.plan({}, 1, _facts())
    hen = next(k for k in section["kinds"] if k["id"] == "hen")
    assert [v["id"] for v in hen["variants"]] == ["hen_01_black", "hen_01_white", "hen_02_black"]
    black, white, second = hen["variants"]
    # the sheet it sleeps in is named when it is another file than the one it walks in
    assert black == {
        "id": "hen_01_black",
        "colour": "black",
        "asset": "p.animals.hen_01_black_move_down_16x16_4frames",
        "sleep": "p.animals.hen_01_black_sleep_16x16_2frames",
    }
    assert white["sleep"] == "" and second["sleep"] == "", "none, and one sheet for both"
    cow = next(k for k in section["kinds"] if k["id"] == "cow")
    assert cow["variants"] == [
        {"id": "cow", "colour": "", "asset": "p.animals.cows.cow_32x32", "sleep": ""}
    ]
    # an animal that is only drawn asleep is nothing to show by day
    asleep = {"houses": BOTH, "animals": [_fact("p.pig_sleep", "", walk=False, sleep=True)]}
    assert animal_plan.plan({}, 1, asleep)["kinds"] == []


def test_only_the_kinds_whose_house_the_farm_has_are_planned() -> None:
    coop = animal_plan.plan({}, 1, _facts(["coop"]))
    assert [k["id"] for k in coop["kinds"]] == ["duck", "hen"] and coop["notes"] == []
    barn = animal_plan.plan({}, 1, _facts(["barn"]))
    assert [k["id"] for k in barn["kinds"]] == ["cow", "horse"]
    # a house the packs have no animal for stays empty, and the plan says so
    cows = {"houses": BOTH, "animals": [_fact("p.cow_walk")]}
    lonely = animal_plan.plan({}, 1, cows)
    assert [k["id"] for k in lonely["kinds"]] == ["cow"]
    assert lonely["notes"] == ["The packs have no animal for the coop: it stays empty."]
    assert animal_plan.plan({}, 1, _facts([]))["kinds"] == []


def test_a_farm_without_an_animal_house_has_no_plan_of_animals() -> None:
    assert animal_plan.for_project(None, {}, 1, _facts([])) == (None, [])
    assert animal_plan.for_project(None, {}, 1, None) == (None, [])
    farm = crop_plan.plan({}, 1, None)
    assert animal_plan.store(farm, None) == farm, "the section of such a farm is what it was"
    fresh, notes = animal_plan.for_project(None, {}, 1, _facts(["coop"]))
    assert fresh is not None and notes == []
    stored = animal_plan.store(farm, fresh)
    assert stored["animals"] == fresh and stored["crops"] == farm["crops"]
    assert "animals" not in farm, "a copy"


def test_the_stored_plan_is_kept_and_gains_what_the_packs_gain() -> None:
    facts = _facts(["coop"])
    stored, _notes = animal_plan.for_project(None, {}, 7, facts)
    assert stored is not None
    # another seed and other options change nothing of a stored plan
    again, notes = animal_plan.for_project(stored, {"animals": "none"}, 99, facts)
    assert again == stored and notes == []
    more = copy.deepcopy(facts)
    more["animals"] += [
        _fact("p.animals.hen_03_red_move_down_16x16_4frames", "red"),
        _fact("p.animals.chicken_walk_16x16", ""),
        _fact("p.animals.sheep_walk_16x16", ""),
    ]
    grown, notes = animal_plan.for_project(stored, {}, 99, more)
    assert grown is not None
    assert grown["kinds"][: len(stored["kinds"])][0] == stored["kinds"][0], "what was there stays"
    assert [k["id"] for k in grown["kinds"]] == ["duck", "hen", "chicken"], "no barn, no sheep"
    hen = next(k for k in grown["kinds"] if k["id"] == "hen")
    assert [v["id"] for v in hen["variants"]][-1] == "hen_03_red"
    assert notes == ["The farm kept its animals; added: Chicken, Hen (red)."]
    assert animal_plan.for_project(grown, {}, 99, more) == (grown, []), "added once"
    # a stored plan is kept although the farm lost nothing: even without the facts of a house
    assert animal_plan.for_project(stored, {}, 1, _facts([]))[0] == stored


def test_the_check_finds_what_is_wrong_with_a_plan() -> None:
    section = animal_plan.plan({}, 1, _facts())
    assert animal_plan.check(section) == []
    broken = copy.deepcopy(section)
    broken["kinds"].append(copy.deepcopy(broken["kinds"][0]))
    broken["kinds"][1]["house"] = "stable"
    broken["kinds"][2]["variants"] = []
    broken["kinds"][3]["price"] = 0
    broken["kinds"][3]["collect"] = "magic"
    problems = animal_plan.check(broken)
    assert problems == [
        "hen: lives in 'stable', which is no animal house",
        "cow: has no picture",
        "horse: its product or the animal itself has no price",
        "horse: its product is taken 'magic'",
        "duck: listed twice",
    ]


def test_the_summary() -> None:
    section = animal_plan.plan({}, 1, _facts(["coop"]))
    assert animal_plan.summary(section) == "2 kinds of animal: Duck (coop), Hen (coop, 3 colours)"
    assert animal_plan.summary({"kinds": []}) == "0 kinds of animal"


# ------------------------------------------------------------------------ the houses and the file


def test_the_houses_are_the_animal_houses_of_the_farms_plan() -> None:
    farm_map = farm_plan.plan({"animals": "coop_and_barn"}, 3)
    houses = animal_plan.houses_of(farm_map)
    assert houses == [
        {
            "kind": kind,
            "map": f"res://game/maps/farm_{kind}.tscn",
            "yard_map": "res://game/maps/farm.tscn",
            "stalls": farm_plan.STALLS[kind],
        }
        for kind in ("coop", "barn")
    ]
    assert animal_plan.houses_of(farm_plan.plan({}, 3)) == [], "the default farm has none"
    assert animal_plan.houses_of(None) == []


def test_the_file_of_the_game_fits_its_schema() -> None:
    section = animal_plan.plan({}, 5, _facts())
    houses = animal_plan.houses_of(farm_plan.plan({"animals": "coop_and_barn"}, 5))
    scenes = {"hen.hen_01_black": "res://generated/scenes/farm/animals/hen__hen_01_black.tscn"}
    listed = animal_plan.animals_file(section, houses, scenes)
    schema.validate("animals", listed)
    assert [k["id"] for k in listed["animals"]] == [k["id"] for k in section["kinds"]]
    hen = next(k for k in listed["animals"] if k["id"] == "hen")
    assert hen["variants"][0]["scene"] == scenes["hen.hen_01_black"]
    assert hen["variants"][1]["scene"] == "", "a variant without a scene is listed all the same"
    assert listed["feed"] == animal_plan.FEED and listed["names"] == section["names"]
    assert listed["houses"] == houses
    assert "scene" not in section["kinds"][0]["variants"][0], "the plan is not changed"
    schema.validate("animals", {"animals": []})
    with pytest.raises(RpgGenError):
        schema.validate("animals", {"animals": [{"id": "hen", "name": "Hen"}]})
    with pytest.raises(RpgGenError):
        schema.validate(
            "animals", {**listed, "houses": [{"kind": "stable", "map": "x", "stalls": 1}]}
        )


def test_the_plan_fits_the_schema_of_the_world_plan() -> None:
    farm = crop_plan.plan({}, 5, None)
    world = crop_plan.world(animal_plan.store(farm, animal_plan.plan({}, 5, _facts())), 5)
    schema.validate("world_plan", world)
    schema.validate("world_plan", crop_plan.world(farm, 5))
    world["farm"]["animals"]["kinds"][0]["house"] = "stable"
    with pytest.raises(RpgGenError):
        schema.validate("world_plan", world)


# ------------------------------------------------------------------------ real packs


def test_the_ranch_pack_has_hens_and_cows_in_three_colours() -> None:
    facts = animal_plan.facts_of(_catalog(RANCH, "ranch"), BOTH)
    assert facts["houses"] == BOTH
    assert {(f["kind"], f["breed"], f["colour"]) for f in facts["animals"]} == {
        (kind, f"{kind}_01", colour)
        for kind in ("hen", "cow")
        for colour in ("black", "brown", "white")
    }
    section = animal_plan.plan({}, 11, facts)
    assert animal_plan.check(section) == []
    assert [(k["id"], k["house"]) for k in section["kinds"]] == [("hen", "coop"), ("cow", "barn")]
    for kind in section["kinds"]:
        assert [v["colour"] for v in kind["variants"]] == ["black", "brown", "white"]
        for variant in kind["variants"]:
            assert "_move_down_" in variant["asset"] and "_sleep_" in variant["sleep"]
            assert variant["colour"] in variant["asset"] and variant["colour"] in variant["sleep"]
    assert animal_plan.summary(section) == (
        "2 kinds of animal: Hen (coop, 3 colours), Cow (barn, 3 colours)"
    )
    # with a coop alone the cows are not in the game
    coop = animal_plan.plan({}, 11, animal_plan.facts_of(_catalog(RANCH, "ranch"), ["coop"]))
    assert [k["id"] for k in coop["kinds"]] == ["hen"]


def test_a_pack_without_an_animal_keeps_the_drawn_hen(tmp_path: Path) -> None:
    found = _catalog(SAMPLE, "sample_pack")
    assert animal_plan.facts_of(found, ["coop"])["animals"] == [], "the sample has no animal"
    farm_kit.add(found, 16, tmp_path)
    facts = animal_plan.facts_of(found, ["coop", "stable"])
    assert facts["houses"] == ["coop"], "a house nobody knows is none"
    assert facts["animals"] == [
        {
            "asset": "rpggen_farm_kit.hen",
            "kind": "hen",
            "breed": "hen",
            "colour": "",
            "walk": True,
            "sleep": False,
        }
    ]
    section = animal_plan.plan({}, 2, facts)
    assert [(k["id"], k["house"], k["product"]) for k in section["kinds"]] == [
        ("hen", "coop", "egg")
    ]
    assert section["kinds"][0]["variants"] == [
        {"id": "hen", "colour": "", "asset": "rpggen_farm_kit.hen", "sleep": ""}
    ]
    # an animal that is switched off is none
    hen = found.asset("rpggen_farm_kit.hen")
    assert hen is not None
    hen.status = "UNUSED"
    assert animal_plan.facts_of(found, ["coop"])["animals"] == []


# ------------------------------------------------------------------------ the houses a farm builds (T18.05)

HENS = [_fact("p.animals.hen_01_black_move_down_16x16_4frames", "black")]
COWS = [_fact("p.animals.cow_01_brown_move_down_32x32_4frames", "brown")]
KIT_HEN = [_fact(f"{farm_kit.KIT_PACK}.farm_kit.hen_16", "")]
PACKS = {
    "hens only": HENS,
    "cows only": COWS,
    "mixed": HENS + COWS,
    "no animal": KIT_HEN,  # the farm kit's drawn hen stands in, and does not count
}
# choice -> pack -> (the houses built, the houses the Options page warns are empty)
CHOICES = {
    "auto": {
        "hens only": (["coop"], []),
        "cows only": (["barn"], []),
        "mixed": (["coop", "barn"], []),
        "no animal": ([], []),
    },
    "coop": {
        "hens only": (["coop"], []),
        "cows only": (["coop"], ["coop"]),
        "mixed": (["coop"], []),
        "no animal": (["coop"], ["coop"]),
    },
    "barn": {
        "hens only": (["barn"], ["barn"]),
        "cows only": (["barn"], []),
        "mixed": (["barn"], []),
        "no animal": (["barn"], ["barn"]),
    },
    "coop_and_barn": {
        "hens only": (["coop", "barn"], ["barn"]),
        "cows only": (["coop", "barn"], ["coop"]),
        "mixed": (["coop", "barn"], []),
        "no animal": (["coop", "barn"], ["coop", "barn"]),
    },
}


@pytest.mark.parametrize("choice", list(CHOICES))
@pytest.mark.parametrize("pack", list(PACKS))
def test_the_houses_of_each_choice_on_each_pack(choice: str, pack: str) -> None:
    facts = farm_plan.facts_of(animal_houses=animal_plan.pack_houses(PACKS[pack]))
    built, empty = CHOICES[choice][pack]
    farm = farm_plan.plan({"animals": choice}, 7, facts)
    assert [b["kind"] for b in farm["animal_houses"]] == built
    assert farm_plan.empty_houses(choice, facts) == empty
    # the animals planned live in the houses built; a house nobody lives in has its note
    animals = animal_plan.plan({}, 7, {"houses": built, "animals": PACKS[pack]})
    assert {k["house"] for k in animals["kinds"]} <= set(built)
    for house in empty:
        if pack != "no animal":
            assert f"The packs have no animal for the {house}: it stays empty." in animals["notes"]


def test_a_new_farm_is_auto_and_an_older_config_keeps_its_houses() -> None:
    from rpggen.core import config

    new_farm = config.default_for("Farm", [], archetype="farm")
    assert new_farm.starter_map_options()["animals"] == "auto"
    # an older config has its choice written, and means what it meant
    assert farm_plan.normalized({"animals": "coop_and_barn"})["animals"] == "coop_and_barn"
    assert farm_plan.normalized({})["animals"] == "none", "a missing key is not auto"
    assert farm_plan.houses_for("coop_and_barn", {"animal_houses": []}) == ("coop", "barn")
    with pytest.raises(farm_plan.FarmPlanError):
        farm_plan.normalized({"animals": "pigsty"})


def test_a_cows_only_pack_makes_a_farm_with_a_barn_and_no_coop_by_default(tmp_path: Path) -> None:
    """The farm sample without its hens (and its profile): its cows are its only animals, and
    the default choice (auto) builds the barn."""
    import shutil

    from rpggen.core import config, orchestrator

    shutil.copytree(
        REPO / "sample_pack_farm",
        tmp_path / "cows",
        ignore=shutil.ignore_patterns("hen_*", "*.rpgprofile.json"),
    )
    cat = _catalog(tmp_path / "cows", "cows")
    cfg = config.default_for("Farm", [], archetype="farm")
    facts = orchestrator.farm_facts(cfg, cat)
    assert facts["animal_houses"] == ["barn"]
    farm = farm_plan.plan(cfg.starter_map_options(), cfg.seed, facts)
    assert [b["kind"] for b in farm["animal_houses"]] == ["barn"]
