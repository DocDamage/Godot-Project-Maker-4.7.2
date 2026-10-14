"""The people of a farm's village (T17.09): who lives there, where, what they do all day and
what they like to be given.

Every ``NPC`` asset of the catalog is a person: an id and a name from a small list (by the
seed), a **home** (one of the village's houses, shared out evenly), a **job** when the village
has a shop (one shopkeeper), a **schedule** built from a few patterns (at home early and late,
at work or on the square by day, at the pond some afternoons, indoors when it rains) and
**tastes** drawn from the items the game has. A project whose packs have no NPC has three
people without a picture of their own (the builder gives them the stand-in NPC).

A schedule is a list of the entries of ``RpgSchedule`` (``actors/schedule.gd``): ``hour``,
optionally ``days`` (of the week, 0 to 6) and ``weather``, and a ``place``. The plan names
places, not markers: ``home``, ``work``, ``square`` and ``pond`` (``PLACES``); the builder
knows the map and the marker each is for a person (``people_file``).

What the planner needs of the village it takes as ``facts`` (how many houses, whether there is
a shop and a pond, the item ids): it does not read the map's plan. The plan is deterministic
for a seed and is **stored** in the project (``rpggen/world_plan.json``, the key ``people`` of
the section ``farm``) and reused: once it is there the seed and the options no longer change
it, and an NPC the packs gain later is appended (``extend``). The builder writes it to
``game/data/people.json`` once; that file is the user's. No Qt, no Godot.

**Birthdays** (T17.25) are added by ``with_birthdays`` to whoever has none: a season and a day
of it, by the seed and the person's id, spread over the seasons, never on the day of a festival
or on the first day of spring (the first morning of a game, when the farmer knows nobody) and no
two on one day while the year has days enough. Somebody who has a birthday keeps it, so
the people a project stored before it had birthdays get theirs without anything else of them
changing. A project with ``festivals`` off has no birthdays.

**Who can be courted** (T17.26) is added by ``with_courtable``: while nobody of the village has
the key ``courtable``, ``count`` of them are chosen by the seed (not the shopkeeper while there
are others) and every person gets ``courtable`` true or false. Once anybody has the key the
choice is made and stays: a person the packs add later is not courtable, and a changed count
changes nobody. So the people a project stored before it had marriage get the key without
anything else of them changing. ``courtable`` 0 (the option ``starter_map.courtable``) chooses
nobody and writes no key, so the people of a farm that switches it on later are chosen then.
"""

from __future__ import annotations

import copy
import re
from random import Random
from typing import Any

from rpggen.core import calendar_math

PLAN_VERSION = 1
PEOPLE_FILE = "game/data/people.json"
PLACES = ("home", "work", "square", "pond")
TASTES = ("loves", "likes", "dislikes")
# how many items of the game a person loves, likes and dislikes (fewer in a game with few)
TASTE_COUNTS = {"loves": 2, "likes": 3, "dislikes": 2}
SHOPKEEPER = "shopkeeper"
RAIN = "rain"
WEEK_DAYS = 7
DAY_FIRST_HOUR = 6  # a day runs from 6:00 to 2:00 (RpgCalendar)
# the day of the week the shop is closed and its keeper is out
SHOP_CLOSED_DAY = 6
MAX_PEOPLE = 12
PEOPLE_RANGE = (1, 40)
# the people of a village whose packs have no NPC
DRAWN_PEOPLE = 3
# how many people can be courted (T17.26: ``starter_map.courtable``; 0 turns marriage off)
COURTABLE_DEFAULT = 2
COURTABLE_RANGE = (0, 6)
COURTABLE_KEY = "courtable"
PATTERNS = ("villager", "stroller", "angler")
# what nobody is given: the tools, and seeds
NOT_GIFTS = frozenset({"hoe", "watering_can", "sickle", "farm_axe"})
NAMES = (
    "Anna", "Bert", "Clara", "Dov", "Edda", "Finn", "Greta", "Hugo", "Ida", "Jonas",
    "Kira", "Lars", "Mina", "Nils", "Olga", "Pim", "Runa", "Sven", "Tilda", "Ulf",
    "Vera", "Willa", "Yann", "Zora", "Alma", "Bruno", "Cleo", "Dag", "Elsa", "Fritz",
    "Gus", "Hanne", "Ivo", "Juna", "Karl", "Lotte", "Milo", "Nora", "Otto", "Pia",
)  # fmt: skip

