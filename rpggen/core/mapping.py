"""Starter mapping: which asset fills which required or recommended role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rpggen.core import catalog as catalog_mod
from rpggen.core import classifier, requirements

# role -> key in ``config.starter``; roles without a key (WALL, UI) only need to exist.
ROLE_KEYS = {
    "PLAYER": "player",
    "NPC": "npc",
    "ENEMY": "enemy",
    "GROUND": "ground",
    "BUILDING": "building",
    "ITEM": "chest",
    "PORTRAIT": "portrait",
    "BOSS": "boss",  # the guardian of a metroidvania (T14.02)
    "VEHICLE": "vehicle",  # the car of a racing game (T16.03)
    "PROJECTILE": "projectile",
    "EXPLOSION": "explosion",
}
# Asset usages a role can plausibly come from (the picker is restricted to these).
PLAUSIBLE_USAGE: dict[str, set[str]] = {
    "PLAYER": {"sprite"},
    "NPC": {"sprite"},
    "ENEMY": {"sprite"},
    "GROUND": {"tiles"},
    "WALL": {"tiles"},
    "BUILDING": {"object", "tiles", "background"},
    "ITEM": {"object", "sprite"},
    "PORTRAIT": {"portrait", "sprite"},
    "UI": {"ui"},
    "BOSS": {"sprite"},
    "BACKGROUND": {"background"},
    "DECORATION": {"object", "sprite", "tiles"},
    "VEHICLE": {"sprite"},
    "PROJECTILE": {"sprite"},
    "EXPLOSION": {"sprite"},
    "POWERUP": {"sprite", "object"},
    "HAZARD": {"sprite", "object", "tiles"},
    "CROP": {"growth_strip", "sprite", "object"},  # the farm's (T17.02)
    "ANIMAL": {"sprite"},
    "TOOL": {"sprite", "object"},
}
OBJECT_ROLES = requirements.OBJECT_ROLES  # roles that can also be filled with a SheetObject
_INACTIVE = {"UNUSED", "MISSING"}
TOP_DOWN = "top_down"
ISOMETRIC = catalog_mod.PROJECTION_ISOMETRIC


def plausible_usage(role: str, projection: str = TOP_DOWN) -> set[str]:
    """The usages ``role`` can come from in a project seen in ``projection``: an isometric
    project (T17.13) takes what a top-down one takes from a sheet of tiles from the single
    tiles of an isometric pack."""
    usages = PLAUSIBLE_USAGE.get(role, set())
    if projection == ISOMETRIC and "tiles" in usages:
        return (usages - {"tiles"}) | {catalog_mod.ISO_TILE_USAGE}
    return usages


@dataclass(frozen=True)
class RoleRow:
    role: str
    required: bool
    key: str | None  # starter key, None for WALL / UI


def rows(archetype: str) -> list[RoleRow]:
    required = requirements.REQUIRED.get(archetype, requirements.REQUIRED["turn_based"])
    ordered = [*required, *(r for r in requirements.recommended(archetype) if r not in required)]
    return [RoleRow(r, r in required, ROLE_KEYS.get(r)) for r in ordered]


def _usable(asset: catalog_mod.Asset, projection: str = TOP_DOWN) -> bool:
    # what was drawn for the other view is no choice for a role (T17.13): an isometric tile in
    # a top-down project, a sheet of squares in an isometric one
    return (
        asset.status not in _INACTIVE
        and asset.kind == "image"
        and catalog_mod.fits_projection(asset, projection)
    )


def assets_with_role(
    catalog: catalog_mod.Catalog, role: str, projection: str = TOP_DOWN
) -> list[catalog_mod.Asset]:
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if _usable(a, projection) and catalog_mod.effective(a).get("role") == role
    ]


def objects_with_role(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.SheetObject]:
    return [o for o in sorted(catalog.objects, key=lambda o: o.id) if o.role == role]


def _is_variant(asset: catalog_mod.Asset) -> bool:
    return "derived_from" in asset.detected


def _later_turn(asset: catalog_mod.Asset) -> bool:
    """True for the second to the last turn of a tile (T17.12): the first stands for all."""
    return bool(catalog_mod.turn_name(asset))


def _later_season(asset: catalog_mod.Asset) -> bool:
    """True for a sheet that comes once a season and is not the first of its group (T17.01):
    the first stands for all, since the game swaps them with the calendar. Without this the
    ground of a farming pack was its autumn (the first by name), not its spring."""
    from rpggen.core import classifier

    tags = [str(tag) for tag in asset.detected.get("tags") or []]
    return bool(catalog_mod.season_name(asset)) and any(
        tag.startswith(classifier.VARIANT_TAG) for tag in tags
    )


def _worked_soil(asset: catalog_mod.Asset) -> bool:
    """True for a sheet of tilled or watered soil (the tags of T17.01). It has the role of a
    ground, which is how a farm's field finds it, and it is never the ground a map is laid
    with while the packs have another: the village of a farming pack stood on tilled soil,
    the sheet its reader was surest of."""
    tags = {str(tag) for tag in asset.detected.get("tags") or []}
    return bool(tags & {"soil", "watered"})


OPEN_GROUND_WORDS = (
    frozenset({"grass", "lawn", "meadow"}),  # what a field, a village and a track lie on
    frozenset({"ground", "dirt", "earth", "soil", "land", "sand", "snow"}),
)


def open_ground_rank(asset: catalog_mod.Asset) -> int:
    """How good a ground of an isometric map a tile is, the lower the better: a flat tile
    whose name or surface says grass (the reader tags a plain green tile ``surface:grass``),
    then one that says earth, then any other flat tile, and a raised piece or one that joins
    on some sides last (a roof, a block, a ramp, a river bank: height is not modelled). The
    isometric packs name every tile, and the first by name is a paving as often as a meadow.
    The same choice as the field of an isometric track (``iso_track.gd``), for every map."""
    facets = catalog_mod.effective(asset)
    ranks = len(OPEN_GROUND_WORDS)
    if int(facets.get("rise") or 0) > 0 or facets.get("edge") or facets.get("joins"):
        return ranks + 1
    tags = {str(tag) for tag in facets.get("tags") or []}
    said = {tag.removeprefix("surface:") for tag in tags} | set(classifier.tokens(asset.path)[1])
    for rank, words in enumerate(OPEN_GROUND_WORDS):
        if said & words:
            return rank
    return ranks


def candidates(
    catalog: catalog_mod.Catalog, role: str, projection: str = TOP_DOWN
) -> list[catalog_mod.Asset]:
    """Assets the picker offers for ``role``: plausible usage, assets that already have the role
    first."""
    usages = plausible_usage(role, projection)
    pool = [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if _usable(a, projection) and catalog_mod.effective(a).get("usage") in usages
    ]
    return sorted(
        pool,
        key=lambda a: (
            catalog_mod.effective(a).get("role") != role,
            _is_variant(a),
            -a.confidence,
            a.id,
        ),
    )


def best_for(catalog: catalog_mod.Catalog, role: str, projection: str = TOP_DOWN) -> str | None:
    """The asset (or object, for buildings) that fills a role by default."""
    # a drawn stand-in of the farm (T17.02) is found by the farm's recipes, by its tag: it is
    # never the chest or the scenery of a map by itself
    found = [
        a
        for a in assets_with_role(catalog, role, projection)
        if a.pack_id != requirements.FARM_KIT_PACK
    ]
    if found:
        # a farming pack's ground is chosen as an isometric map's is (T17.29): grass before a
        # shadow, a path or a bridge (*Farm RPG* was laid with its sheet of shadows)
        farms = {p.pack_id for p in catalog.packs if catalog_mod.VIEW_FARM in p.warnings}

        def ground_rank(a: catalog_mod.Asset) -> int:
            if role == "BUILDING" and a.pack_id in farms:
                # ... and its house the largest building, not a market stall; a house by its
                # name before a barn or a coop (T17.33)
                w, h = (catalog_mod.effective(a).get("frame") or [0, 0])[:2]
                return -int(w) * int(h)
            if role != "GROUND" or (projection == TOP_DOWN and a.pack_id not in farms):
                return 0
            rank = open_ground_rank(a)
            tags = {str(t) for t in catalog_mod.effective(a).get("tags") or []}
            if a.pack_id in farms and any(
                t.startswith("season:") and t != "season:spring" for t in tags
            ):
                rank += len(OPEN_GROUND_WORDS) + 1  # a farm begins in spring (T17.33)
            if a.pack_id in farms and set(classifier.tokens(a.path)[1]) & {"forest", "deep"}:
                rank += 1  # a wood's darker grass after the meadow's
            if a.pack_id in farms and set(classifier.tokens(a.path)[1]) & NOT_FARM_GROUND_WORDS:
                # T17.33: a farm is laid with its meadow, not with the grass of its caves
                # (*Farm RPG*'s ``Tileset Grass Caves`` was its farm's ground)
                rank += len(OPEN_GROUND_WORDS) + 2
            return rank

        # a recolour variant (T13.18) never takes a role from the pack's own asset by itself,
        # of a tile turned four ways (T17.12) the first turn is the one that is named, and of
        # a sheet that comes once a season (T17.01) the first season is; tilled and watered
        # soil are the field's, and the ground of a map only when there is no other
        ranked = sorted(
            found,
            key=lambda a: (
                # a ground a map can be laid with before a single picture with the role
                # (T17.29: *Modern Farm*'s village was laid with one 16 px birch, so not at all)
                role == "GROUND"
                and catalog_mod.effective(a).get("usage") not in plausible_usage(role, projection),
                role == "GROUND" and _worked_soil(a),
                ground_rank(a),
                _is_variant(a),
                _later_turn(a),
                _later_season(a),
                a.status != "CONFIRMED",
                -a.confidence,
                a.id,
            ),
        )
        return ranked[0].id
    if role in OBJECT_ROLES:
        objs = [o for o in objects_with_role(catalog, role) if o.status != "UNUSED"]
        if objs:
            if role == "BUILDING":
                # T17.33: a house by its name before a part of a tile sheet (*Farm RPG*'s
                # village had a piece of its dungeon tile set as its house), an animal's house
                # last, the larger first
                objs = sorted(
                    objs,
                    key=lambda o: (
                        _house_rank(catalog, o),
                        _size_rank(o),
                        objs.index(o),
                    ),
                )
            return objs[0].id
    return None


NOT_FARM_GROUND_WORDS = frozenset(
    {"cave", "caves", "mine", "mines", "dungeon", "cliff", "cliffs", "shadow", "shadows",
     "water", "path", "paths", "road", "bridge", "beach", "temple", "house", "barn", "carpet"}
)  # fmt: skip
HOUSE_NAME_WORDS = frozenset(
    {"house", "houses", "home", "cottage", "farmhouse", "cabin", "hut", "inn", "shop"}
)
NOT_A_HOUSE_NAME = frozenset(
    {"dog", "bird", "birdhouse", "doghouse", "tree", "tileset", "npc", "npcs", "fishman",
     "blacksmith", "wizard", "school", "temple", "station", "trailer"}
)  # fmt: skip


def _size_rank(obj: Any) -> int:
    """A house of about the farm plan's house (6 x 5 cells of 16 px) first: a cottage, not a
    manor nor a shed (T17.33)."""
    w, h = int(obj.region[2]), int(obj.region[3])
    return abs(w - 96) + abs(h - 80)


def _house_words_rank(path: str) -> int:
    """0 for a picture named a house, 2 for a barn or a coop and the like, 1 else."""
    said = set(classifier.tokens(path)[0]) | set(classifier.tokens(path)[1])
    if said & {"barn", "barns", "coop", "coops", "stable", "silo", "greenhouse", "mill"}:
        return 2
    if said & HOUSE_NAME_WORDS and not said & NOT_A_HOUSE_NAME:
        return 0
    return 1


def _house_rank(catalog: catalog_mod.Catalog, obj: Any) -> int:
    tags = set(getattr(obj, "tags", None) or [])
    sheet = catalog.asset(obj.sheet)
    said = (
        set(classifier.tokens(sheet.path)[0]) | set(classifier.tokens(sheet.path)[1])
        if sheet
        else set()
    )
    said |= set(classifier.tokens(str(obj.name))[1])
    if tags & {"barn", "coop"}:
        return 3
    w, h = int(obj.region[2]), int(obj.region[3])
    if h > 1.6 * w or w > 3.5 * h:
        return 2  # a column of beds or a row of fences, no house (T17.33: *Tiny Farm*)
    if said & HOUSE_NAME_WORDS and not said & NOT_A_HOUSE_NAME:
        return 0
    if said & NOT_A_HOUSE_NAME:
        return 2
    return 1


def is_assigned(catalog: catalog_mod.Catalog, role: str, projection: str = TOP_DOWN) -> bool:
    return best_for(catalog, role, projection) is not None


def valid_selection(
    catalog: catalog_mod.Catalog, role: str, ident: str | None, projection: str = TOP_DOWN
) -> bool:
    """True when ``ident`` still exists and (for assets) still has ``role``."""
    if not ident:
        return False
    asset = catalog.asset(ident)
    if asset is not None:
        return _usable(asset, projection) and catalog_mod.effective(asset).get("role") == role
    return role in OBJECT_ROLES and any(o.id == ident and o.role == role for o in catalog.objects)


def default_starter(
    catalog: catalog_mod.Catalog, archetype: str, projection: str = TOP_DOWN
) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows(archetype):
        if row.key and (ident := best_for(catalog, row.role, projection)):
            out[row.key] = ident
    return out


def resolve_starter(
    catalog: catalog_mod.Catalog,
    archetype: str,
    current: dict[str, str],
    projection: str = TOP_DOWN,
) -> dict[str, str]:
    """``current`` with stale entries dropped and gaps filled with the default choice."""
    out: dict[str, str] = {}
    for row in rows(archetype):
        if not row.key:
            continue
        ident = current.get(row.key)
        if valid_selection(catalog, row.role, ident, projection):
            out[row.key] = ident  # type: ignore[assignment]
        elif (best := best_for(catalog, row.role, projection)) is not None:
            out[row.key] = best
    return out


def used_for(role: str, archetype: str | None = None) -> str:
    """ "Used for the player actor": what in the game needs this role (in ``archetype``)."""
    return requirements.required_by(role, archetype)


def missing_required(
    catalog: catalog_mod.Catalog,
    archetype: str,
    placeholders: set[str],
    projection: str = TOP_DOWN,
) -> list[str]:
    """Required roles with neither an asset nor a placeholder."""
    return [
        r.role
        for r in rows(archetype)
        if r.required
        and not is_assigned(catalog, r.role, projection)
        and r.role not in placeholders
    ]
