"""T17.10: the plan of a farm's fish and forage: what lies where in which season, which fish
bites when, the places on the farm's map, and when the rod is sold."""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import (
    archive,
    catalog,
    config,
    crop_plan,
    farm_kit,
    farm_plan,
    forage_plan,
    inventory,
)

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(source: Path) -> catalog.Catalog:
    opened = archive.open_pack(source, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _map(seed: int = 7, pond: bool = True, **options: str) -> dict:
    return farm_plan.plan(options, seed, farm_plan.facts_of(water=pond))


def _facts(fish: int, forage: int) -> dict:
    return {
        "fish": [{"asset": f"p.items.fish_{n}", "name": f"fish_{n}"} for n in range(fish)],
        "forage": [
            {"asset": f"p.items.forage_{n}", "name": f"forage_{n}", "seasons": []}
            for n in range(forage)
        ],
    }


def _world(section: dict, seed: int = 7) -> dict:
    farm = crop_plan.plan({}, seed)
    return crop_plan.world(forage_plan.store(farm, section), seed)


def test_the_plan_is_the_same_for_the_same_seed_and_fits_its_schemas() -> None:
    farm = _map()
    first = forage_plan.plan({}, 7, None, farm)
    assert first == forage_plan.plan({}, 7, None, copy.deepcopy(farm))
    assert first["spots"] != forage_plan.plan({}, 8, None, farm)["spots"], "another seed"
    assert first["plan_version"] == 1 and first["seed"] == 7 and first["fishing"] is True
    schema.validate("world_plan", _world(first))
    file = forage_plan.forage_file(first)
    schema.validate("forage", file)
    assert all("asset" not in row and "color" not in row for key in file for row in file[key])
    assert forage_plan.stored_in(_world(first)) == first
    assert forage_plan.stored_in({}) is None and forage_plan.stored_in({"farm": {}}) is None
    assert forage_plan.summary(first) == "4 things to forage at 8 places, 3 fish (the rod is sold)"
    assert "forage" in schema.KINDS


def test_packs_without_fish_or_forage_get_the_drawn_ones_of_the_kit() -> None:
    section = forage_plan.plan({}, 3, None, _map())
    assert sorted(f["id"] for f in section["fish"]) == ["fish_carp", "fish_eel", "fish_perch"]
    assert {f["id"]: f["seasons"] for f in section["forage"]} == {
        "forage_wild_herb": ["spring"],
        "forage_wild_berries": ["summer"],
        "forage_mushroom": ["autumn"],
        "forage_winter_root": ["winter"],
    }, "each in the season it was drawn for"
    rows = [*section["fish"], *section["forage"]]
    assert all(row["asset"] == "" and row["color"] for row in rows)
    assert len(section["notes"]) == 2 and "drawn" in section["notes"][0]
    # the names are the ones the kit draws
    assert [n for n, _s, _c in forage_plan.DRAWN_FORAGE] == list(farm_kit.FORAGE)
    assert [n for n, _c in forage_plan.DRAWN_FISH] == [n for n, _c in farm_kit.FISH]
    assert forage_plan.ROD_ITEM in farm_kit.TOOLS
    for row in rows:
        assert row["item"] == row["id"] and row["price"] > 0 and row["energy"] > 0
    assert all(f["water"] == ["pond"] and 1.0 <= f["speed"] <= 1.4 for f in section["fish"])


@pytest.mark.parametrize("fish", [1, 2, 3, 4, 7])
@pytest.mark.parametrize("forage", [1, 2, 4, 6])
def test_every_season_has_something_to_find_and_every_time_of_it_a_fish(
    fish: int, forage: int
) -> None:
    section: dict = {}
    for seed in range(6):
        section = forage_plan.plan({}, seed, _facts(fish, forage), _map())
        assert forage_plan.check(section) == []
        assert len(section["fish"]) == fish and len(section["forage"]) == forage
        assert len({r["id"] for r in [*section["fish"], *section["forage"]]}) == fish + forage
        assert section["notes"] == []
        schema.validate("world_plan", _world(section))
    if fish >= 3:
        assert any(len(f["seasons"]) < 4 for f in section["fish"]), "the season matters"
        assert all(len(f["times"]) == 2 for f in section["fish"]), "and the time of day"


def test_check_names_what_is_missing() -> None:
    section = forage_plan.plan({}, 1, None, _map())
    section["forage"] = [f for f in section["forage"] if f["seasons"] != ["winter"]]
    for fish in section["fish"]:
        fish["times"] = ["day"]
    section["fish"].append(copy.deepcopy(section["fish"][0]))
    problems = forage_plan.check(section)
    assert "winter: nothing to forage" in problems
    assert "spring, morning: no fish bites" in problems
    assert f"{section['fish'][0]['id']}: listed twice" in problems


@pytest.mark.parametrize("size", ["small", "medium", "large"])
@pytest.mark.parametrize("animals", ["none", "coop_and_barn"])
def test_the_places_lie_on_free_cells_near_the_edge(size: str, animals: str) -> None:
    for seed in range(8):
        farm = _map(seed, farm_size=size, animals=animals)
        spots = [tuple(c) for c in forage_plan.spots_for(farm, seed)]
        assert len(spots) == forage_plan.SPOTS[farm["farm_size"]] and len(set(spots)) == len(spots)
        assert spots == sorted(spots, key=lambda c: (c[1], c[0]))
        cols, rows = farm["size"]
        walkable = farm_plan.reached_cells(farm)
        taken = {tuple(c) for key in ("tillable", "paths", "trees") for c in farm[key]}
        taken |= {tuple(t["cell"]) for key in ("scenery", "debris") for t in farm[key]}
        taken |= {tuple(c) for c in farm["water"]["cells"]}
        taken |= {tuple(farm["bin"]["cell"]), tuple(farm["bin"]["front"])}
        taken |= {tuple(farm["house"]["door"]), tuple(farm["exit"]["cell"])}
        for house in farm["animal_houses"]:
            x, y, wide, high = house["yard"]["rect"]
            taken |= {(x + dx, y + dy) for dx in range(wide) for dy in range(high)}
        for spot in spots:
            assert spot in walkable and spot not in taken, (seed, spot)
            from_edge = min(spot[0], spot[1], cols - 1 - spot[0], rows - 1 - spot[1])
            assert 1 <= from_edge <= forage_plan.EDGE
        assert set(spots) <= set(forage_plan.free_cells(farm))
        apart = min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a in spots for b in spots if a != b)
        assert apart >= forage_plan.APART, "they lie apart"
    assert forage_plan.spots_for(None, 1) == []