_SLUG = re.compile(r"[^a-z0-9]+")


class PeoplePlanError(ValueError):
    """Options that cannot be planned; the message names the key."""


def normalized(options: Any) -> dict[str, Any]:
    """The options the planner reads: ``people``, the most people a village has (12 when it is
    not given; the packs' NPCs beyond it are left out, by the seed)."""
    raw = options if isinstance(options, dict) else {}
    most = raw.get("people", MAX_PEOPLE)
    lo, hi = PEOPLE_RANGE
    if isinstance(most, bool) or not isinstance(most, int) or not lo <= most <= hi:
        raise PeoplePlanError(f"people: {most!r} is not a number from {lo} to {hi}")
    return {"people": most}


def facts_of(
    catalog: Any,
    houses: int = 1,
    shop: bool = False,
    pond: bool = False,
    items: Any = (),
) -> dict[str, Any]:
    """What the planner needs to know: the ``NPC`` assets of the catalog (sorted by id; one that
    is switched off or missing is nobody), and of the village what the caller knows of it."""
    from rpggen.core import catalog as catalog_mod

    npcs = []
    for asset in sorted(getattr(catalog, "assets", []), key=lambda a: a.id):
        if catalog_mod.effective(asset).get("role") != "NPC":
            continue
        if asset.status in ("UNUSED", "MISSING"):
            continue
        npcs.append({"asset": str(asset.id)})
    return {
        "npcs": npcs,
        "houses": int(houses),
        "shop": bool(shop),
        "pond": bool(pond),
        "items": sorted(str(i) for i in items),
    }


def gifts_of(items: Any) -> list[str]:
    """The items of a game that can be a gift, sorted: all but the tools and the seeds."""
    found = {str(i) for i in (items or [])}
    return sorted(i for i in found if i and i not in NOT_GIFTS and not i.startswith("seed_"))


def _slug(name: str) -> str:
    return _SLUG.sub("_", name.lower()).strip("_") or "person"


def _names(count: int, rng: Random, taken: set[str]) -> list[str]:
    """``count`` names nobody has yet, in an order the seed gives. A village larger than the
    list has an Anna 2."""
    pool = list(NAMES)
    rng.shuffle(pool)
    out: list[str] = []
    round_no = 1
    while len(out) < count:
        for name in pool:
            full = name if round_no == 1 else f"{name} {round_no}"
            if _slug(full) not in taken and len(out) < count:
                taken.add(_slug(full))
                out.append(full)
        round_no += 1
    return out


def _entry(
    hour: int, place: str, days: list[int] | None = None, weather: str = ""
) -> dict[str, Any]:
    entry: dict[str, Any] = {"hour": hour}
    if days is not None:
        entry["days"] = sorted(days)
    if weather:
        entry["weather"] = weather
    entry["place"] = place
    return entry


