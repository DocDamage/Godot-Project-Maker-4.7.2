"""Sound slots: which audio asset plays where in the generated game (T11.20).

A fixed list of slots, each filled by one audio asset or left empty. ``default_sounds`` picks an
asset per slot from file-name tokens, ``resolve_sounds`` keeps the user's choices, drops stale
ones and fills the gaps (the same shape as ``mapping.default_starter`` / ``resolve_starter``).
Audio is never required and there are no audio placeholders: an empty slot is silent.

Beyond the fixed list a project can have **custom slots** (T13.16): any key that matches
``SLOT_PATTERN``. ``sfx_step_<surface>`` is the footstep on ground whose asset has the tag
``surface:<name>``; any other custom slot is played by name (``play_sound:<slot>`` in a dialogue,
``RpgAudio.play`` in a script).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from rpggen.core import catalog as catalog_mod
from rpggen.core import classifier

MUSIC = "music"
SFX = "sfx"
SLOT_PATTERN = re.compile(r"^(music|sfx)_[a-z][a-z0-9_]{1,30}$")
# The surfaces rpggen fills a footstep slot for by itself. A ground asset's tag may name any
# surface (snow is detected too); its slot is then a custom one like every other.
SURFACES = ["grass", "stone", "wood", "water", "sand"]
SURFACE_TAG = "surface:"
STEP_PREFIX = "sfx_step_"
_STEP_TOKENS = {"step", "steps", "footstep", "footsteps", "walk"}
_INACTIVE = {"UNUSED", "MISSING"}
ROLE_OF_KIND = {MUSIC: "AUDIO_MUSIC", SFX: "AUDIO_SFX"}


@dataclass(frozen=True)
class Slot:
    key: str
    kind: str  # "music" or "sfx"
    label: str
    help: str
    tokens: tuple[str, ...]  # file-name tokens, first hit wins (in this order)


SLOTS: tuple[Slot, ...] = (
    Slot("music_map", MUSIC, "Map music", "Plays on the maps.",
         ("town", "village", "overworld", "field", "map", "theme")),
    Slot("music_battle", MUSIC, "Battle music", "Plays during battles.",
         ("battle", "fight", "combat", "boss")),
    Slot("music_title", MUSIC, "Title music", "Plays on the title screen.",
         ("title", "menu", "intro")),
    Slot("sfx_ui_move", SFX, "Menu cursor", "Moving through a menu.",
         ("cursor", "move", "select", "tick", "hover")),
    Slot("sfx_ui_confirm", SFX, "Menu confirm", "Choosing a menu entry.",
         ("confirm", "accept", "ok", "click")),
    Slot("sfx_ui_cancel", SFX, "Menu cancel", "Going back in a menu.",
         ("cancel", "back", "close")),
    Slot("sfx_hit", SFX, "Hit", "Something is hurt.",
         ("hit", "hurt", "damage", "impact", "slash")),
    Slot("sfx_attack", SFX, "Attack", "An attack starts.",
         ("attack", "swing", "sword", "whoosh")),
    Slot("sfx_pickup", SFX, "Pick up", "An item or coin is picked up.",
         ("pickup", "coin", "item", "collect")),
    Slot("sfx_chest", SFX, "Chest", "A chest opens.",
         ("chest", "open", "unlock")),
    Slot("sfx_door", SFX, "Door", "A door or stairs are used.",
         ("door", "enter", "stairs")),
    Slot("sfx_step", SFX, "Footstep", "The player walks.",
         ("step", "footstep", "walk")),
    Slot("sfx_save", SFX, "Save", "The game is saved.",
         ("save",)),
    Slot("sfx_levelup", SFX, "Level up", "The player levels up.",
         ("levelup", "level", "fanfare", "victory")),
)  # fmt: skip
SLOT_KEYS = tuple(s.key for s in SLOTS)
# The fixed slots only one archetype plays (T14.10). They come after the shared ones; for every
# other archetype such a name is a custom slot like any other, so their projects are unchanged.
ARCHETYPE_SLOTS: dict[str, tuple[Slot, ...]] = {
    "metroidvania": (
        Slot("sfx_jump", SFX, "Jump", "The player jumps.",
             ("jump", "hop", "leap")),
        Slot("sfx_land", SFX, "Land", "The player lands after a fall.",
             ("land", "landing", "thud")),
        Slot("sfx_dash", SFX, "Dash", "The player dashes.",
             ("dash", "dodge", "roll")),
        Slot("sfx_ability", SFX, "Ability", "An ability is found.",
             ("powerup", "ability", "upgrade", "power")),
    ),
    # the arcade kinds (T16.03)
    "shmup": (
        Slot("sfx_shoot", SFX, "Shoot", "The ship fires.", ("shoot", "shot", "laser", "fire")),
        Slot("sfx_explosion", SFX, "Explosion", "A ship is destroyed.",
             ("explosion", "explode", "boom", "blast")),
        Slot("sfx_powerup", SFX, "Power-up", "A capsule is picked up.",
             ("powerup", "upgrade", "capsule", "power")),
        Slot("sfx_bomb", SFX, "Bomb", "The bomb clears the screen.", ("bomb", "nuke")),
        Slot("music_stage", MUSIC, "Stage music", "Plays during a stage.",
             ("stage", "level", "theme")),
        Slot("music_boss", MUSIC, "Boss music", "Plays during a boss fight.", ("boss",)),
    ),
    "run_and_gun": (
        Slot("sfx_shoot", SFX, "Shoot", "The soldier fires.", ("shoot", "shot", "gun", "fire")),
        Slot("sfx_explosion", SFX, "Explosion", "Something is destroyed.",
             ("explosion", "explode", "boom", "blast")),
        Slot("sfx_grenade", SFX, "Grenade", "A grenade is thrown.", ("grenade", "throw")),
        Slot("sfx_weapon_pickup", SFX, "Weapon pickup", "A weapon is picked up.",
             ("weapon", "powerup", "reload", "pickup")),
        Slot("sfx_grapple", SFX, "Grapple", "The grapple arm fires.",
             ("grapple", "hook", "chain")),
        Slot("music_stage", MUSIC, "Stage music", "Plays during a stage.",
             ("stage", "level", "theme")),
        Slot("music_boss", MUSIC, "Boss music", "Plays during a boss fight.", ("boss",)),
    ),
    "racing": (
        Slot("sfx_engine", SFX, "Engine", "Loops while driving; its pitch follows the speed.",
             ("engine", "motor")),
        Slot("sfx_skid", SFX, "Skid", "The car slides.", ("skid", "drift", "screech")),
        Slot("sfx_bump", SFX, "Bump", "The car hits something.", ("bump", "crash", "hit")),
        Slot("sfx_pickup", SFX, "Pick up", "A pickup is driven over.",
             ("pickup", "coin", "item", "collect")),
        Slot("sfx_lap", SFX, "Lap", "A lap is finished.", ("lap", "checkpoint")),
        Slot("sfx_countdown", SFX, "Countdown", "The lights before the start.",
             ("countdown", "beep", "start")),
        Slot("music_race", MUSIC, "Race music", "Plays during a race.",
             ("race", "track", "theme")),
        Slot("music_results", MUSIC, "Results music", "Plays on the results screen.",
             ("results", "victory", "win")),
    ),
    # the farm (T17.02)
    "farm": (
        Slot("sfx_hoe", SFX, "Hoe", "The hoe tills the ground.", ("hoe", "till", "dig")),
        Slot("sfx_water", SFX, "Watering", "The watering can waters the soil.",
             ("watering", "water", "splash", "pour")),
        Slot("sfx_plant", SFX, "Plant", "A seed is planted.", ("plant", "seed", "sow")),
        Slot("sfx_harvest", SFX, "Harvest", "A ripe crop is harvested.",
             ("harvest", "pluck", "sickle", "cut")),
        Slot("sfx_sell", SFX, "Sell", "What is in the shipping bin is sold.",
             ("sell", "sold", "cash", "money")),
        Slot("sfx_animal", SFX, "Animal", "An animal is petted or fed.",
             ("animal", "cluck", "hen", "chicken", "moo", "cow")),
        Slot("sfx_rooster", SFX, "Rooster", "A new day begins.", ("rooster", "crow", "morning")),
        Slot("music_spring", MUSIC, "Spring music",
             "Plays in spring. A season without music of its own plays the first that has.",
             ("spring",)),
        Slot("music_summer", MUSIC, "Summer music", "Plays in summer.", ("summer",)),
        Slot("music_autumn", MUSIC, "Autumn music", "Plays in autumn.", ("autumn", "fall")),
        Slot("music_winter", MUSIC, "Winter music", "Plays in winter.", ("winter", "snow")),
        Slot("music_night", MUSIC, "Night music", "Plays after dark.", ("night", "evening")),
    ),
}  # fmt: skip
_BY_KEY = {s.key: s for s in SLOTS}
_ARCHETYPE_BY_KEY = {s.key: s for group in ARCHETYPE_SLOTS.values() for s in group}


def slots_for(archetype: str = "turn_based") -> tuple[Slot, ...]:
    """The fixed slots of an archetype: the shared ones, then its own."""
    return SLOTS + ARCHETYPE_SLOTS.get(archetype, ())


def slot_keys(archetype: str = "turn_based") -> tuple[str, ...]:
    return tuple(s.key for s in slots_for(archetype))


def is_valid_name(key: object) -> bool:
    """A slot key the config accepts: a fixed slot or a custom one."""
    return isinstance(key, str) and SLOT_PATTERN.fullmatch(key) is not None


def invalid_names(sounds: object) -> list[str]:
    """The keys of a ``sounds`` table that are not slot names, sorted."""
    if not isinstance(sounds, dict):
        return []
    return sorted(str(k) for k in sounds if not is_valid_name(k))


def is_custom(key: str, archetype: str = "turn_based") -> bool:
    return key not in _BY_KEY and key not in {s.key for s in ARCHETYPE_SLOTS.get(archetype, ())}


def kind_of(key: str) -> str:
    return MUSIC if key.startswith("music_") else SFX


def custom_slots(sounds: Iterable[str], archetype: str = "turn_based") -> list[str]:
    """The custom slots among ``sounds`` (its keys), sorted."""
    return sorted(k for k in sounds if is_custom(k, archetype) and is_valid_name(k))


def slot(key: str) -> Slot:
    """The slot of a key; a custom key gets a slot made from its name."""
    if key in _BY_KEY:
        return _BY_KEY[key]
    if key in _ARCHETYPE_BY_KEY:
        return _ARCHETYPE_BY_KEY[key]
    if key.startswith(STEP_PREFIX):
        surface = key[len(STEP_PREFIX) :]
        return Slot(
            key,
            SFX,
            f"Footstep ({surface.replace('_', ' ')})",
            f"The player walks on ground tagged surface:{surface}.",
            (),
        )
    return Slot(key, kind_of(key), key, "A custom slot: played by its name.", ())


def surface_of(asset: catalog_mod.Asset) -> str | None:
    """The surface a ground asset is tagged with (``surface:<name>``), or None."""
    for tag in catalog_mod.effective(asset).get("tags") or []:
        if isinstance(tag, str) and tag.startswith(SURFACE_TAG) and tag != SURFACE_TAG:
            return tag[len(SURFACE_TAG) :]
    return None


def audio_assets(catalog: catalog_mod.Catalog, kind: str) -> list[catalog_mod.Asset]:
    """Active audio assets of one kind, sorted by id."""
    role = ROLE_OF_KIND[kind]
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.kind == "audio"
        and a.status not in _INACTIVE
        and catalog_mod.effective(a).get("role") == role
    ]


def duration_of(asset: catalog_mod.Asset) -> float | None:
    audio = catalog_mod.effective(asset).get("audio") or {}
    value = audio.get("duration_s") if isinstance(audio, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def _name_tokens(asset: catalog_mod.Asset) -> set[str]:
    stem = asset.path.rsplit("/", 1)[-1]
    return set(classifier.tokens(f"x/{stem}")[1])


def _by_tokens(slot_def: Slot, pool: list[catalog_mod.Asset]) -> str | None:
    named = [(a, _name_tokens(a)) for a in pool]
    for token in slot_def.tokens:
        for asset, tokens in named:
            if token in tokens:
                return asset.id
    return None


def _longest(pool: list[catalog_mod.Asset]) -> str | None:
    if not pool:
        return None
    ranked = sorted(pool, key=lambda a: (-(duration_of(a) or 0.0), a.id))
    return ranked[0].id


def default_sounds(catalog: catalog_mod.Catalog, archetype: str = "turn_based") -> dict[str, str]:
    """An asset per slot where the packs have a plausible one (file-name tokens; the map music
    falls back to the longest music track and the title music to the map music)."""
    music = audio_assets(catalog, MUSIC)
    sfx = audio_assets(catalog, SFX)
    out: dict[str, str] = {}
    for s in slots_for(archetype):
        found = _by_tokens(s, music if s.kind == MUSIC else sfx)
        if found is None and s.key == "music_map":
            found = _longest(music)
        if found is None and s.key == "music_title":
            found = out.get("music_map")
        if found is not None:
            out[s.key] = found
    named = [(a, _name_tokens(a)) for a in sfx]
    for surface in SURFACES:  # step_grass.wav, footstep-stone.ogg
        for asset, tokens in named:
            if surface in tokens and tokens & _STEP_TOKENS:
                out[STEP_PREFIX + surface] = asset.id
                break
    return out


def valid_choice(catalog: catalog_mod.Catalog, key: str, asset_id: str | None) -> bool:
    if not asset_id or not is_valid_name(key):
        return False
    asset = catalog.asset(asset_id)
    return asset is not None and any(a.id == asset_id for a in audio_assets(catalog, kind_of(key)))


CLEARED = ""  # a slot the user emptied on purpose: it stays silent instead of getting a default


def resolve_sounds(
    catalog: catalog_mod.Catalog, current: dict[str, str], archetype: str = "turn_based"
) -> dict[str, str]:
    """``current`` with stale entries dropped and gaps filled with the default choice. A slot
    that is ``CLEARED`` stays cleared. A custom slot stays as long as its name is valid: without
    a sound it is ``CLEARED``, so the row the user added does not vanish."""
    defaults = default_sounds(catalog, archetype)
    out: dict[str, str] = {}
    keys = list(slot_keys(archetype)) + sorted(
        k for k in set(defaults) | set(current) if is_custom(k, archetype) and is_valid_name(k)
    )
    for key in keys:
        chosen = current.get(key)
        if chosen == CLEARED and key in current:
            out[key] = CLEARED
        elif valid_choice(catalog, key, chosen):
            out[key] = chosen  # type: ignore[assignment]
        elif key in defaults:
            out[key] = defaults[key]
        elif key in current and is_custom(key, archetype):
            out[key] = CLEARED
    return out


def summary(sounds: dict[str, str]) -> str:
    """ "3 music tracks, 14 sound effects assigned" for the collapsed Mapping group."""
    music = sum(1 for k, v in sounds.items() if v and is_valid_name(k) and kind_of(k) == MUSIC)
    sfx = sum(1 for k, v in sounds.items() if v and is_valid_name(k) and kind_of(k) == SFX)
    tracks = f"{music} music track{'s' if music != 1 else ''}"
    effects = f"{sfx} sound effect{'s' if sfx != 1 else ''}"
    return f"{tracks}, {effects} assigned"