def test_the_rod_is_sold_on_a_farm_with_a_pond_unless_the_option_says_no() -> None:
    pond, well = _map(), _map(pond=False)
    assert pond["water"]["kind"] == "pond" and well["water"]["kind"] == "well"
    assert forage_plan.plan({}, 1, None, pond)["fishing"] is True
    assert forage_plan.plan({"fishing": False}, 1, None, pond)["fishing"] is False
    assert forage_plan.plan({}, 1, None, well)["fishing"] is False
    assert forage_plan.plan({}, 1, None, None)["fishing"] is False, "no map, no pond"
    assert forage_plan.summary(forage_plan.plan({}, 1, None, well)).endswith("(no fishing)")
    # a well has things to forage and the fish stay planned: a pond may come
    assert len(forage_plan.plan({}, 1, None, well)["fish"]) == 3
    # the option is a key of the farm's starter_map, and of no other kind's
    assert config.starter_map_defaults("farm")["fishing"] is True
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        assert "fishing" not in config.starter_map_defaults(older), older


def test_a_stored_plan_is_kept_and_only_gains() -> None:
    farm = _map()
    stored = forage_plan.plan({}, 5, _facts(3, 4), farm)
    again, notes = forage_plan.for_project(stored, {}, 999, _facts(3, 4), farm)
    assert again == stored and notes == [], "another seed changes nothing"
    # the option and the farm's water are followed on every generation
    off, _notes = forage_plan.for_project(stored, {"fishing": False}, 5, _facts(3, 4), farm)
    assert off["fishing"] is False and {**off, "fishing": True} == stored
    well = copy.deepcopy(farm)
    well["water"]["kind"] = "well"
    dry, _notes = forage_plan.for_project(stored, {}, 5, _facts(3, 4), well)
    assert dry["fishing"] is False and dry["spots"] == stored["spots"], "the places stay"
    # a farm that was planned again before its map was built: the places are chosen again, on
    # free cells of the map that is, and everything else stays
    other = _map(seed=8, farm_size="large")
    moved, _notes = forage_plan.for_project(stored, {}, 5, _facts(3, 4), other)
    assert moved["spots"] == forage_plan.spots_for(other, 5) != stored["spots"]
    assert {tuple(c) for c in moved["spots"]} <= set(forage_plan.free_cells(other))
    assert moved["fish"] == stored["fish"] and moved["forage"] == stored["forage"]
    assert forage_plan.for_project(moved, {}, 5, _facts(3, 4), other)[0] == moved
    # what the packs gained is appended, and nothing that was there changes
    more, notes = forage_plan.for_project(stored, {}, 5, _facts(4, 5), farm)
    assert more["fish"][:3] == stored["fish"] and more["forage"][:4] == stored["forage"]
    assert [r["asset"] for r in (more["fish"][-1], more["forage"][-1])] == [
        "p.items.fish_3",
        "p.items.forage_4",
    ]
    assert notes == ["The farm kept its fish and forage; added: Forage 4, Fish 3."]
    assert forage_plan.check(more) == []
    # a plan stored before the farm had a map gets its places when it has one
    early = forage_plan.plan({}, 5, _facts(3, 4), None)
    assert early["spots"] == []
    late, _notes = forage_plan.for_project(early, {}, 5, _facts(3, 4), farm)
    assert late["spots"] == stored["spots"] and late["fishing"] is True
    fresh, notes = forage_plan.for_project(None, {}, 5, None, farm)
    assert fresh == forage_plan.plan({}, 5, None, farm) and len(notes) == 2