def schedule_for(pattern: str, rng: Random, pond: bool) -> list[dict[str, Any]]:
    """The day of a person by its pattern. Every pattern begins at home at 6:00 and ends there,
    and has an entry for rain that keeps the person in (the shopkeeper works whatever the
    weather and stays in on a rainy day off).

    * ``shopkeeper``: at work from 8:00 to 18:00 on six days; on the day the shop is closed on
      the square, and at the pond in the afternoon.
    * ``villager``: on the square by day, at the pond on two afternoons a week.
    * ``stroller``: on the square in the morning and again in the afternoon, at home at noon.
    * ``angler``: at the pond in the morning on five days a week, on the square afterwards.
    """
    if pattern == SHOPKEEPER:
        off = [SHOP_CLOSED_DAY]
        work = [d for d in range(WEEK_DAYS) if d != SHOP_CLOSED_DAY]
        out = [_entry(DAY_FIRST_HOUR, "home"), _entry(8, "work", work), _entry(10, "square", off)]
        if pond:
            out.append(_entry(14, "pond", off))
        return [*out, _entry(18, "home"), _entry(10, "home", off, RAIN)]
    if pattern == "stroller":
        first = rng.choice((9, 10))
        return [
            _entry(DAY_FIRST_HOUR, "home"),
            _entry(first, "square"),
            _entry(13, "home"),
            _entry(16, "square"),
            _entry(rng.choice((19, 20)), "home"),
            _entry(first, "home", None, RAIN),
        ]
    if pattern == "angler" and pond:
        days = rng.sample(range(WEEK_DAYS), 5)
        return [
            _entry(DAY_FIRST_HOUR, "home"),
            _entry(8, "pond", days),
            _entry(12, "square"),
            _entry(rng.choice((17, 18)), "home"),
            _entry(8, "home", None, RAIN),
        ]
    first = rng.choice((8, 9, 10))
    out = [_entry(DAY_FIRST_HOUR, "home"), _entry(first, "square")]
    if pond:
        out.append(_entry(14, "pond", rng.sample(range(WEEK_DAYS), 2)))
    return [*out, _entry(rng.choice((18, 19, 20)), "home"), _entry(first, "home", None, RAIN)]


def tastes_for(rng: Random, gifts: list[str]) -> dict[str, list[str]]:
    """What a person loves, likes and dislikes: items of the game, none of them twice. A game
    with few items shares them out as far as they go, the loved ones first."""
    pool = list(gifts)
    rng.shuffle(pool)
    out: dict[str, list[str]] = {}
    for taste in TASTES:
        count = min(TASTE_COUNTS[taste], len(pool))
        out[taste] = sorted(pool[:count])
        pool = pool[count:]
    return out


def _person(
    name: str, asset: str, index: int, job: str, pattern: str, seed: int, facts: dict[str, Any]
) -> dict[str, Any]:
    person_id = _slug(name)
    rng = Random(f"{int(seed)}:person:{person_id}")
    houses = max(1, int(facts.get("houses", 1) or 1))
    return {
        "id": person_id,
        "name": name,
        "asset": asset,
        "home": 1 + index % houses,
        "job": job,
        "pattern": pattern,
        "schedule": schedule_for(pattern, rng, bool(facts.get("pond"))),
        **tastes_for(rng, gifts_of(facts.get("items"))),
    }


def _patterns(count: int, rng: Random, shop: bool, pond: bool) -> list[tuple[str, str]]:
    """(job, pattern) for each of ``count`` people: the first keeps the shop when there is one,
    the others take the patterns in turn."""
    kinds = [p for p in PATTERNS if pond or p != "angler"]
    rng.shuffle(kinds)
    out: list[tuple[str, str]] = []
    for i in range(count):
        if i == 0 and shop:
            out.append((SHOPKEEPER, SHOPKEEPER))
        else:
            out.append(("", kinds[(i - (1 if shop else 0)) % len(kinds)]))
    return out


