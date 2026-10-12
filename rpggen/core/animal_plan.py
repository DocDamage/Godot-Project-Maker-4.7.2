"""The animals of a farm (T17.07): which kinds the game has, where each lives, what it gives and
what that is worth.

Every sprite of the catalog with the role ``ANIMAL`` is a picture of an animal. Its **kind**
(``hen``, ``cow``) is the word of its tags or of its name that names an animal; its **house**
follows from the kind (a hen, a chicken and a duck live in the coop; a cow, a sheep, a goat, a
pig and every animal nobody knows live in the barn); its **product** and the prices come from
a small table. The pictures of one kind are its **variants**: one for each colour of each
animal the packs drew (``hen_01`` in black, brown and white), with the strip it walks in and,
when it is another file, the strip it sleeps in. A project whose packs have no animal has the
drawn hen of the farm kit (``farm_kit.py``, T17.02) in its catalog, and it is planned like any
other.

Only the kinds whose house the farm has are planned (``facts["houses"]``, from the farm's own
plan): a farm with ``animals: none`` has no plan of its animals at all (``for_project`` gives
``None``), and nothing of the animals is written for it.

The plan is deterministic for a seed (the seed gives the order of the names an animal gets when
it is bought) and is **stored** in the project (``rpggen/world_plan.json``, the key ``animals``
of the section ``farm``) and reused: once it is there the seed no longer changes it, and a kind
or a colour the packs gain later is appended (``extend``). The builder writes it with the
scenes and the houses to ``generated/data/animals.json`` on every build and to
``game/data/animals.json`` once; that file is the user's. The planner reads no option: what the
options say of animals (``animals``) is in the farm's plan as the houses it has. No Qt, no Godot.
"""

from __future__ import annotations

import copy
import re
from random import Random
from typing import Any

PLAN_VERSION = 1
ANIMALS_FILE = "game/data/animals.json"
PLANNED_FILE = "generated/data/animals.json"
MAPS_DIR = "res://game/maps/"
FARM_MAP = MAPS_DIR + "farm.tscn"
COOP = "coop"
BARN = "barn"
HOUSES = (COOP, BARN)
# the words of a tag or a name that say what an animal is -> its kind
COOP_KINDS = {
    "hen": "hen", "hens": "hen", "chicken": "chicken", "chickens": "chicken",
    "duck": "duck", "ducks": "duck",
}  # fmt: skip
BARN_KINDS = {
    "cow": "cow", "cows": "cow", "sheep": "sheep", "goat": "goat", "goats": "goat",
    "pig": "pig", "pigs": "pig",
}  # fmt: skip
KIND_WORDS = {**COOP_KINDS, **BARN_KINDS}
# kind -> (the item it gives, the item's name, what one sells for)
PRODUCTS = {
    "hen": ("egg", "Egg", 25),
    "chicken": ("egg", "Egg", 25),
    "duck": ("duck_egg", "Duck egg", 35),
    "cow": ("milk", "Milk", 60),
    "goat": ("goat_milk", "Goat milk", 50),
    "sheep": ("wool", "Wool", 70),
    "pig": ("truffle", "Truffle", 90),
}
OTHER_PRICE = 40  # what the product of an animal nobody knows sells for
COST_FACTOR = 6  # an animal costs this many of its products
LARGE_FACTOR = (3, 2)  # the product of an animal that is a friend sells for 3/2
# how the product is taken: it lies in the house in the morning, or the animal is asked for it
ON_THE_FLOOR = "floor"
BY_HAND = "hand"
FEED = {"item": "hay", "name": "Hay", "price": 10}
# what an animal is called when it is bought, in an order the seed gives
NAMES = (
    "Dot", "Bess", "Pip", "Clover", "Daisy", "Nell", "Mabel", "Poppy", "Hazel", "Juno",
    "Fern", "Midge", "Olive", "Tansy", "Birdie", "Maple",
)  # fmt: skip
# the words of a name that say no kind: what an animal does and where it looks
NOT_A_KIND = frozenset(
    {"move", "walk", "run", "idle", "sleep", "dead", "fly", "eat", "down", "up", "left", "right",
     "frames", "frame", "animal", "animals", "livestock", "sheet", "strip"}
)  # fmt: skip

_WORDS = re.compile(r"[a-z]+")
# a number after the name is the animal's (`cow_01`), not a cell size or a frame count (`cow_32x32`)
_BREED = re.compile(r"^([a-z]+(?:_\d+(?![0-9a-z]))?)")
_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    return _SLUG.sub("_", name.lower()).strip("_")


def kind_of(asset_id: str, tags: Any = ()) -> str:
    """The kind of the animal a picture shows: the word of its tags that names an animal, else
    the last such word of its id (``ranch.animals.chickens.hen_01...`` is a ``hen``: its own name
    counts before its folder's), else the first word of its name that says nothing else."""
    for tag in tags or ():
        if str(tag) in KIND_WORDS:
            return KIND_WORDS[str(tag)]
    words = _WORDS.findall(asset_id.lower())
    for word in reversed(words):
        if word in KIND_WORDS:
            return KIND_WORDS[word]
    last = _WORDS.findall(asset_id.rsplit(".", 1)[-1].lower())
    return next((w for w in last if w not in NOT_A_KIND and len(w) > 1), "animal")


