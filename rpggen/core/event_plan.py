"""The festivals of a farm's year (T17.25): one a season, on a fixed day, with one small thing
to do and a prize.

* **spring**: an **egg hunt** on the square (eggs lie on marked spots of the village for that
  day; each one found pays a little, and finding them all pays the prize);
* **summer**: a **fishing count** (the fish caught that day are counted; a prize from a number
  on), on a farm that can fish (``farm.forage.fishing``); on one that cannot, a second
  **produce contest**, judged on how many things were shipped that season;
* **autumn**: a **produce contest** (judged on the dearest thing shipped that season);
* **winter**: a **feast** (a dish, any food, is brought to the table on the square: friendship
  with everyone a little).

**The day.** A festival is on the fifth day of a week (``FESTIVAL_WEEKDAY``: a Friday, never the
day the shop is closed anyway, ``people_plan.SHOP_CLOSED_DAY``). Spring's and summer's are in the
middle week of the season, autumn's and winter's in its last: day 12, 12, 26 and 26 of a season
of 28 days, 5, 5, 12 and 12 of one of 14, and 5 in every season of 7 (``festival_day``). The
day is planned for the length of the season the project has when it is planned; the game folds
a day that a shorter season no longer has into it (``RpgFarmEvents.day_in``: 26 is 12 of 14 and
5 of 7, so a festival stays a Friday).

The plan is deterministic (the seed changes nothing of it: there is one festival a season and
its day is fixed) and is **stored** in the project (``rpggen/world_plan.json``, ``farm.events``)
and reused: once it is there the options no longer change it. The builder writes it to
``generated/data/events.json`` on every build and to ``game/data/events.json`` once; that file
is the user's. Birthdays are not here: each person has theirs (``people_plan.with_birthdays``,
``game/data/people.json``). A wedding (T17.26) is an event the game adds at run time
(``RpgFarmEvents.add_event``); it is not planned. No Qt, no Godot.
"""

from __future__ import annotations

import copy
from typing import Any

from rpggen.core import calendar_math

PLAN_VERSION = 1
SEASONS = calendar_math.SEASONS
EVENTS_FILE = "game/data/events.json"
PLANNED_FILE = "generated/data/events.json"
# the day of the week of a festival: 0 is the first day of a year (a Monday), 4 a Friday
FESTIVAL_WEEKDAY = 4
# the hours the people stand on the square on a festival
FROM_HOUR = 9
TO_HOUR = 20
EGG_HUNT = "egg_hunt"
FISHING_COUNT = "fishing_count"
PRODUCE_CONTEST = "produce_contest"
FEAST = "feast"
KINDS = (EGG_HUNT, FISHING_COUNT, PRODUCE_CONTEST, FEAST)
# what a produce contest is judged on: the dearest thing shipped that season, or how many
JUDGE_PRICE = "price"
JUDGE_COUNT = "count"
# the markers of the village a festival names (people_recipes.gd makes them)
PLACE = "square"
TABLE = "festival_table"
EGG_SPOTS = 5
EGGS = tuple(f"festival_egg_{n}" for n in range(1, EGG_SPOTS + 1))
MARKERS = (TABLE, *EGGS)
# the prizes
EGG_EACH = 20
EGG_PRIZE = 150
FISH_GOAL = 3
FISH_PRIZE = 200
CONTEST_PRIZE = 300
COUNT_GOAL = 10
COUNT_PRIZE = 200
FEAST_POINTS = 60


class EventPlanError(ValueError):
    """Options that cannot be planned; the message names the key."""


def normalized(options: Any) -> dict[str, Any]:
    """The options the planner reads: ``festivals`` (true when it is not given) and
    ``days_per_season`` (28 when it is not given)."""
    raw = options if isinstance(options, dict) else {}
    wanted = raw.get("festivals", True)
    if not isinstance(wanted, bool):
        raise EventPlanError(f"festivals: {wanted!r} is not true or false")
    days = raw.get("days_per_season", calendar_math.DAYS_PER_SEASON)
    if isinstance(days, bool) or days not in calendar_math.SEASON_LENGTHS:
        raise EventPlanError(f"days_per_season: {days!r} is not 7, 14 or 28")
    return {"festivals": wanted, "days_per_season": int(days)}


