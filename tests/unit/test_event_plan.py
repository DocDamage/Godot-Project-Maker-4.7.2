"""Festivals and birthdays (T17.25): the planner of the year's festivals, the birthdays of the
people, the stored plans and what the game reads of them."""

from __future__ import annotations

import copy

import pytest

from rpggen import schema
from rpggen.core import calendar_math, config, crop_plan, event_plan, options, people_plan

SEASONS = calendar_math.SEASONS
CROPS = [
    {"price": 30, "seasons": ["spring"]},
    {"price": 40, "seasons": ["autumn"]},
    {"price": 90, "seasons": ["autumn", "summer"]},
    {"price": 120, "seasons": ["autumn"]},
]


def _facts(fishing: bool = True) -> dict:
    return {"fishing": fishing, "crops": copy.deepcopy(CROPS)}


def _people(count: int, seed: int = 7) -> list[dict]:
    facts = {
        "npcs": [{"asset": f"p.characters.villager{i:02d}"} for i in range(count)],
        "houses": 3,
        "shop": True,
        "pond": False,
        "items": ["crop_corn", "crop_turnip", "potion"],
    }
    return people_plan.plan({"people": 40}, seed, facts)["people"]


def _world(farm: dict) -> dict:
    return crop_plan.world(farm, 1)


# ------------------------------------------------------------------------ the festivals


def test_the_plan_is_the_same_whatever_the_seed() -> None:
    first = event_plan.plan({}, 4711, _facts())
    assert event_plan.plan({}, 4711, _facts()) == first
    other = event_plan.plan({}, 12, _facts())
    assert other["festivals"] == first["festivals"], "one festival a season, on a fixed day"
    assert event_plan.check(first) == []


@pytest.mark.parametrize(
    ("days", "wanted"), [(28, [12, 12, 26, 26]), (14, [5, 5, 12, 12]), (7, [5] * 4)]
)
def test_a_festival_a_season_on_a_day_the_season_has(days: int, wanted: list[int]) -> None:
    plan = event_plan.plan({"days_per_season": days}, 1, _facts())
    events = plan["festivals"]
    assert [e["season"] for e in events] == list(SEASONS), "one a season, in the year's order"
    assert [e["day"] for e in events] == wanted
    assert plan["days_per_season"] == days
    for event in events:
        assert 1 <= event["day"] <= days
        # a Friday: never the day the shop is closed anyway
        weekday = calendar_math.weekday(
            calendar_math.day_index(event["day"], SEASONS.index(event["season"]), 1, days)
        )
        assert weekday == event_plan.FESTIVAL_WEEKDAY != people_plan.SHOP_CLOSED_DAY
    assert event_plan.festival_days(days) == list(zip(range(4), wanted, strict=True))
    assert event_plan.check(plan) == []


def test_a_day_of_a_long_season_folds_into_a_short_one_as_a_friday() -> None:
    # what RpgFarmEvents.day_in does with a day the season no longer has
    for long, short in ((28, 14), (28, 7), (14, 7)):
        for season in range(4):
            day = event_plan.festival_day(season, long)
            folded = (day - 1) % short + 1
            assert folded <= short
            assert (folded - 1) % calendar_math.WEEK_DAYS == event_plan.FESTIVAL_WEEKDAY


def test_each_festival_has_its_thing_to_do_and_its_prize() -> None:
    eggs, fish, fair, feast = event_plan.plan({}, 1, _facts())["festivals"]
    assert eggs["kind"] == event_plan.EGG_HUNT
    assert eggs["spots"] == list(event_plan.EGGS) and eggs["goal"] == len(eggs["spots"])
    assert eggs["each"] > 0 and eggs["prize"]["gold"] > 0
    assert fish["kind"] == event_plan.FISHING_COUNT and fish["goal"] >= 1
    assert fish["prize"]["gold"] > 0
    assert fair["kind"] == event_plan.PRODUCE_CONTEST and fair["judge"] == event_plan.JUDGE_PRICE
    # the middle price of what grows in autumn: 40, 90, 120
    assert fair["goal"] == 90 and fair["table"] == event_plan.TABLE
    assert feast["kind"] == event_plan.FEAST and feast["points"] > 0
    assert feast["table"] == event_plan.TABLE
    for event in (eggs, fish, fair, feast):
        assert event["place"] == event_plan.PLACE and event["from"] < event["to"]


