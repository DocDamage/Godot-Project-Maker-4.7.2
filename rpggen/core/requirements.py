from __future__ import annotations

import dataclasses

from rpggen.core import catalog as catalog_mod
from rpggen.core.config import GeneratorConfig
from rpggen.errors import IssueList, Severity

REQUIRED: dict[str, list[str]] = {"turn_based": ["PLAYER", "GROUND"], "arpg": ["PLAYER", "GROUND"]}
RECOMMENDED = ["NPC", "ENEMY", "BUILDING", "WALL", "ITEM", "UI", "PORTRAIT"]

# What needs each role (used in the ASSET-010 message).
REQUIRED_BY = {
    "PLAYER": "the player actor",
    "GROUND": "the starter map",
    "NPC": "town NPCs",
    "ENEMY": "encounters",
    "BUILDING": "building scenes",
    "WALL": "map borders",
    "ITEM": "items and chests",
    "UI": "menus",
    "PORTRAIT": "dialogue portraits",
}
OBJECT_ROLES = {"BUILDING"}  # roles a sheet object (a house cut from a tile sheet) can fill
_INACTIVE = {"UNUSED", "MISSING"}


def _assets_with_role(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.Asset]:
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.status not in _INACTIVE and catalog_mod.effective(a).get("role") == role
    ]


def _filled(catalog: catalog_mod.Catalog, role: str) -> bool:
    if _assets_with_role(catalog, role):
        return True
    return role in OBJECT_ROLES and any(
        o.role == role and o.status not in _INACTIVE for o in catalog.objects
    )


def role_counts(catalog: catalog_mod.Catalog) -> dict[str, int]:
    """How many active assets (and sheet objects) fill each role, by role name."""
    counts: dict[str, int] = {}
    for asset in catalog.assets:
        if asset.status in _INACTIVE:
            continue
        role = catalog_mod.effective(asset).get("role")
        if role:
            counts[str(role)] = counts.get(str(role), 0) + 1
    for obj in catalog.objects:
        if obj.status not in _INACTIVE and obj.role:
            counts[obj.role] = counts.get(obj.role, 0) + 1
    return dict(sorted(counts.items()))


def check(catalog: catalog_mod.Catalog, cfg: GeneratorConfig) -> IssueList:
    """ASSET-010 for missing required (error) and recommended (warning) roles; ASSET-014 when
    several PLAYER assets exist and none is CONFIRMED; ASSET-028 for a pack whose licence asks
    for credit but names no author (after the Audit page's corrections)."""
    issues = IssueList()
    for role in REQUIRED.get(cfg.archetype, REQUIRED["turn_based"]):
        if not _filled(catalog, role):
            issue = issues.add("ASSET-010", role=role, feature=REQUIRED_BY.get(role, role.lower()))
            issues[-1] = dataclasses.replace(issue, severity=Severity.ERROR)
    for role in RECOMMENDED:
        if not _filled(catalog, role):
            issues.add("ASSET-010", role=role, feature=REQUIRED_BY.get(role, role.lower()))
    if not _assets_with_role(catalog, "AUDIO_MUSIC"):
        issues.add("ASSET-026")
    if not _assets_with_role(catalog, "AUDIO_SFX"):
        issues.add("ASSET-027")
    players = _assets_with_role(catalog, "PLAYER")
    if len(players) > 1 and not any(p.status == "CONFIRMED" for p in players):
        issues.add("ASSET-014", role="PLAYER", candidates=", ".join(p.id for p in players))
    for pack in sorted(catalog.packs, key=lambda p: p.pack_id):
        found = pack.effective_license()
        if found.attribution_required and not found.author.strip():
            issues.add("ASSET-028", pack_id=pack.pack_id)
    return issues
