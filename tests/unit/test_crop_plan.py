"""The crops of a farm (T17.05): the planner, the seasons, the days, the stored plan and what
the game reads of it."""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from rpggen import schema
from rpggen.core import archive, catalog, crop_plan, inventory

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
RANCH = REPO / "test_packs" / "synthetic" / "ranch"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _catalog(pack: Path, pack_id: str) -> catalog.Catalog:
    opened = archive.open_pack(pack, set(), pack_id=pack_id)
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


def _facts(count: int) -> dict:
    """``count`` growth strips of 5, 6, 7, ... pictures."""
    return {
        "crops": [
            {
                "asset": f"p.crops.crop{i:02d}_16x32_{5 + i}frames",
                "name": f"crop{i:02d}",
                "stages": 5 + i,
            }
            for i in range(count)
        ]
    }


# ------------------------------------------------------------------------ the plan


def test_orchards_keep_harvest_seasons_and_regrow_without_replanning_existing_crops() -> None:
    orchard = {
        "asset": "fruit.apple",
        "name": "apple",
        "stages": 6,
        "orchard": True,
        "mature_stage": 3,
        "seasons": ["autumn"],
    }
    original = crop_plan.plan({}, 7, _facts(3))
    before = copy.deepcopy(original)
    extended, _ = crop_plan.extend(original, {"crops": [orchard]})
    assert original == before
    assert extended["crops"][:-1] == original["crops"]
    apple = extended["crops"][-1]
    assert apple["seasons"] == ["autumn"] and apple["orchard"] is True
    assert apple["regrow"] == 2 and apple["mature_stage"] == 3
    assert crop_plan.crops_file(extended)["crops"][-1]["orchard"] is True
    for seed in range(10):
        planned = crop_plan.plan({}, seed, {"crops": [orchard]})
        assert crop_plan.check(planned) == [], "orchards don't replace year-round field crops"
        assert "spring" in planned["crops"][0]["seasons"]
        fruit = next(c for c in planned["crops"] if c.get("orchard"))
        assert fruit["seasons"] == ["autumn"]


def test_the_plan_is_the_same_for_the_same_seed_and_the_seed_counts() -> None:
    facts = _facts(7)
    first = crop_plan.plan({}, 4711, facts)
    assert crop_plan.plan({}, 4711, copy.deepcopy(facts)) == first
    # the order the packs list their strips in does not count
    shuffled = {"crops": list(reversed(facts["crops"]))}
    assert crop_plan.plan({}, 4711, shuffled) == first
    orders = {tuple(c["id"] for c in crop_plan.plan({}, seed, facts)["crops"]) for seed in range(8)}
    assert len(orders) > 1, "another seed shares the seasons out another way"
    assert first["plan_version"] == crop_plan.PLAN_VERSION and first["seed"] == 4711
    assert first["notes"] == []


@pytest.mark.parametrize("count", range(13))
def test_every_season_has_two_crops(count: int) -> None:
    for seed in (1, 12345):
        section = crop_plan.plan({}, seed, _facts(count))
        assert crop_plan.check(section) == []
        assert all(n >= crop_plan.MIN_PER_SEASON for n in crop_plan.per_season(section).values())
        assert "spring" in section["crops"][0]["seasons"], "a new game has the first crop's seeds"
        assert len({c["id"] for c in section["crops"]}) == len(section["crops"])
        for crop in section["crops"]:
            assert len(set(crop["seasons"])) == len(crop["seasons"]) >= 1


def test_how_many_seasons_a_crop_has_follows_from_how_many_crops_there_are() -> None:
    spans = {n: len(crop_plan.seasons_for(0, n)) for n in (2, 3, 4, 7, 8, 20)}
    assert spans == {2: 4, 3: 3, 4: 2, 7: 2, 8: 1, 20: 1}
    assert crop_plan.seasons_for(0, 8) == ["spring"]
    assert crop_plan.seasons_for(3, 4) == ["winter", "spring"], "a run goes round the year"


def test_a_pack_without_crops_gets_the_three_drawn_ones() -> None:
    section = crop_plan.plan({}, 12345, None)
    assert sorted(c["id"] for c in section["crops"]) == ["berry", "carrot", "turnip"]
    assert all(c["asset"] == "" and c["stages"] == crop_plan.DRAWN_STAGES for c in section["crops"])
    assert len({c["color"] for c in section["crops"]}) == 3, "three colours"
    assert section["notes"] == [
        "The packs have no crop: the drawn crops (turnip, carrot, berry) were added."
    ]
    assert [c["regrow"] > 0 for c in section["crops"]] == [False, False, True]
    # one crop is not enough for a season either: the drawn ones fill up
    one = crop_plan.plan({}, 12345, _facts(1))
    assert len(one["crops"]) == 4 and "one crop" in one["notes"][0]
    assert crop_plan.check(one) == []
    assert "color" not in next(c for c in one["crops"] if c["asset"])
    assert crop_plan.plan({}, 12345, _facts(2))["notes"] == [], "two crops grow all year"


