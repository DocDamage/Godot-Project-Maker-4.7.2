"""Friendly names and one-line descriptions for roles and usages (T11.13).

The catalog, profiles and the command line keep the raw names (``GROUND``, ``tiles``); only what
the wizard and the generation report show goes through here.
"""

from __future__ import annotations

ROLE_INFO: dict[str, tuple[str, str]] = {
    "GROUND": ("Ground tiles", "Painted as the floor of the starter map. Walkable."),
    "WALL": ("Wall tiles", "Used for the map border. Blocks movement."),
    "CLIFF": ("Cliff tiles", "Raised terrain edges. Blocks movement."),
    "WATER": ("Water tiles", "Ponds and rivers. Blocks movement."),
    "ROAD": ("Road tiles", "Paths drawn from the start to the doors. Walkable."),
    "AUTOTILE": ("Autotile terrain", "A terrain that joins its edges and corners by itself."),
    "DECORATION": ("Decoration", "Placed as scenery. Available in the editor dock."),
    "BUILDING": ("Building", "A house the player can enter. Its door leads to an interior."),
    "INTERIOR": ("Interior tiles", "Floors and furniture of the rooms inside buildings."),
    "PLAYER": ("Player", "The character you control."),
    "NPC": ("Villager (NPC)", "A character you can talk to."),
    "ENEMY": ("Enemy", "A creature that fights the player."),
    "BOSS": ("Boss", "A larger enemy for special encounters."),
    "WEAPON": ("Weapon", "A weapon's picture, for items and attack effects."),
    "ITEM": ("Item or chest", "Items, icons and the chest of the starter map."),
    "EFFECT": ("Effect", "An animation for hits, magic and other effects."),
    "PROJECTILE": ("Projectile", "Arrows, bolts and other things that fly."),
    "UI": ("Interface", "Panels and buttons of the menus."),
    "PORTRAIT": ("Portrait", "A face shown next to dialogue."),
    "BACKGROUND": ("Background", "A picture behind battles or the title."),
    "AUDIO_MUSIC": ("Music", "A long track that loops."),
    "AUDIO_SFX": ("Sound effect", "A short sound."),
    "FONT": ("Font", "Text for menus and dialogue (used only with the pack's license)."),
    "NONE": ("Not used", "Left out of the game."),
}

USAGE_INFO: dict[str, tuple[str, str]] = {
    "tiles": ("Tile sheet", "Cut into a grid and added to a TileSet."),
    "sprite": ("Sprite or character", "Frames of a character, enemy or item."),
    "object": ("Object", "A single picture placed on the map, like a house or a tree."),
    "ui": ("Interface art", "Panels and buttons."),
    "portrait": ("Portrait", "A face for dialogue."),
    "background": ("Background", "A full-screen picture."),
    "audio": ("Sound", "Music or a sound effect."),
    "font": ("Font", "A typeface."),
}

# The groups of the Mapping page, in order.
ROLE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("World", ("GROUND", "WALL", "BUILDING")),
    ("Characters", ("PLAYER", "NPC", "ENEMY", "PORTRAIT")),
    ("Things", ("ITEM",)),
    ("Interface", ("UI",)),
)
# The Mapping page's groups: the same, with the roles only a metroidvania has rows for (T14.10).
MAPPING_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("World", ("GROUND", "WALL", "BUILDING", "BACKGROUND", "DECORATION")),
    ("Characters", ("PLAYER", "NPC", "ENEMY", "BOSS", "PORTRAIT")),
    ("Things", ("ITEM",)),
    ("Interface", ("UI",)),
)


def role_label(role: str) -> str:
    """The friendly name of a role; an unknown role is returned as it is."""
    return ROLE_INFO.get(role, (role, ""))[0]


def role_help(role: str) -> str:
    return ROLE_INFO.get(role, ("", ""))[1]


def usage_label(usage: str) -> str:
    return USAGE_INFO.get(usage, (usage, ""))[0]


def usage_help(usage: str) -> str:
    return USAGE_INFO.get(usage, ("", ""))[1]


def group_of(role: str) -> str:
    for name, roles in ROLE_GROUPS:
        if role in roles:
            return name
    return "Other"
