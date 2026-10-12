"""The people of a farm's village (T17.09): the planner, homes, jobs, schedules and tastes, the
stored plan and what the game reads of it."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import schema
from rpggen.core import archive, catalog, crop_plan, inventory, people_plan

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
ITEMS = [
    "hoe", "watering_can", "sickle", "farm_axe", "seed_corn", "seed_turnip",
    "crop_corn", "crop_turnip", "crop_berry", "fish_carp", "stone", "wood", "egg", "milk",
    "flower", "mushroom",
]  # fmt: skip


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _facts(count: int, houses: int = 4, shop: bool = True, pond: bool = True) -> dict:
    return {
        "npcs": [{"asset": f"p.characters.villager{i:02d}"} for i in range(count)],
        "houses": houses,
        "shop": shop,
        "pond": pond,
        "items": list(ITEMS),
    }


def _world(people: list[dict]) -> dict:
    """The world plan file of a farm with these people beside its crops."""
    farm = crop_plan.plan({}, 1, None)
    return crop_plan.world(people_plan.store(farm, people), 1)


# ------------------------------------------------------------------------ the plan


def test_the_plan_is_the_same_for_the_same_seed_and_the_seed_counts() -> None:
    facts = _facts(6)
    first = people_plan.plan({}, 4711, facts)
    assert people_plan.plan({}, 4711, copy.deepcopy(facts)) == first
    # the order the packs list their NPCs in does not count
    shuffled = {**facts, "npcs": list(reversed(facts["npcs"])), "items": list(reversed(ITEMS))}
    assert people_plan.plan({}, 4711, shuffled) == first
    plans = [people_plan.plan({}, seed, facts)["people"] for seed in range(8)]
    assert len({tuple(p["name"] for p in people) for people in plans}) > 1, "the seed names them"
    assert len({str([p["schedule"] for p in people]) for people in plans}) > 1
    assert first["plan_version"] == people_plan.PLAN_VERSION and first["seed"] == 4711
    assert first["notes"] == []


@pytest.mark.parametrize("count", [1, 2, 3, 5, 8, 12])
@pytest.mark.parametrize("seed", [0, 7, 4711])
def test_every_npc_is_a_person_with_a_home_and_a_schedule_of_known_places(
    count: int, seed: int
) -> None:
    facts = _facts(count)
    people = people_plan.plan({}, seed, facts)["people"]
    assert sorted(p["asset"] for p in people) == sorted(n["asset"] for n in facts["npcs"])
    assert len({p["id"] for p in people}) == count and len({p["name"] for p in people}) == count
    assert people_plan.check(people, facts) == []
    for person in people:
        assert person["name"] in people_plan.NAMES
        assert 1 <= person["home"] <= facts["houses"], "one of the village's houses"
        places = [e["place"] for e in person["schedule"]]
        assert set(places) <= set(people_plan.PLACES)
        first = min(person["schedule"], key=lambda e: (e["hour"], "weather" in e))
        assert (first["hour"], first["place"]) == (6, "home"), "at home early"
        plain = [e for e in person["schedule"] if "days" not in e and "weather" not in e]
        assert plain[-1]["place"] == "home" and plain[-1]["hour"] >= 17, "and late"
        assert {"square", "work"} & set(places), "out by day"
        rain = [e for e in person["schedule"] if e.get("weather") == "rain"]
        assert rain and all(e["place"] == "home" for e in rain), "indoors when it rains"
    # the houses are shared out evenly
    per_house = [sum(1 for p in people if p["home"] == h) for h in range(1, facts["houses"] + 1)]
    assert max(per_house) - min(per_house) <= 1
    schema.validate("world_plan", _world(people))


def test_the_pond_is_for_some_afternoons_and_only_where_there_is_one() -> None:
    with_pond = people_plan.plan({}, 3, _facts(8))["people"]
    at_pond = [e for p in with_pond for e in p["schedule"] if e["place"] == "pond"]
    assert at_pond, "somebody goes to the pond"
    assert all(e.get("days") and len(e["days"]) < 7 for e in at_pond), "on some days"
    villagers = [p for p in with_pond if p["pattern"] == "villager"]
    assert villagers
    for person in villagers:
        (pond,) = [e for e in person["schedule"] if e["place"] == "pond"]
        assert pond["hour"] == 14 and len(pond["days"]) == 2, "two afternoons a week"
    facts = _facts(8, pond=False)
    without = people_plan.plan({}, 3, facts)["people"]
    assert not [e for p in without for e in p["schedule"] if e["place"] == "pond"]
    assert "angler" not in {p["pattern"] for p in without}
    assert people_plan.check(without, facts) == []


@pytest.mark.parametrize("seed", range(6))
def test_one_shopkeeper_when_there_is_a_shop(seed: int) -> None:
    facts = _facts(7)
    people = people_plan.plan({}, seed, facts)["people"]
    keepers = [p for p in people if p["job"] == people_plan.SHOPKEEPER]
    assert len(keepers) == 1
    keeper = keepers[0]
    work = [e for e in keeper["schedule"] if e["place"] == "work"]
    assert len(work) == 1 and work[0]["hour"] == 8
    assert work[0]["days"] == [d for d in range(7) if d != people_plan.SHOP_CLOSED_DAY]
    off = [e for e in keeper["schedule"] if e.get("days") == [people_plan.SHOP_CLOSED_DAY]]
    assert {e["place"] for e in off} == {"square", "pond", "home"}, "a day off"
    assert all(p["job"] == "" for p in people if p is not keeper)
    assert not [e for p in people if p is not keeper for e in p["schedule"] if e["place"] == "work"]
    # a village without a shop: nobody has a job
    no_shop = _facts(7, shop=False)
    jobless = people_plan.plan({}, seed, no_shop)["people"]
    assert all(p["job"] == "" for p in jobless)
    assert not [e for p in jobless for e in p["schedule"] if e["place"] == "work"]
    assert people_plan.check(jobless, no_shop) == []


def test_tastes_are_of_items_that_exist() -> None:
    facts = _facts(10)
    gifts = set(people_plan.gifts_of(ITEMS))
    assert "crop_corn" in gifts and "fish_carp" in gifts
    assert not gifts & people_plan.NOT_GIFTS, "nobody is given a tool"
    assert not [g for g in gifts if g.startswith("seed_")], "or seeds"
    people = people_plan.plan({}, 11, facts)["people"]
    for person in people:
        listed = [i for taste in people_plan.TASTES for i in person[taste]]
        assert set(listed) <= gifts
        assert len(listed) == len(set(listed)), "no item in two tastes"
        assert [len(person[t]) for t in people_plan.TASTES] == [2, 3, 2]
    assert len({tuple(p["loves"]) for p in people}) > 1, "people differ"
    # a game with few items shares them out as far as they go, and one with none has no tastes
    few = people_plan.plan({}, 11, {**facts, "items": ["egg", "milk", "hoe"]})["people"]
    assert all(sorted(p["loves"]) == ["egg", "milk"] and p["likes"] == [] for p in few)
    none = people_plan.plan({}, 11, {**facts, "items": []})["people"]
    assert all(p["loves"] == p["likes"] == p["dislikes"] == [] for p in none)
    schema.validate("world_plan", _world(none))


def test_a_village_without_npcs_has_three_people_and_a_large_one_is_cut() -> None:
    drawn = people_plan.plan({}, 5, _facts(0))
    assert [p["asset"] for p in drawn["people"]] == ["", "", ""]
    assert len(drawn["notes"]) == 1 and "no NPC" in drawn["notes"][0]
    assert people_plan.check(drawn["people"], _facts(0)) == []
    assert people_plan.plan({}, 5, None)["people"], "no facts at all: still a village"
    facts = _facts(30)
    many = people_plan.plan({}, 5, facts)
    assert len(many["people"]) == people_plan.MAX_PEOPLE
    assert "30 NPCs" in many["notes"][0]
    assert len(people_plan.plan({"people": 30}, 5, facts)["people"]) == 30
    large = people_plan.plan({"people": 40}, 5, _facts(40))["people"]
    assert len({p["id"] for p in large}) == 40, "a name for everybody"
    more = people_plan.extend(large, 5, _facts(43))[0]
    assert len({p["id"] for p in more}) == 43 and more[-1]["name"].endswith(" 2")
    for bad in (0, 41, "many", True):
        with pytest.raises(people_plan.PeoplePlanError, match="people"):
            people_plan.plan({"people": bad}, 5, facts)
    no_house = people_plan.plan({}, 5, _facts(3, houses=0))
    assert all(p["home"] == 1 for p in no_house["people"])
    assert any("no house" in note for note in no_house["notes"])


# ------------------------------------------------------------------------ the check


def test_the_check_names_what_is_wrong() -> None:
    facts = _facts(4)
    people = people_plan.plan({}, 2, facts)["people"]
    assert people_plan.check(people) == [] and people_plan.check(people, facts) == []

    def broken(change) -> list[str]:  # noqa: ANN001 - a function that damages the copy
        damaged = copy.deepcopy(people)
        change(damaged)
        return people_plan.check(damaged, facts)

    who = people[1]["id"]
    assert broken(lambda p: p[1].pop("home")) == [f"{who}: has no home"]
    assert broken(lambda p: p[1].update(home=0)) == [f"{who}: has no home"]
    assert "house 9" in broken(lambda p: p[1].update(home=9))[0]
    assert (
        "unknown place 'tavern'" in broken(lambda p: p[1]["schedule"][0].update(place="tavern"))[0]
    )
    assert "without a job" in broken(lambda p: p[1]["schedule"][1].update(place="work"))[0]
    assert "no entry for every day" in broken(lambda p: p[1].update(schedule=[]))[0]
    assert "listed twice" in broken(lambda p: p.append(copy.deepcopy(p[1])))[0]
    assert "a shop has one" in broken(lambda p: p[1].update(job="shopkeeper"))[-1]
    assert "does not have" in broken(lambda p: p[1]["loves"].append("gem"))[0]
    assert "two tastes" in broken(lambda p: p[1]["likes"].append(p[1]["loves"][0]))[0]
    assert "hour 30" in broken(lambda p: p[1]["schedule"][0].update(hour=30))[0]
    # against a village without a pond or a shop
    assert any("pond" in line for line in people_plan.check(people, _facts(4, pond=False)))
    assert any("shop" in line for line in people_plan.check(people, _facts(4, shop=False)))


# ------------------------------------------------------------------------ stored and reused


def test_the_stored_people_are_kept_and_a_new_npc_is_appended() -> None:
    facts = _facts(3)
    people, notes = people_plan.for_project(None, {}, 9, facts)
    assert notes == [] and len(people) == 3
    # another seed, other options, other items: nothing changes
    again, notes = people_plan.for_project(people, {"people": 1}, 1234, {**facts, "items": []})
    assert again == people and notes == []
    grown = _facts(5)
    more, notes = people_plan.for_project(people, {}, 9, grown)
    assert more[:3] == people, "who is there stays as they are"
    assert len(more) == 5 and len({p["id"] for p in more}) == 5
    assert {p["asset"] for p in more[3:]} == {n["asset"] for n in grown["npcs"][3:]}
    assert all(p["job"] == "" for p in more[3:]), "the shop keeps its keeper"
    assert notes == [f"The village kept its people; added: {more[3]['name']}, {more[4]['name']}."]
    assert people_plan.check(more, grown) == []
    assert people_plan.for_project(more, {}, 9, grown) == (more, [])
    # beside the crops in the world plan
    farm = crop_plan.plan({}, 9, None)
    stored = people_plan.store(farm, more, ["a note", farm["notes"][0]])
    assert stored["crops"] == farm["crops"] and "people" not in farm
    assert stored["people"] == more and stored["notes"] == [*farm["notes"], "a note"]
    schema.validate("world_plan", crop_plan.world(stored, 9))
    assert people_plan.summary(more).startswith("5 people: ")
    assert "shopkeeper, house" in people_plan.summary(more)
    assert people_plan.summary(more[:1]).startswith("1 person: ")


# ------------------------------------------------------------------------ what the game reads


def test_the_json_fits_its_schema_and_names_maps_and_markers() -> None:
    facts = _facts(5, houses=2)
    people = people_plan.plan({}, 21, facts)["people"]
    places = {
        "home": [
            {"map": "village", "place": "house_1"},
            {"map": "interior_house_2", "cell": [3, 4], "facing": "down"},
        ],
        "work": {"map": "interior_shop", "place": "counter", "facing": "down"},
        "square": {"map": "village", "place": "square"},
        "pond": {"map": "village", "place": "pond"},
    }
    scenes = {p["id"]: f"res://generated/scenes/actors/characters/{p['id']}.tscn" for p in people}
    listed = people_plan.people_file(people, places, scenes)
    schema.validate("people", listed)
    assert [p["id"] for p in listed["people"]] == [p["id"] for p in people]
    for planned, person in zip(people, listed["people"], strict=True):
        assert "asset" not in person and "pattern" not in person
        assert person["scene"] == scenes[person["id"]]
        assert [person[t] for t in people_plan.TASTES] == [planned[t] for t in people_plan.TASTES]
        assert len(person["schedule"]) == len(planned["schedule"])
        for before, entry in zip(planned["schedule"], person["schedule"], strict=True):
            assert entry["hour"] == before["hour"]
            assert entry.get("days") == before.get("days")
            assert entry.get("weather") == before.get("weather")
            assert entry["map"], "every entry names its map"
            if before["place"] == "home" and planned["home"] == 2:
                assert entry["cell"] == [3, 4] and "place" not in entry
            elif before["place"] == "home":
                assert (entry["map"], entry["place"]) == ("village", "house_1")
            elif before["place"] == "work":
                assert (entry["map"], entry["place"]) == ("interior_shop", "counter")
            else:
                assert (entry["map"], entry["place"]) == ("village", before["place"])
    assert people[0]["schedule"][0] == {"hour": 6, "place": "home"}, "the plan is not changed"
    # without the places the names stay, and the file still fits
    bare = people_plan.people_file(people)
    schema.validate("people", bare)
    assert bare["people"][0]["schedule"][0] == {"hour": 6, "place": "home"}
    assert bare["people"][0]["scene"] == ""
    with pytest.raises(Exception, match="CAT-002|place|cell"):
        schema.validate("people", {"people": [{**bare["people"][0], "schedule": [{"hour": 6}]}]})


def test_the_facts_are_the_npcs_of_the_catalog() -> None:
    opened = archive.open_pack(SAMPLE, set(), pack_id="sample")
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    facts = people_plan.facts_of(cat, houses=3, shop=True, pond=True, items=["egg", "crop_corn"])
    roles = {str(a.id): catalog.effective(a).get("role") for a in cat.assets}
    assert [n["asset"] for n in facts["npcs"]] == sorted(a for a, r in roles.items() if r == "NPC")
    assert (facts["houses"], facts["shop"], facts["pond"]) == (3, True, True)
    assert facts["items"] == ["crop_corn", "egg"]
    people = people_plan.plan({}, 1, facts)["people"]
    assert people and people_plan.check(people, facts) == []