def house_of(kind: str) -> str:
    """Where a kind lives: the coop for a hen, a chicken and a duck, the barn for all others."""
    return COOP if kind in COOP_KINDS.values() else BARN


def breed_of(asset_id: str) -> str:
    """``ranch.animals.cows.cow_01.brown.move.cow_01_brown_move_down_32x32_4frames`` ->
    ``cow_01``: the first word of the picture's own name with the number that follows it."""
    found = _BREED.match(asset_id.rsplit(".", 1)[-1].lower())
    return found.group(1) if found else "animal"


def facts_of(catalog: Any, houses: Any = ()) -> dict[str, Any]:
    """What the planner needs to know: the animal houses the farm has (``houses``, of the farm's
    own plan: ``houses_of``), and the sprites of the catalog with the role ``ANIMAL``, sorted by
    id, each ``{asset, kind, breed, colour, walk, sleep}`` (whether it has a strip to walk in
    and one to sleep in). One that is switched off, missing or has no animation is no animal."""
    from rpggen.core import catalog as catalog_mod

    animals = []
    for asset in sorted(getattr(catalog, "assets", []), key=lambda a: a.id):
        facets = catalog_mod.effective(asset)
        animations = facets.get("animations") or {}
        if facets.get("role") != "ANIMAL" or facets.get("usage") != "sprite" or not animations:
            continue
        if asset.status in ("UNUSED", "MISSING"):
            continue
        animals.append(
            {
                "asset": str(asset.id),
                "kind": kind_of(str(asset.id), facets.get("tags") or ()),
                "breed": breed_of(str(asset.id)),
                "colour": catalog_mod.colour_name(asset),
                "walk": any(str(name).startswith(("walk", "idle")) for name in animations),
                "sleep": any(str(name).startswith("sleep") for name in animations),
            }
        )
    return {"houses": [h for h in HOUSES if h in set(houses or ())], "animals": animals}


def houses_of(farm_map: Any) -> list[dict[str, Any]]:
    """The animal houses of a farm's own plan (``farm.map``) as the game needs them: ``kind``,
    the scene of the room (``map``), the scene of the map its yard is on (``yard_map``) and how
    many animals it has room for (``stalls``)."""
    out = []
    for building in (farm_map or {}).get("animal_houses", []):
        room = building.get("interior", {})
        out.append(
            {
                "kind": str(building["kind"]),
                "map": f"{MAPS_DIR}{room.get('id', building.get('id', ''))}.tscn",
                "yard_map": FARM_MAP,
                "stalls": len(room.get("stalls", [])),
            }
        )
    return out


