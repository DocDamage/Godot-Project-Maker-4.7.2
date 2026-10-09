"""Starter mapping: which asset fills which required or recommended role."""

from __future__ import annotations

from dataclasses import dataclass

from rpggen.core import catalog as catalog_mod
from rpggen.core import requirements

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
}
OBJECT_ROLES = requirements.OBJECT_ROLES  # roles that can also be filled with a SheetObject
_INACTIVE = {"UNUSED", "MISSING"}


@dataclass(frozen=True)
class RoleRow:
    role: str
    required: bool
    key: str | None  # starter key, None for WALL / UI


def rows(archetype: str) -> list[RoleRow]:
    required = requirements.REQUIRED.get(archetype, requirements.REQUIRED["turn_based"])
    ordered = [*required, *(r for r in requirements.recommended(archetype) if r not in required)]
    return [RoleRow(r, r in required, ROLE_KEYS.get(r)) for r in ordered]


def _usable(asset: catalog_mod.Asset) -> bool:
    return asset.status not in _INACTIVE and asset.kind == "image"


def assets_with_role(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.Asset]:
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if _usable(a) and catalog_mod.effective(a).get("role") == role
    ]


def objects_with_role(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.SheetObject]:
    return [o for o in sorted(catalog.objects, key=lambda o: o.id) if o.role == role]


def _is_variant(asset: catalog_mod.Asset) -> bool:
    return "derived_from" in asset.detected


def candidates(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.Asset]:
    """Assets the picker offers for ``role``: plausible usage, assets that already have the role
    first."""
    usages = PLAUSIBLE_USAGE.get(role, set())
    pool = [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if _usable(a) and catalog_mod.effective(a).get("usage") in usages
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


def best_for(catalog: catalog_mod.Catalog, role: str) -> str | None:
    """The asset (or object, for buildings) that fills a role by default."""
    found = assets_with_role(catalog, role)
    if found:
        # a recolour variant (T13.18) never takes a role from the pack's own asset by itself
        ranked = sorted(
            found, key=lambda a: (_is_variant(a), a.status != "CONFIRMED", -a.confidence, a.id)
        )
        return ranked[0].id
    if role in OBJECT_ROLES:
        objs = [o for o in objects_with_role(catalog, role) if o.status != "UNUSED"]
        if objs:
            return objs[0].id
    return None


def is_assigned(catalog: catalog_mod.Catalog, role: str) -> bool:
    return best_for(catalog, role) is not None


def valid_selection(catalog: catalog_mod.Catalog, role: str, ident: str | None) -> bool:
    """True when ``ident`` still exists and (for assets) still has ``role``."""
    if not ident:
        return False
    asset = catalog.asset(ident)
    if asset is not None:
        return _usable(asset) and catalog_mod.effective(asset).get("role") == role
    return role in OBJECT_ROLES and any(o.id == ident and o.role == role for o in catalog.objects)


def default_starter(catalog: catalog_mod.Catalog, archetype: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows(archetype):
        if row.key and (ident := best_for(catalog, row.role)):
            out[row.key] = ident
    return out


def resolve_starter(
    catalog: catalog_mod.Catalog, archetype: str, current: dict[str, str]
) -> dict[str, str]:
    """``current`` with stale entries dropped and gaps filled with the default choice."""
    out: dict[str, str] = {}
    for row in rows(archetype):
        if not row.key:
            continue
        ident = current.get(row.key)
        if valid_selection(catalog, row.role, ident):
            out[row.key] = ident  # type: ignore[assignment]
        elif (best := best_for(catalog, row.role)) is not None:
            out[row.key] = best
    return out


def used_for(role: str, archetype: str | None = None) -> str:
    """ "Used for the player actor": what in the game needs this role (in ``archetype``)."""
    return requirements.required_by(role, archetype)


def missing_required(
    catalog: catalog_mod.Catalog, archetype: str, placeholders: set[str]
) -> list[str]:
    """Required roles with neither an asset nor a placeholder."""
    return [
        r.role
        for r in rows(archetype)
        if r.required and not is_assigned(catalog, r.role) and r.role not in placeholders
    ]