def test_the_days_come_from_the_pictures_and_the_difficulty_and_the_prices_from_the_days() -> None:
    assert [crop_plan.days_of(n, "normal") for n in (2, 5, 8, 12, 29)] == [2, 4, 7, 11, 14]
    assert [crop_plan.days_of(n, "easy") for n in (5, 8, 12)] == [3, 5, 8]
    assert [crop_plan.days_of(n, "hard") for n in (5, 8, 12)] == [6, 10, 14]
    easy = crop_plan.plan({"difficulty": "easy"}, 3, _facts(4))
    hard = crop_plan.plan({"difficulty": "hard"}, 3, _facts(4))
    assert easy["difficulty"] == "easy" and hard["difficulty"] == "hard"
    for a, b in zip(easy["crops"], hard["crops"], strict=True):
        assert a["id"] == b["id"] and a["days"] < b["days"]
    for crop in hard["crops"]:
        assert crop["seed_price"] == 5 * crop["days"] and crop["energy"] == 8 + 2 * crop["days"]
        once = crop["regrow"] == 0
        assert crop["price"] == (crop["seed_price"] * 2 if once else crop["seed_price"] * 2 // 3)
        assert 0 <= crop["regrow"] <= crop["days"]
        assert (crop["seed"], crop["produce"]) == (f"seed_{crop['id']}", f"crop_{crop['id']}")
    with pytest.raises(crop_plan.CropPlanError, match="difficulty"):
        crop_plan.plan({"difficulty": "brutal"}, 3, None)


def test_the_stages_are_spread_evenly_over_the_days() -> None:
    # the same numbers as godot_templates/tests/unit/test_field.gd (RpgCropData.stage_of)
    cases = [
        (0, 4, 5, 0), (1, 4, 5, 1), (3, 4, 5, 3), (4, 4, 5, 4), (0, 6, 4, 0), (1, 6, 4, 0),
        (2, 6, 4, 1), (5, 6, 4, 2), (6, 6, 4, 3), (1, 2, 12, 5), (2, 2, 12, 11), (9, 2, 12, 11),
        (7, 14, 29, 14), (0, 1, 1, 0), (1, 1, 1, 0),
    ]  # fmt: skip
    for grown, days, stages, wanted in cases:
        assert crop_plan.stage_of(grown, days, stages) == wanted, (grown, days, stages)
    for crop in crop_plan.plan({}, 9, _facts(9))["crops"]:
        shown = [
            crop_plan.stage_of(d, crop["days"], crop["stages"]) for d in range(crop["days"] + 1)
        ]
        assert shown[0] == 0 and shown[-1] == crop["stages"] - 1, "seedling to ripe"
        assert shown == sorted(shown)


def test_a_name_is_the_file_without_its_size_and_frames() -> None:
    names = {
        "ranch.crops.corn_16x32_8frames": "corn",
        "ranch.crops.pumpkin_16x16": "pumpkin",
        "pack.plants.Sweet-Potato_32x32_12_frames": "sweet_potato",
        "pack.growth.wheat": "wheat",
        "pack.16x16": "crop",
    }
    for asset_id, name in names.items():
        assert crop_plan.crop_name(asset_id) == name, asset_id
    # two strips of one name are two crops
    twice = {
        "crops": [
            {"asset": "a.corn_16x32_8frames", "name": "corn", "stages": 8},
            {"asset": "b.corn_16x16_6frames", "name": "corn", "stages": 6},
        ]
    }
    assert sorted(c["id"] for c in crop_plan.plan({}, 1, twice)["crops"]) == ["corn", "corn_2"]


# ------------------------------------------------------------------------ the files


def test_the_json_fits_its_schema() -> None:
    for facts in (None, _facts(1), _facts(5), _facts(12)):
        section = crop_plan.plan({}, 77, facts)
        world = crop_plan.world(section, 77)
        schema.validate("world_plan", world)
        listed = crop_plan.crops_file(
            section, {c["id"]: f"res://x/{c['id']}.tscn" for c in section["crops"]}
        )
        schema.validate("crops", listed)
        assert [c["id"] for c in listed["crops"]] == [c["id"] for c in section["crops"]]
        assert all("asset" not in c and "color" not in c for c in listed["crops"])
        assert all(c["scene"].startswith("res://x/") for c in listed["crops"])
    bad = crop_plan.world(crop_plan.plan({}, 77, None), 77)
    bad["farm"]["crops"][0]["seasons"] = ["monsoon"]
    with pytest.raises(Exception, match="CAT-002|monsoon"):
        schema.validate("world_plan", bad)
    with pytest.raises(Exception, match="CAT-002|days"):
        schema.validate("crops", {"crops": [{"id": "x", "name": "X"}]})
    # a world of areas may have the section too, and a plan without it is what it was
    assert "farm" not in schema._validator("world_plan").schema["required"]


def test_the_stored_plan_is_kept_and_a_new_crop_is_added_to_it() -> None:
    first, notes = crop_plan.for_project(None, {}, 5, _facts(3))
    assert notes == [] and len(first["crops"]) == 3
    # another seed, another difficulty, the same packs: the stored plan counts
    again, notes = crop_plan.for_project(
        copy.deepcopy(first), {"difficulty": "hard"}, 99, _facts(3)
    )
    assert again == first and notes == []
    grown = _facts(5)
    extended, notes = crop_plan.for_project(copy.deepcopy(first), {}, 99, grown)
    assert extended["crops"][:3] == first["crops"], "what was there is untouched"
    assert [c["id"] for c in extended["crops"][3:]] == ["crop03", "crop04"]
    assert notes == ["The farm kept its crops; added: Crop03, Crop04."]
    assert extended["seed"] == 5 and crop_plan.check(extended) == []
    for crop in extended["crops"][3:]:
        assert len(crop["seasons"]) == 2
    schema.validate("world_plan", crop_plan.world(extended, 5))
    # a strip that left the packs stays in the plan: the game's file is the user's
    fewer, notes = crop_plan.for_project(copy.deepcopy(extended), {}, 5, _facts(1))
    assert fewer == extended and notes == []
    assert crop_plan.summary(first).startswith("3 crops: ")


def test_what_is_wrong_with_a_plan_is_said() -> None:
    section = crop_plan.plan({}, 1, _facts(4))
    section["crops"][1]["seasons"] = ["spring"]
    section["crops"][2]["regrow"] = 99
    section["crops"].append(copy.deepcopy(section["crops"][0]))
    problems = crop_plan.check(section)
    assert any("crops, 2 are needed" in p or "crop, 2 are needed" in p for p in problems)
    assert any("grows again after more days than it takes" in p for p in problems)
    assert any("listed twice" in p for p in problems)


# ------------------------------------------------------------------------ the packs


class _Asset(dict):
    """What the planner reads of a catalog asset: its id, its status and its facets."""

    def __init__(self, asset_id: str, status: str, detected: dict) -> None:
        super().__init__(detected=detected)
        self.id = asset_id
        self.status = status


def test_the_facts_are_the_growth_strips_of_the_catalog() -> None:
    strip = {"usage": "growth_strip", "role": "CROP", "stages": 8, "tags": ["crop"]}
    assets = [
        _Asset("p.crops.wheat_16x32_5frames", "NEEDS_REVIEW", {**strip, "stages": 5}),
        _Asset("p.crops.corn_16x32_8frames", "AUTO_DETECTED", strip),
        _Asset("p.crops.off_16x32_8frames", "UNUSED", strip),
        _Asset("p.crops.pumpkin_16x16", "NEEDS_REVIEW", {"usage": "sprite", "role": "CROP"}),
        _Asset("p.fx.sprout_16x16_4frames", "AUTO_DETECTED", {**strip, "role": "DECORATION"}),
        _Asset("p.crops.one_16x16_1frames", "AUTO_DETECTED", {**strip, "stages": 1}),
    ]
    facts = crop_plan.facts_of(SimpleNamespace(assets=assets))
    assert facts == {
        "crops": [
            {"asset": "p.crops.corn_16x32_8frames", "name": "corn", "stages": 8},
            {"asset": "p.crops.wheat_16x32_5frames", "name": "wheat", "stages": 5},
        ]
    }, "sorted by id; a strip that is switched off, has one picture or is no CROP is no crop"
    assert crop_plan.facts_of(SimpleNamespace(assets=[])) == {"crops": []}


def test_the_sample_pack_has_no_crop_and_the_ranch_pack_has_three(tmp_path: Path) -> None:
    from rpggen.core import farm_kit

    plain = _catalog(SAMPLE, "sample_pack")
    assert crop_plan.facts_of(plain) == {"crops": []}
    # a run draws the farm kit into the catalog (T17.02): its three crops are planned like any
    farm_kit.add(plain, 16, tmp_path / "plain")
    drawn = crop_plan.facts_of(plain)
    assert [(c["asset"], c["name"], c["stages"]) for c in drawn["crops"]] == [
        (f"rpggen_farm_kit.{name}", name, 5) for name in ("berry", "carrot", "turnip")
    ]
    assert sorted(name for name, _colour in crop_plan.DRAWN) == ["berry", "carrot", "turnip"]
    section = crop_plan.plan({}, 12345, drawn)
    assert section["notes"] == [], "the kit's crops are crops of the catalog: nothing to add"
    assert all(c["asset"].startswith("rpggen_farm_kit.") for c in section["crops"])
    assert all("color" not in c for c in section["crops"])
    facts = crop_plan.facts_of(_catalog(RANCH, "ranch"))
    assert [(c["name"], c["stages"]) for c in facts["crops"]] == [
        ("corn", 8),
        ("tomato", 12),
        ("wheat", 5),
    ], "a crop of one picture (the pumpkin) has no stages to grow through"
    section = crop_plan.plan({}, 12345, facts)
    assert section["notes"] == [] and crop_plan.check(section) == []
    assert {c["id"]: c["days"] for c in section["crops"]} == {"wheat": 4, "corn": 7, "tomato": 11}