def _facts(facts: Any) -> dict[str, Any]:
    return dict(facts) if isinstance(facts, dict) else {}


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The people of a new project: ``{"plan_version", "seed", "people", "notes"}``. ``people``
    is what is stored under ``farm.people`` (``store``)."""
    opts = normalized(options)
    known = _facts(facts)
    notes: list[str] = []
    assets = sorted({str(n.get("asset", "")) for n in known.get("npcs", []) if n.get("asset")})
    rng = Random(f"{int(seed)}:people")
    rng.shuffle(assets)
    if not assets:
        assets = [""] * min(DRAWN_PEOPLE, opts["people"])
        notes.append(f"The packs have no NPC: {len(assets)} people share the stand-in.")
    elif len(assets) > opts["people"]:
        notes.append(f"The packs have {len(assets)} NPCs: the village has {opts['people']}.")
        assets = assets[: opts["people"]]
    if int(known.get("houses", 1) or 0) < 1:
        notes.append("The village has no house: everybody lives in house 1.")
    names = _names(len(assets), rng, set())
    kinds = _patterns(len(assets), rng, bool(known.get("shop")), bool(known.get("pond")))
    people = [
        _person(names[i], asset, i, kinds[i][0], kinds[i][1], seed, known)
        for i, asset in enumerate(assets)
    ]
    return {"plan_version": PLAN_VERSION, "seed": int(seed), "people": people, "notes": notes}


def extend(
    stored: list[dict[str, Any]], seed: int, facts: Any
) -> tuple[list[dict[str, Any]], list[str]]:
    """The stored people with the NPCs of ``facts`` nobody is yet appended (an NPC added to the
    packs later). Nothing of who is there changes, and a shop that came later gets no keeper
    by itself. Returns (people, names added)."""
    known = _facts(facts)
    out = copy.deepcopy(stored)
    have = {str(p.get("asset", "")) for p in out}
    taken = {str(p["id"]) for p in out}
    new = sorted({str(n.get("asset", "")) for n in known.get("npcs", [])} - have - {""})
    rng = Random(f"{int(seed)}:people:{len(out)}")
    names = _names(len(new), rng, taken)
    kinds = [p for p in PATTERNS if known.get("pond") or p != "angler"]
    for i, asset in enumerate(new):
        index = len(out)
        out.append(_person(names[i], asset, index, "", kinds[index % len(kinds)], seed, known))
    return out, names


def for_project(
    stored: list[dict[str, Any]] | None, options: Any, seed: int, facts: Any = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """The people a generation uses: a fresh plan while the project has none (``stored`` is the
    ``people`` of its ``farm`` section, or None), else the stored ones, never planned again, with
    the NPCs the packs have gained. Returns (people, notes)."""
    if stored:
        extended, added = extend(stored, seed, facts)
        note = f"The village kept its people; added: {', '.join(added)}."
        return extended, [note] if added else []
    fresh = plan(options, seed, facts)
    return fresh["people"], list(fresh["notes"])


def with_birthdays(
    people: list[dict[str, Any]],
    seed: int,
    days_per_season: int = calendar_math.DAYS_PER_SEASON,
) -> list[dict[str, Any]]:
    """The people, each with a ``birthday`` ``{"season", "day"}`` (a copy). Who has one keeps
    it; the others get theirs in the order of the list: the season that has the fewest
    birthdays so far (of several, one by the seed and the person's id), and a day of it that is
    no festival's, not the first of spring and nobody else's (anybody's, once every such day of
    the year is taken)."""
    from rpggen.core import event_plan

    length = calendar_math.season_length(days_per_season)
    seasons = calendar_math.SEASONS
    festivals = {(seasons[s], d) for s, d in event_plan.festival_days(length)}
    festivals.add((seasons[0], 1))  # the first morning of a game is nobody's birthday
    out = copy.deepcopy(people)
    taken: set[tuple[str, int]] = set()
    counts = dict.fromkeys(seasons, 0)
    for person in out:
        born = person.get("birthday")
        if isinstance(born, dict) and born.get("season") in seasons:
            taken.add((str(born["season"]), int(born.get("day", 0) or 0)))
            counts[str(born["season"])] += 1
    for person in out:
        born = person.get("birthday")
        if isinstance(born, dict) and born.get("season") in seasons:
            continue
        rng = Random(f"{int(seed)}:birthday:{person.get('id', '')}")
        every = {s: [d for d in range(1, length + 1) if (s, d) not in festivals] for s in seasons}
        free = {s: [d for d in days if (s, d) not in taken] for s, days in every.items()}
        pool = free if any(free.values()) else every
        fewest = min(counts[s] for s in seasons if pool[s])
        season = rng.choice([s for s in seasons if pool[s] and counts[s] == fewest])
        day = rng.choice(pool[season])
        person["birthday"] = {"season": season, "day": day}
        taken.add((season, day))
        counts[season] += 1
    return out


def courtable_count(options: Any) -> int:
    """How many people can be courted by the options (``starter_map.courtable``; 2 when it is
    not given). Raises a ``PeoplePlanError`` for a value that is no number of the range."""
    raw = options if isinstance(options, dict) else {}
    count = raw.get(COURTABLE_KEY, COURTABLE_DEFAULT)
    lo, hi = COURTABLE_RANGE
    if isinstance(count, bool) or not isinstance(count, int) or not lo <= count <= hi:
        raise PeoplePlanError(f"courtable: {count!r} is not a number from {lo} to {hi}")
    return count


def with_courtable(people: list[dict[str, Any]], seed: int, count: int) -> list[dict[str, Any]]:
    """The people, each with ``courtable`` true or false (a copy). While nobody has the key,
    ``count`` people are chosen by the seed (the shopkeeper last: only when there are too few
    others); once somebody has it, whoever lacks it (a person added later) is not courtable and
    nobody else changes. ``count`` 0 chooses nobody and adds no key."""
    out = copy.deepcopy(people)
    if any(COURTABLE_KEY in p for p in out):
        for person in out:
            person.setdefault(COURTABLE_KEY, False)
        return out
    if count <= 0:
        return out
    ids = sorted(str(p.get("id", "")) for p in out)
    rng = Random(f"{int(seed)}:courtable")
    rng.shuffle(ids)
    keepers = {str(p.get("id", "")) for p in out if p.get("job") == SHOPKEEPER}
    ordered = [i for i in ids if i not in keepers] + [i for i in ids if i in keepers]
    chosen = set(ordered[:count])
    for person in out:
        person[COURTABLE_KEY] = str(person.get("id", "")) in chosen
    return out


def courtable(people: list[dict[str, Any]]) -> list[str]:
    """The ids of the people who can be courted, in the order of the list."""
    return [str(p["id"]) for p in people if p.get(COURTABLE_KEY) is True]


def store(farm: dict[str, Any], people: list[dict[str, Any]], notes: Any = ()) -> dict[str, Any]:
    """The ``farm`` section of the world plan with the people beside its crops (a copy)."""
    out = copy.deepcopy(farm)
    out["people"] = copy.deepcopy(people)
    out["notes"] = [*out.get("notes", []), *[n for n in notes if n not in out.get("notes", [])]]
    return out


def check(people: list[dict[str, Any]], facts: Any = None) -> list[str]:
    """What is wrong with the people of a plan (an empty list for good ones): somebody without
    a home or with a schedule that does not cover every day, an entry that names no known
    place, work for somebody without a job, two people of one id, two shopkeepers, a birthday
    that is no season and day. With
    ``facts``, also a home the village does not have, the pond or the shop of a village
    without one, and a taste for an item the game does not have."""
    known = _facts(facts) if facts is not None else None
    problems: list[str] = []
    seen: set[str] = set()
    keepers = 0
    for person in people:
        who = str(person.get("id", "?"))
        if who in seen:
            problems.append(f"{who}: listed twice")
        seen.add(who)
        keepers += person.get("job") == SHOPKEEPER
        home = person.get("home")
        if isinstance(home, bool) or not isinstance(home, int) or home < 1:
            problems.append(f"{who}: has no home")
        elif known is not None and home > max(1, int(known.get("houses", 1) or 1)):
            problems.append(f"{who}: lives in house {home}, which the village does not have")
        schedule = person.get("schedule") or []
        if not any(not e.get("days") and not e.get("weather") for e in schedule):
            problems.append(f"{who}: the schedule has no entry for every day")
        for entry in schedule:
            place = entry.get("place")
            if place not in PLACES:
                problems.append(f"{who}: the schedule names the unknown place {place!r}")
            elif place == "work" and not person.get("job"):
                problems.append(f"{who}: goes to work without a job")
            elif known is not None and place == "pond" and not known.get("pond"):
                problems.append(f"{who}: goes to a pond the village does not have")
            elif known is not None and place == "work" and not known.get("shop"):
                problems.append(f"{who}: works in a shop the village does not have")
            if not 0 <= int(entry.get("hour", -1)) <= 23:
                problems.append(f"{who}: an entry at the hour {entry.get('hour')!r}")
        if "birthday" in person:
            born = person["birthday"] if isinstance(person["birthday"], dict) else {}
            day = born.get("day")
            if born.get("season") not in calendar_math.SEASONS:
                problems.append(f"{who}: a birthday in the unknown season {born.get('season')!r}")
            if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 28:
                problems.append(f"{who}: a birthday on the day {day!r}")
        if COURTABLE_KEY in person and not isinstance(person[COURTABLE_KEY], bool):
            problems.append(f"{who}: courtable is {person[COURTABLE_KEY]!r}, not true or false")
        listed = [item for taste in TASTES for item in person.get(taste, [])]
        if len(listed) != len(set(listed)):
            problems.append(f"{who}: an item in two tastes")
        if known is not None:
            for item in sorted(set(listed) - set(gifts_of(known.get("items")))):
                problems.append(f"{who}: a taste for {item}, which the game does not have")
    if keepers > 1:
        problems.append(f"{keepers} shopkeepers: a shop has one")
    return problems


def summary(people: list[dict[str, Any]]) -> str:
    """One line for the log and the report: "3 people: Anna (shopkeeper, house 1), ..."."""
    parts = [
        f"{p['name']} ({p['job'] + ', ' if p.get('job') else ''}house {p['home']})" for p in people
    ]
    return f"{len(people)} {'person' if len(people) == 1 else 'people'}: {', '.join(parts)}"


def people_file(
    people: list[dict[str, Any]],
    places: dict[str, Any] | None = None,
    scenes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """What ``game/data/people.json`` holds for the people of a plan (the builder writes the
    same): each person without what only the planner needs (``asset``, ``pattern``), with its
    ``scene`` when ``scenes`` names it, and with the places of its schedule turned into the
    map and the marker (or the cell) they are for this person.

    ``places`` says where each place is: ``home`` a list with one entry a house (the first is
    house 1), ``work``, ``square`` and ``pond`` one entry each; an entry is ``{"map", "place"}``
    or ``{"map", "cell"}``, optionally with a ``facing``. A place it does not name keeps its
    name and gets no map: the marker ``home`` of the map the NPC is on."""
    where = places or {}
    out = []
    for person in people:
        entry = {k: copy.deepcopy(v) for k, v in person.items() if k not in ("asset", "pattern")}
        entry["scene"] = (scenes or {}).get(str(person["id"]), "")
        entry["schedule"] = [_placed(e, int(person["home"]), where) for e in person["schedule"]]
        out.append(entry)
    return {"people": out}


def _placed(entry: dict[str, Any], home: int, where: dict[str, Any]) -> dict[str, Any]:
    name = str(entry["place"])
    spot = where.get(name)
    if name == "home" and isinstance(spot, list):
        spot = spot[home - 1] if 0 < home <= len(spot) else None
    if not isinstance(spot, dict):
        return copy.deepcopy(entry)
    out = {k: copy.deepcopy(v) for k, v in entry.items() if k != "place"}
    out.update(copy.deepcopy(spot))
    return out
