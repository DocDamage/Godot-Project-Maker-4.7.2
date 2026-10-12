from __future__ import annotations

import dataclasses

from rpggen.core import catalog as catalog_mod
from rpggen.core.config import GeneratorConfig
from rpggen.errors import IssueList, Severity

REQUIRED: dict[str, list[str]] = {
    "turn_based": ["PLAYER", "GROUND"],
    "arpg": ["PLAYER", "GROUND"],
    "metroidvania": ["PLAYER", "GROUND"],
    # the arcade kinds (T16.03)
    "shmup": ["PLAYER"],
    "run_and_gun": ["PLAYER", "GROUND"],
    "racing": ["VEHICLE", "GROUND"],
    "farm": ["PLAYER", "GROUND"],  # T17.02
}
RECOMMENDED = ["NPC", "ENEMY", "BUILDING", "WALL", "ITEM", "UI", "PORTRAIT"]
# The roles an archetype uses beside the required ones (T14.02). The two top-down archetypes
# share RECOMMENDED; a metroidvania has no houses or map border and adds backgrounds and a boss.
OPTIONAL: dict[str, list[str]] = {
    "turn_based": RECOMMENDED,
    "arpg": RECOMMENDED,
    "metroidvania": ["BACKGROUND", "DECORATION", "ENEMY", "BOSS", "ITEM", "NPC", "UI", "PORTRAIT"],
    "shmup": ["ENEMY", "BOSS", "PROJECTILE", "EXPLOSION", "POWERUP", "HAZARD", "BACKGROUND", "UI"],
    "run_and_gun": ["ENEMY", "BOSS", "PROJECTILE", "EXPLOSION", "POWERUP", "HAZARD", "BACKGROUND",
                    "DECORATION", "UI"],
    "racing": ["ENEMY", "HAZARD", "POWERUP", "DECORATION", "UI"],
    # a farm's village is the top-down starter map, so it has its walls and portraits too
    "farm": ["BUILDING", "NPC", "CROP", "ANIMAL", "TOOL", "ITEM", "DECORATION", "WALL", "UI",
             "PORTRAIT"],
}  # fmt: skip

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
# The same for a metroidvania, where a role is used for something else.
REQUIRED_BY_ARCHETYPE: dict[str, dict[str, str]] = {
    "metroidvania": {
        "PLAYER": "the player, seen from the side",
        "GROUND": "the floors and walls of every room",
        "BACKGROUND": "the parallax layers behind a room",
        "DECORATION": "scenery in the rooms",
        "ENEMY": "the creatures in the rooms",
        "BOSS": "the guardian",
        "ITEM": "pickups and chests",
        "NPC": "the characters you talk to",
    },
    "shmup": {
        "PLAYER": "the ship you fly",
        "ENEMY": "the waves of enemy ships",
        "BOSS": "the boss at the end of a stage",
        "PROJECTILE": "what the ships shoot",
        "EXPLOSION": "the burst of a ship that is hit",
        "POWERUP": "the capsules that make the ship stronger",
        "HAZARD": "asteroids and other things to fly around",
        "BACKGROUND": "the layers that scroll under the ship",
        "UI": "the score, the lives and the menus",
    },
    "run_and_gun": {
        "PLAYER": "the soldier, seen from the side",
        "GROUND": "the floors and platforms of every stage",
        "ENEMY": "the soldiers and turrets of a stage",
        "BOSS": "the boss at the end of a stage",
        "PROJECTILE": "the bullets",
        "EXPLOSION": "the burst of what is destroyed",
        "POWERUP": "the weapons to pick up",
        "HAZARD": "spikes, mines and pits",
        "BACKGROUND": "the parallax layers behind a stage",
        "DECORATION": "scenery of the stages",
        "UI": "the score, the lives and the menus",
    },
    "racing": {
        "VEHICLE": "the car you drive",
        "GROUND": "the road and what lies beside it",
        "ENEMY": "the rival cars",
        "HAZARD": "tyres, cones and oil on the track",
        "POWERUP": "boosts and pickups on the track",
        "DECORATION": "trackside scenery",
        "UI": "the lap counter, the position and the menus",
    },
    "farm": {
        "PLAYER": "the farmer",
        "GROUND": "the farmyard, the field and the village",
        "BUILDING": "the house, the coop and the barn",
        "NPC": "the people of the village",
        "CROP": "what grows in the field",
        "ANIMAL": "the animals of the coop and the barn",
        "TOOL": "the hoe, the watering can, the sickle and the axe",
        "ITEM": "seeds, produce and what the shop sells",
        "DECORATION": "trees, fences and what is cleared from the field",
        "UI": "the clock, the hotbar and the menus",
    },
}
ARCADE_KINDS = ("shmup", "run_and_gun", "racing")
FARM_KIND = "farm"
FARM_KIT_PACK = "rpggen_farm_kit"  # farm_kit.KIT_PACK: the farm's drawn stand-ins


def recommended(archetype: str) -> list[str]:
    """The roles ``archetype`` uses when the pack has them, in the Mapping page's order."""
    return OPTIONAL.get(archetype, RECOMMENDED)


def required_by(role: str, archetype: str | None = None) -> str:
    """What in the game needs ``role`` ("the starter map"); the role's name when nothing does."""
    own = REQUIRED_BY_ARCHETYPE.get(archetype or "", {})
    return own.get(role) or REQUIRED_BY.get(role, role.lower())


OBJECT_ROLES = {"BUILDING"}  # roles a sheet object (a house cut from a tile sheet) can fill
_INACTIVE = {"UNUSED", "MISSING"}


def _assets_with_role(catalog: catalog_mod.Catalog, role: str) -> list[catalog_mod.Asset]:
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.status not in _INACTIVE
        and catalog_mod.effective(a).get("role") == role
        # an isometric tile fills no role until a project can be isometric (T17.13)
        and not catalog_mod.is_iso_tile(a)
    ]