def festival_day(season: int, days_per_season: int = calendar_math.DAYS_PER_SEASON) -> int:
    """The day of the season the festival of ``season`` (0 spring to 3 winter) is on: a Friday
    of the middle week in spring and summer, of the last week in autumn and winter."""
    weeks = calendar_math.season_length(days_per_season) // calendar_math.WEEK_DAYS
    week = (weeks - 1) // 2 if season < 2 else weeks - 1
    return week * calendar_math.WEEK_DAYS + FESTIVAL_WEEKDAY + 1


def festival_days(days_per_season: int = calendar_math.DAYS_PER_SEASON) -> list[tuple[int, int]]:
    """``(season, day)`` of the four festivals of a year, in their order."""
    return [(season, festival_day(season, days_per_season)) for season in range(len(SEASONS))]


def facts_of(farm: Any) -> dict[str, Any]:
    """What the planner needs to know of a farm's stored section: whether it can fish
    (``forage.fishing``) and what its crops are worth in which season."""
    section = farm if isinstance(farm, dict) else {}
    crops = [
        {"price": int(c.get("price", 0) or 0), "seasons": [str(s) for s in c.get("seasons", [])]}
        for c in section.get("crops", [])
        if isinstance(c, dict)
    ]
    forage = section.get("forage")
    fishing = bool(forage.get("fishing")) if isinstance(forage, dict) else False
    return {"fishing": fishing, "crops": crops}