def test_a_farm_that_cannot_fish_has_a_second_contest_in_summer() -> None:
    plan = event_plan.plan({}, 1, _facts(fishing=False))
    summer = plan["festivals"][1]
    assert summer["kind"] == event_plan.PRODUCE_CONTEST
    assert summer["judge"] == event_plan.JUDGE_COUNT and summer["goal"] == event_plan.COUNT_GOAL
    assert summer["id"] != plan["festivals"][2]["id"]
    assert any("cannot fish" in note for note in plan["notes"])
    assert event_plan.check(plan) == []
    assert event_plan.contest_goal([], "autumn") == 1, "a game without crops: anything wins"


def test_the_facts_are_read_off_the_farm_section() -> None:
    farm = crop_plan.plan({}, 1, None)
    assert event_plan.facts_of(farm)["fishing"] is False
    farm["forage"] = {"fishing": True}
    facts = event_plan.facts_of(farm)
    assert facts["fishing"] is True
    assert [c["price"] for c in facts["crops"]] == [c["price"] for c in farm["crops"]]
    assert event_plan.facts_of(None) == {"fishing": False, "crops": []}


def test_the_stored_events_are_kept_and_the_option_turns_them_off() -> None:
    stored = event_plan.plan({}, 1, _facts())
    stored["festivals"][0]["day"] = 3  # somebody moved it
    kept, notes = event_plan.for_project(stored, {}, 99, _facts(fishing=False))
    assert kept == stored and kept is not stored and notes == []
    fresh, _ = event_plan.for_project(None, {}, 99, _facts())
    assert fresh == event_plan.plan({}, 99, _facts())
    # a shorter season: nothing is planned again, and a note says what the game does
    kept, notes = event_plan.for_project(stored, {"days_per_season": 7}, 1, _facts())
    assert kept == stored and "folds" in notes[0]
    assert event_plan.for_project(stored, {"festivals": False}, 1, _facts()) == (None, [])
    assert event_plan.for_project(None, {"festivals": False}, 1, _facts()) == (None, [])
    for bad in ({"festivals": "yes"}, {"days_per_season": 9}):
        with pytest.raises(event_plan.EventPlanError):
            event_plan.for_project(None, bad, 1, _facts())


def test_the_check_names_what_is_wrong() -> None:
    plan = event_plan.plan({}, 1, _facts())
    events = plan["festivals"]
    events[1]["day"] = 12 if events[0]["day"] != 12 else events[1]["day"]
    events[1]["season"] = "spring"
    events[2]["kind"] = "parade"
    events[3]["day"] = 40
    del events[3]["table"]
    events[0]["spots"] = []
    events.append(copy.deepcopy(events[0]))
    problems = "\n".join(event_plan.check(plan))
    for wanted in (
        "a second festival on spring 12",
        "the unknown kind 'parade'",
        "day 40 is not a day",
        "no table",
        "an egg hunt without spots",
        "listed twice",
    ):
        assert wanted in problems, wanted


def test_the_json_fits_its_schemas() -> None:
    for fishing in (True, False):
        section = event_plan.plan({"days_per_season": 14}, 5, _facts(fishing))
        farm = event_plan.store(crop_plan.plan({}, 1, None), section)
        schema.validate("world_plan", _world(farm))
        data = event_plan.events_file(section)
        schema.validate("events", data)
        assert [e["map"] for e in data["events"]] == ["starter_map"] * 4
        named = {m for e in data["events"] for m in [e.get("table"), *e.get("spots", [])] if m}
        assert named <= set(event_plan.MARKERS)
    schema.validate("events", {"events": [{"id": "egg_hunt", "removed": True}]})
    schema.validate(
        "events",
        {"events": [{"id": "w", "kind": "wedding", "name": "W", "season": "summer", "day": 3}]},
    )
    assert schema.errors("events", {"events": [{"id": "x", "kind": "egg_hunt"}]})
    assert event_plan.summary(None) == "no festivals"
    assert event_plan.summary(section).startswith("4 festivals: Egg hunt (spring 5), ")