def _filled(catalog: catalog_mod.Catalog, role: str) -> bool:
    # a drawn stand-in of the farm that a last run left in the catalog fills nothing: the check
    # says the same on every run, by what the packs have (``farm_kit.lacking``)
    if any(a.pack_id != FARM_KIT_PACK for a in _assets_with_role(catalog, role)):
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


def mixed_ground(catalog: catalog_mod.Catalog) -> str | None:
    """The first isometric ground tile of a catalog that also has square ground (a tile sheet
    with the role), or None: a map is painted with one of the two (``TILE-011``)."""
    square = False
    isometric: str | None = None
    for asset in sorted(catalog.assets, key=lambda a: a.id):
        facets = catalog_mod.effective(asset)
        if asset.status in _INACTIVE or facets.get("role") != "GROUND":
            continue
        if catalog_mod.is_iso_tile(asset):
            isometric = isometric or asset.id
        elif facets.get("usage") == "tiles" and asset.pack_id not in catalog_mod.RUN_MADE_PACKS:
            square = True  # a pack's own: a placeholder or a drawn stand-in is nobody's choice
    return isometric if square else None


AIR_ACTIONS = ("jump", "fall")


def missing_air_animations(player: catalog_mod.Asset | None) -> list[str]:
    """The actions among jump and fall a side-view player has no animation for (T14.03). The
    game then shows the idle frame in the air (ASSET-030, informational)."""
    if player is None:
        return []
    animations = catalog_mod.effective(player).get("animations") or {}
    have = {str(name).split("_", 1)[0] for name in animations}
    return [action for action in AIR_ACTIONS if action not in have]


def check(catalog: catalog_mod.Catalog, cfg: GeneratorConfig) -> IssueList:
    """ASSET-010 for missing required (error) and recommended (warning) roles; ASSET-014 when
    several PLAYER assets exist and none is CONFIRMED; ASSET-028 for a pack whose licence asks
    for credit but names no author (after the Audit page's corrections); ASSET-030 for a
    metroidvania whose player has no jump or fall animation; ASSET-031 for what an arcade kind
    or a farm gets drawn because the packs lack it; TILE-011 for packs with isometric ground
    beside square ground."""
    issues = IssueList()
    drawn: frozenset[str] = frozenset()
    stood_in: set[str] = set()  # the roles a drawn stand-in fills: noted, so not also missing
    if cfg.archetype == FARM_KIND:
        from rpggen.core import farm_kit

        # what a farm works with and a pack lacks is drawn (T17.02). The player and the ground
        # are not: a farm needs them from a pack. A bed or a bin is no scenery, and drawn soil
        # no ground, so those leave their roles as lacking as they were.
        for farm_stand_in in farm_kit.lacking(catalog):
            issues.add("ASSET-031", role=farm_stand_in.role, thing=farm_stand_in.thing, file="")
            if farm_stand_in.fills:
                stood_in.add(farm_stand_in.role)
    if cfg.archetype in ARCADE_KINDS:
        from rpggen.core import arcade_kit

        # what an arcade kind needs and a pack lacks is drawn (T16.03): a note, not an error
        drawn = arcade_kit.drawn_roles(cfg.archetype)
        for stand_in in arcade_kit.lacking(catalog, cfg.archetype):
            issues.add("ASSET-031", role=stand_in.role, thing=stand_in.thing, file="")
            stood_in.add(stand_in.role)
        vehicles = _assets_with_role(catalog, "VEHICLE") if cfg.archetype == "racing" else []
        chosen = (cfg.starter or {}).get("vehicle")
        mine = next((v for v in vehicles if v.id == chosen), vehicles[0] if vehicles else None)
        if mine is not None and not catalog_mod.effective(mine).get("headings"):
            issues.add("ASSET-032", asset=mine.id)
    mixed = mixed_ground(catalog)
    if mixed is not None:  # isometric and square ground in one project (T17.12)
        issues.add("TILE-011", asset=mixed, file="")
    for role in REQUIRED.get(cfg.archetype, REQUIRED["turn_based"]):
        if not _filled(catalog, role) and role not in drawn:
            issue = issues.add("ASSET-010", role=role, feature=required_by(role, cfg.archetype))
            issues[-1] = dataclasses.replace(issue, severity=Severity.ERROR)
    # what a kit draws for the kind is noted above (ASSET-031): it is not also missing
    for role in recommended(cfg.archetype):
        if not _filled(catalog, role) and role not in stood_in:
            issues.add("ASSET-010", role=role, feature=required_by(role, cfg.archetype))
    if not _assets_with_role(catalog, "AUDIO_MUSIC"):
        issues.add("ASSET-026")
    if not _assets_with_role(catalog, "AUDIO_SFX"):
        issues.add("ASSET-027")
    players = _assets_with_role(catalog, "PLAYER")
    if len(players) > 1 and not any(p.status == "CONFIRMED" for p in players):
        issues.add("ASSET-014", role="PLAYER", candidates=", ".join(p.id for p in players))
    if cfg.archetype in ("metroidvania", "run_and_gun"):  # the kinds whose player jumps
        chosen = (cfg.starter or {}).get("player")
        player = next((p for p in players if p.id == chosen), players[0] if players else None)
        missing = missing_air_animations(player)
        if player is not None and missing:
            issues.add("ASSET-030", asset=player.id, missing=" or ".join(missing))
    for pack in sorted(catalog.packs, key=lambda p: p.pack_id):
        found = pack.effective_license()
        if found.attribution_required and not found.author.strip():
            issues.add("ASSET-028", pack_id=pack.pack_id)
    return issues