def test_the_facts_are_the_items_tagged_fish_and_forage(tmp_path: Path) -> None:
    # a plain pack as a farm: the kit's pictures are the fish and the forage
    plain = _catalog(SYNTH / "basic16")
    assert forage_plan.facts_of(plain) == {"forage": [], "fish": []}
    farm_kit.add(plain, 16, tmp_path / "staging")
    facts = forage_plan.facts_of(plain)
    assert [f["asset"] for f in facts["fish"]] == [
        "rpggen_farm_kit.carp",
        "rpggen_farm_kit.eel",
        "rpggen_farm_kit.perch",
    ]
    assert sorted(f["name"] for f in facts["forage"]) == sorted(farm_kit.FORAGE)
    section = forage_plan.plan({}, 2, facts, _map())
    assert section["notes"] == [] and forage_plan.check(section) == []
    assert {f["name"]: f["seasons"] for f in section["forage"]} == {
        "Wild herb": ["spring"],
        "Wild berries": ["summer"],
        "Mushroom": ["autumn"],
        "Winter root": ["winter"],
    }
    for row in section["fish"]:
        assert row["asset"].startswith("rpggen_farm_kit.") and "color" not in row
    # a farming pack with a fish and a thing to forage of its own: none is drawn
    pack = tmp_path / "ranch"
    shutil.copytree(SYNTH / "ranch", pack)
    for name in ("items/fish_trout_16x16.png", "items/autumn/forage_chestnut_16x16.png"):
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        image.paste((120, 140, 90 + len(name), 255), (3, 5, 13, 12))
        image.save(pack / name)
    own = _catalog(pack)
    drawn = [s.name for s in farm_kit.lacking(own)]
    assert not set(drawn) & {*farm_kit.FORAGE, *(n for n, _c in farm_kit.FISH)}, drawn
    assert "fishing_rod" in drawn, "the ranch has no rod"
    facts = forage_plan.facts_of(own)
    assert facts["fish"] == [{"asset": "ranch.items.fish_trout_16x16", "name": "fish_trout"}]
    assert facts["forage"] == [
        {
            "asset": "ranch.items.autumn.forage_chestnut_16x16",
            "name": "forage_chestnut",
            "seasons": ["autumn"],
        }
    ]
    section = forage_plan.plan({}, 2, facts, _map())
    assert [f["id"] for f in section["fish"]] == ["fish_trout"], "no fish_fish_trout"
    assert section["fish"][0]["seasons"] == list(forage_plan.SEASONS)
    assert section["fish"][0]["times"] == list(forage_plan.TIMES), "the one fish bites always"
    assert section["forage"][0]["id"] == "forage_chestnut"
    assert section["forage"][0]["seasons"] == list(forage_plan.SEASONS), "and lies all the year"
    # one that is switched off is none
    own.asset("ranch.items.fish_trout_16x16").status = "UNUSED"
    assert forage_plan.facts_of(own)["fish"] == []