def _variants(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The variants of one kind: a picture for each colour of each animal drawn, by its name."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for fact in facts:
        groups.setdefault((str(fact["breed"]), str(fact.get("colour", ""))), []).append(fact)
    out = []
    for (breed, colour), members in sorted(groups.items()):
        members.sort(key=lambda f: str(f["asset"]))
        walk = next((f for f in members if f.get("walk")), None)
        if walk is None:
            continue  # it only sleeps: nothing to show by day
        sleep = walk if walk.get("sleep") else next((f for f in members if f.get("sleep")), None)
        out.append(
            {
                "id": _slug(f"{breed}_{colour}" if colour else breed),
                "colour": colour,
                "asset": str(walk["asset"]),
                "sleep": str(sleep["asset"]) if sleep is not None and sleep is not walk else "",
            }
        )
    return out


def _entry(kind: str, variants: list[dict[str, Any]]) -> dict[str, Any]:
    product, product_name, price = PRODUCTS.get(
        kind, (f"{kind}_product", f"{kind.capitalize()} product", OTHER_PRICE)
    )
    house = house_of(kind)
    return {
        "id": kind,
        "name": kind.replace("_", " ").capitalize(),
        "house": house,
        "ticket": f"animal_{kind}",
        "cost": price * COST_FACTOR,
        "product": product,
        "product_name": product_name,
        "price": price,
        "large": f"{product}_large",
        "large_price": price * LARGE_FACTOR[0] // LARGE_FACTOR[1],
        "collect": ON_THE_FLOOR if house == COOP else BY_HAND,
        "variants": variants,
    }


def _by_kind(facts: Any) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for fact in (facts or {}).get("animals", []):
        found.setdefault(_slug(str(fact["kind"])) or "animal", []).append(dict(fact))
    return found


def _house_notes(kinds: list[dict[str, Any]], houses: list[str]) -> list[str]:
    return [
        f"The packs have no animal for the {house}: it stays empty."
        for house in houses
        if not any(k["house"] == house for k in kinds)
    ]


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The ``animals`` of a new farm: the kinds whose house the farm has, the coop's first, each
    with its variants; the feed; and the names in an order the seed gives. ``options`` is not
    read (see the top of the file)."""
    del options
    houses = [h for h in HOUSES if h in set((facts or {}).get("houses", []))]
    kinds = []
    for kind, members in _by_kind(facts).items():
        variants = _variants(members)
        if variants and house_of(kind) in houses:
            kinds.append(_entry(kind, variants))
    kinds.sort(key=lambda k: (HOUSES.index(k["house"]), k["id"]))
    names = list(NAMES)
    Random(f"{int(seed)}:animals").shuffle(names)
    return {
        "plan_version": PLAN_VERSION,
        "seed": int(seed),
        "feed": dict(FEED),
        "names": names,
        "kinds": kinds,
        "notes": _house_notes(kinds, houses),
    }


def extend(stored: dict[str, Any], facts: Any) -> tuple[dict[str, Any], list[str]]:
    """The stored plan with what the packs have gained appended: a kind it does not have (when
    the farm has its house), and a variant of a kind it has. Nothing of what is there changes.
    Returns (plan, what was added)."""
    out = copy.deepcopy(stored)
    houses = set((facts or {}).get("houses", []))
    have = {str(k["id"]): k for k in out["kinds"]}
    added: list[str] = []
    for kind, members in sorted(_by_kind(facts).items()):
        variants = _variants(members)
        if kind in have:
            known = {str(v["asset"]) for v in have[kind]["variants"]}
            ids = {str(v["id"]) for v in have[kind]["variants"]}
            for variant in variants:
                if variant["asset"] not in known and variant["id"] not in ids:
                    have[kind]["variants"].append(variant)
                    added.append(f"{have[kind]['name']} ({variant['colour'] or variant['id']})")
        elif variants and house_of(kind) in houses:
            entry = _entry(kind, variants)
            out["kinds"].append(entry)
            added.append(str(entry["name"]))
    return out, added


def for_project(
    stored: dict[str, Any] | None, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any] | None, list[str]]:
    """The animals a generation uses: nothing (``None``) for a farm without an animal house that
    has no plan of them; a fresh plan while the project has none (``stored`` is the ``animals``
    of its ``farm`` section, or None); else the stored one, never planned again, with what the
    packs have gained. Returns (plan or None, notes)."""
    if stored and "kinds" in stored:
        extended, added = extend(stored, facts)
        return extended, [f"The farm kept its animals; added: {', '.join(added)}."] if added else []
    if not (facts or {}).get("houses"):
        return None, []
    fresh = plan(options, seed, facts)
    return fresh, list(fresh["notes"])


def store(farm: dict[str, Any], animals: dict[str, Any] | None) -> dict[str, Any]:
    """The ``farm`` section of the world plan with the animals beside its crops (a copy); as it
    is for a farm that has none."""
    out = copy.deepcopy(farm)
    if animals is not None:
        out["animals"] = copy.deepcopy(animals)
    return out


def check(section: dict[str, Any]) -> list[str]:
    """What is wrong with a plan (an empty list for a good one): two kinds of one id, a kind
    without a picture, in a house nobody knows, or whose product is worth nothing."""
    problems: list[str] = []
    seen: set[str] = set()
    for kind in section.get("kinds", []):
        who = str(kind.get("id", "?"))
        if who in seen:
            problems.append(f"{who}: listed twice")
        seen.add(who)
        if kind.get("house") not in HOUSES:
            problems.append(f"{who}: lives in {kind.get('house')!r}, which is no animal house")
        if not kind.get("variants"):
            problems.append(f"{who}: has no picture")
        if int(kind.get("price", 0)) <= 0 or int(kind.get("cost", 0)) <= 0:
            problems.append(f"{who}: its product or the animal itself has no price")
        if kind.get("collect") not in (ON_THE_FLOOR, BY_HAND):
            problems.append(f"{who}: its product is taken {kind.get('collect')!r}")
    return problems


def summary(section: dict[str, Any]) -> str:
    """One line for the log and the report: "2 kinds of animal: Hen (coop, 3 colours), ..."."""
    kinds = section.get("kinds", [])
    parts = []
    for kind in kinds:
        count = len(kind["variants"])
        colours = f", {count} colours" if count > 1 else ""
        parts.append(f"{kind['name']} ({kind['house']}{colours})")
    what = "kind" if len(kinds) == 1 else "kinds"
    return f"{len(kinds)} {what} of animal{': ' if parts else ''}{', '.join(parts)}"


def animals_file(
    section: dict[str, Any],
    houses: list[dict[str, Any]] | None = None,
    scenes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """What ``game/data/animals.json`` holds for a plan (the builder writes the same): the kinds
    with the scene of each variant when ``scenes`` names it (by ``<kind>.<variant>``), the feed,
    the names, and the houses of the farm (``houses_of``)."""
    kinds = []
    for kind in section.get("kinds", []):
        entry = copy.deepcopy(kind)
        for variant in entry["variants"]:
            variant["scene"] = (scenes or {}).get(f"{kind['id']}.{variant['id']}", "")
        kinds.append(entry)
    return {
        "animals": kinds,
        "feed": copy.deepcopy(section.get("feed", FEED)),
        "names": list(section.get("names", NAMES)),
        "houses": copy.deepcopy(houses or []),
    }