# ------------------------------------------------------------------------ the birthdays


@pytest.mark.parametrize("days", [7, 14, 28])
def test_birthdays_are_deterministic_spread_and_never_on_a_festival(days: int) -> None:
    people = _people(12)
    first = people_plan.with_birthdays(people, 4711, days)
    assert people_plan.with_birthdays(copy.deepcopy(people), 4711, days) == first
    assert all("birthday" not in p for p in people), "a copy: the list it was given is as it was"
    born = [(p["birthday"]["season"], p["birthday"]["day"]) for p in first]
    assert len(set(born)) == len(born), "no two on one day"
    festivals = {(SEASONS[s], d) for s, d in event_plan.festival_days(days)}
    assert not festivals & set(born) and ("spring", 1) not in born
    assert all(1 <= day <= days for _, day in born)
    # spread: twelve people are three a season
    assert [sum(1 for s, _ in born if s == season) for season in SEASONS] == [3, 3, 3, 3]
    other = people_plan.with_birthdays(people, 12, days)
    assert [p["birthday"] for p in other] != [p["birthday"] for p in first], "the seed counts"
    assert people_plan.check(first) == []


def test_a_year_with_fewer_days_than_people_shares_them() -> None:
    people = _people(30)  # 28 days of a year of four weeks, four of them festivals
    done = people_plan.with_birthdays(people, 3, 7)
    born = [(p["birthday"]["season"], p["birthday"]["day"]) for p in done]
    # every day that is no festival and not the first of spring has one before any has two
    assert len(set(born)) == 23 and ("spring", 1) not in born
    assert not {(SEASONS[s], d) for s, d in event_plan.festival_days(7)} & set(born)


def test_stored_people_get_their_birthdays_and_nothing_else_of_them_changes() -> None:
    stored = _people(5)  # what a project stored before the card: nobody has a birthday
    extended, added = people_plan.extend(stored, 7, {"npcs": [], "items": []})
    assert extended == stored and added == []
    done = people_plan.with_birthdays(extended, 7)
    assert [{k: v for k, v in p.items() if k != "birthday"} for p in done] == stored
    assert all(p["birthday"]["season"] in SEASONS for p in done)
    # once they have them they keep them: another seed, another length, somebody new
    newcomer = {**copy.deepcopy(stored[0]), "id": "newcomer", "name": "Newcomer"}
    again = people_plan.with_birthdays([*done, newcomer], 99, 14)
    assert again[:5] == done
    taken = {(p["birthday"]["season"], p["birthday"]["day"]) for p in done}
    new = again[5]["birthday"]
    assert (new["season"], new["day"]) not in taken and new["day"] <= 14
    farm = people_plan.store(crop_plan.plan({}, 1, None), done)
    schema.validate("world_plan", _world(farm))
    data = people_plan.people_file(done)
    schema.validate("people", data)
    assert [p["birthday"] for p in data["people"]] == [p["birthday"] for p in done]
    bad = copy.deepcopy(done)
    bad[0]["birthday"] = {"season": "monsoon", "day": 0}
    problems = "\n".join(people_plan.check(bad))
    assert "unknown season 'monsoon'" in problems and "on the day 0" in problems


# ------------------------------------------------------------------------ the option


def test_the_option_is_on_by_default_and_the_dry_run_counts_the_festivals() -> None:
    assert config.starter_map_defaults("farm")["festivals"] is True
    assert "festivals" not in config.starter_map_defaults("turn_based")
    cfg = config.default_for("F", [], archetype="farm")
    plans = options.plan_farm(cfg, None)
    assert plans["festivals"] == 4
    assert options.farm_text(plans).endswith(", 4 festivals")
    cfg.starter_map["festivals"] = False
    config.GeneratorConfig.from_json(cfg.to_json())
    off = options.plan_farm(cfg, None)
    assert off["festivals"] == 0
    assert options.farm_text(off).endswith(" people") or options.farm_text(off).endswith("person")
