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
_INACTIVE = {"UNUSED", "MISSING"}


def _assets_with_role(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.Asset]:
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.status not in _INACTIVE and catalog_mod.effective(a).get("role") == role
    ]


def check(catalog: catalog_mod.Catalog, cfg: GeneratorConfig) -> IssueList:
    """ASSET-010 for missing required (error) and recommended (warning) roles; ASSET-014 when
    several PLAYER assets exist and none is CONFIRMED."""
    issues = IssueList()
    for role in REQUIRED.get(cfg.archetype, REQUIRED["turn_based"]):
        if not _assets_with_role(catalog, role):
            issue = issues.add("ASSET-010", role=role, feature=REQUIRED_BY.get(role, role.lower()))
            issues[-1] = dataclasses.replace(issue, severity=Severity.ERROR)
    for role in RECOMMENDED:
        if not _assets_with_role(catalog, role):
            issues.add("ASSET-010", role=role, feature=REQUIRED_BY.get(role, role.lower()))
    players = _assets_with_role(catalog, "PLAYER")
    if len(players) > 1 and not any(p.status == "CONFIRMED" for p in players):
        issues.add("ASSET-014", role="PLAYER", candidates=", ".join(p.id for p in players))
    return issues