def test_the_option_fishing_is_a_key_of_a_farms_starter_map() -> None:
    ref = config.PackRef("ranch", "ranch", "0" * 64, "folder")
    cfg = config.default_for("Green Acre", [ref], archetype="farm")
    assert cfg.starter_map_options()["fishing"] is True
    cfg.starter_map = {"fishing": False}
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["starter_map"]["fishing"] is False
    assert data["starter_map"]["size"] == [40, 24], "the whole section"
    assert config.GeneratorConfig.from_json(data).to_json() == data
    with pytest.raises(Exception):  # noqa: B017, PT011
        schema.validate("config", {**data, "starter_map": {**data["starter_map"], "fishing": 1}})
    assert forage_plan.normalized(cfg.starter_map_options()) == {"fishing": False}
    assert forage_plan.normalized(None) == {"fishing": True}


def test_the_fish_of_the_farms_readme_is_a_real_entry() -> None:
    from rpggen import paths

    text = (paths.templates_root() / "project_files" / "README.farm.md").read_text("utf-8")
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    assert '"crop_' in blocks[0], "the crop is the first entry the README shows"
    shown = next(json.loads(block) for block in blocks if '"fish_' in block)
    planned = forage_plan._fish_entry({"name": "carp", "asset": "x"}, 1, set())
    assert shown == {k: v for k, v in planned.items() if k != "asset"}
    schema.validate("forage", {"forage": [], "fish": [shown]})
    for words in (
        "### Fishing and foraging",
        "game/data/forage.json",
        "generated/data/forage.json",
        "starter_map.fishing",
        "Forage/Spot1",
        "costs 3 energy",
        "one to four seconds",
    ):
        assert words in text, words
    rod = (paths.templates_root() / "addons/rpg_runtime/archetypes/farm/tools/rod.gd").read_text(
        "utf-8"
    )
    assert "energy_cost = 3\n" in rod, "what the README says a cast costs"
    fishing = (paths.templates_root() / "addons/rpg_runtime/archetypes/farm/fishing.gd").read_text(
        "utf-8"
    )
    for line in ("const WAIT_MIN := 1.0", "const WAIT_MAX := 4.0", "const CAST_MINUTES := 10",
                 "const REEL_MINUTES := 20"):  # fmt: skip
        assert line + "\n" in fishing, line
    # the builder's price of the rod and its words for a pack's own are the kit's
    build = (paths.templates_root() / "builder/recipes/farm/farm_build.gd").read_text("utf-8")
    words = ", ".join(f'"{w}"' for w in farm_kit.TOOL_WORDS["fishing_rod"])
    assert f'"fishing_rod": [{words}],' in build
    assert f'"{forage_plan.ROD_ITEM}": "{forage_plan.ROD_ITEM}"' in build