def contest_goal(crops: list[dict[str, Any]], season: str) -> int:
    """The price a thing has to have to win the contest of ``season``: the middle one of the
    prices of the crops that grow then (of all crops when none does), so that the better half
    of what can be grown wins. 1 in a game without crops: anything that was shipped wins."""
    prices = sorted(c["price"] for c in crops if season in c.get("seasons", []) and c["price"] > 0)
    if not prices:
        prices = sorted(c["price"] for c in crops if c["price"] > 0)
    return prices[len(prices) // 2] if prices else 1


def _festival(
    event_id: str, kind: str, name: str, season: int, days_per_season: int
) -> dict[str, Any]:
    return {
        "id": event_id,
        "kind": kind,
        "name": name,
        "season": SEASONS[season],
        "day": festival_day(season, days_per_season),
        "from": FROM_HOUR,
        "to": TO_HOUR,
        "place": PLACE,
    }


def _contest(season: int, days: int, judge: str, crops: list[dict[str, Any]]) -> dict[str, Any]:
    first = season == 1  # summer's, on a farm that cannot fish
    entry = _festival(
        "summer_fair" if first else "harvest_fair",
        PRODUCE_CONTEST,
        "Summer fair" if first else "Harvest fair",
        season,
        days,
    )
    entry["table"] = TABLE
    entry["judge"] = judge
    if judge == JUDGE_COUNT:
        entry["goal"] = COUNT_GOAL
        entry["prize"] = {"gold": COUNT_PRIZE}
    else:
        entry["goal"] = contest_goal(crops, SEASONS[season])
        entry["prize"] = {"gold": CONTEST_PRIZE}
    return entry


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The festivals of a new project: ``{"plan_version", "seed", "days_per_season",
    "festivals", "notes"}``, what is stored under ``farm.events`` (``store``)."""
    opts = normalized(options)
    known = facts if isinstance(facts, dict) else {}
    crops = [c for c in known.get("crops", []) if isinstance(c, dict)]
    days = opts["days_per_season"]
    notes: list[str] = []
    eggs = _festival("egg_hunt", EGG_HUNT, "Egg hunt", 0, days)
    eggs.update({"spots": list(EGGS), "each": EGG_EACH, "goal": EGG_SPOTS})
    eggs["prize"] = {"gold": EGG_PRIZE}
    if known.get("fishing"):
        summer = _festival("fishing_day", FISHING_COUNT, "Fishing day", 1, days)
        summer.update({"goal": FISH_GOAL, "prize": {"gold": FISH_PRIZE}})
    else:
        summer = _contest(1, days, JUDGE_COUNT, crops)
        notes.append("The farm cannot fish: summer has a produce contest by the count.")
    feast = _festival("winter_feast", FEAST, "Winter feast", 3, days)
    feast.update({"table": TABLE, "points": FEAST_POINTS})
    return {
        "plan_version": PLAN_VERSION,
        "seed": int(seed),
        "days_per_season": days,
        "festivals": [eggs, summer, _contest(2, days, JUDGE_PRICE, crops), feast],
        "notes": notes,
    }


def for_project(
    stored: dict[str, Any] | None, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any] | None, list[str]]:
    """The events a generation uses: nothing with ``festivals`` off (a stored plan is left as
    it is: ``store`` is not called); a fresh plan while the project has none (``stored`` is its
    ``farm.events``, or None), else the stored one, never planned again. Returns (section or
    None, notes)."""
    opts = normalized(options)
    if not opts["festivals"]:
        return None, []
    if stored and stored.get("festivals"):
        kept = copy.deepcopy(stored)
        notes = []
        if kept.get("days_per_season") != opts["days_per_season"]:
            notes.append(
                f"The festivals were planned for seasons of {kept.get('days_per_season')} days: "
                f"with {opts['days_per_season']} the game folds their days into the season."
            )
        return kept, notes
    fresh = plan(options, seed, facts)
    return fresh, list(fresh["notes"])


def store(farm: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    """The ``farm`` section of the world plan with the events beside its crops (a copy)."""
    out = copy.deepcopy(farm)
    out["events"] = copy.deepcopy(section)
    return out


def check(section: dict[str, Any]) -> list[str]:
    """What is wrong with the events of a plan (an empty list for good ones): two of one id, a
    kind nobody knows, a season that is none, a day the planned season does not have, two
    festivals on one day, an egg hunt without spots, a contest or a feast without a table."""
    problems: list[str] = []
    seen: set[str] = set()
    dates: set[tuple[str, int]] = set()
    days = calendar_math.season_length(int(section.get("days_per_season", 0) or 0))
    for event in section.get("festivals", []):
        which = str(event.get("id", "?"))
        if which in seen:
            problems.append(f"{which}: listed twice")
        seen.add(which)
        if event.get("kind") not in KINDS:
            problems.append(f"{which}: the unknown kind {event.get('kind')!r}")
        if event.get("season") not in SEASONS:
            problems.append(f"{which}: the unknown season {event.get('season')!r}")
        day = event.get("day")
        if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= days:
            problems.append(f"{which}: day {day!r} is not a day of a season of {days}")
        date = (str(event.get("season")), int(day) if isinstance(day, int) else 0)
        if date in dates:
            problems.append(f"{which}: a second festival on {date[0]} {date[1]}")
        dates.add(date)
        if event.get("kind") == EGG_HUNT and not event.get("spots"):
            problems.append(f"{which}: an egg hunt without spots")
        if event.get("kind") in (PRODUCE_CONTEST, FEAST) and not event.get("table"):
            problems.append(f"{which}: no table to bring it to")
    return problems


def summary(section: dict[str, Any] | None) -> str:
    """One line for the log and the report: "4 festivals: Egg hunt (spring 12), ..."."""
    events = (section or {}).get("festivals", [])
    if not events:
        return "no festivals"
    parts = [f"{e['name']} ({e['season']} {e['day']})" for e in events]
    return f"{len(events)} {'festival' if len(events) == 1 else 'festivals'}: {', '.join(parts)}"


def events_file(section: dict[str, Any] | None, village: str = "starter_map") -> dict[str, Any]:
    """What ``game/data/events.json`` holds for the events of a plan (the builder writes the
    same): each festival with the ``map`` its markers are on (the village)."""
    out = []
    for event in (section or {}).get("festivals", []):
        entry = copy.deepcopy(event)
        entry["map"] = village
        out.append(entry)
    return {"events": out}
