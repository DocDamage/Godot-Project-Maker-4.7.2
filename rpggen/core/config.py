from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, godot_target, jsonio, schema
from rpggen.errors import RpgGenError

CONFIG_VERSION = 1
GODOT_VERSION = godot_target.VERSION
DEFAULT_MAP_LAYERS = ["Ground", "GroundDetails", "Walls", "Props", "Overhead"]
GIT_DEFAULTS = {"pack_art": "commit"}
PACK_ART_CHOICES = ("commit", "lfs", "ignore")
# export targets in their fixed order (the presets in export_check.TARGETS follow it)
EXPORT_TARGETS = ("windows", "web", "linux", "macos")
EXPORT_TARGET_DEFAULT = ("windows",)
FEATURE_KEYS = (
    "tilesets",
    "collision",
    "terrain",
    "animations",
    "demo",
    "editor_tools",
    "save",
    "dialogue",
    "combat",
    "navigation",
    "debug_tools",
    "progression",
    "crafting",  # 1.5.0 (T18.14): recipes, stations and the crafting window
)


@dataclass(frozen=True, slots=True)
class PackRef:
    pack_id: str
    source: str  # absolute path as the user gave it; informational only
    source_sha256: str
    kind: str  # "zip" | "7z" | "folder"
    # T16.22: ``source`` is a bundle of packs and this pack is one folder of it, by its name.
    # A config may list several; loading makes one entry of each (``split_bundles``).
    folders: tuple[str, ...] = ()

    @property
    def folder(self) -> str:
        """The pack folder of the bundle this pack is ("" for a pack that is all of its
        source)."""
        return self.folders[0] if self.folders else ""

    @property
    def path(self) -> Path:
        """The path the wizard knows the pack by: the source, or ``<bundle>/<folder>``."""
        return Path(self.source) / self.folder if self.folders else Path(self.source)

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "pack_id": self.pack_id,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "kind": self.kind,
        }
        if self.folders:
            data["folders"] = list(self.folders)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PackRef:
        return cls(
            data["pack_id"],
            data["source"],
            data["source_sha256"],
            data["kind"],
            tuple(data.get("folders", ())),
        )


def split_bundles(packs: list[PackRef]) -> list[PackRef]:
    """One entry per pack (T16.22): an entry that lists several folders of a bundle becomes
    an entry for each, in the order given, with an id made from the folder's name. An entry
    with one folder keeps its id, so a config that was saved once reads the same ever after."""
    from rpggen import ids

    used = {p.pack_id for p in packs if len(p.folders) < 2}
    out: list[PackRef] = []
    for ref in packs:
        if len(ref.folders) < 2:
            out.append(ref)
            continue
        for folder in ref.folders:
            pack_id = ids.pack_id_from_name(folder, used)
            used.add(pack_id)
            out.append(PackRef(pack_id, ref.source, ref.source_sha256, ref.kind, (folder,)))
    return out


# the input of an assets-only project seen from the side is the metroidvania's (T17.33): its
# scenes are the side-view body, which jumps
ASSETS_VIEW_SIDE_INPUT = "assets:side"


def default_input(archetype: str, view: str = "") -> dict[str, dict[str, Any]]:
    """Default input bindings (02_SCHEMAS §1.1) for the archetype (and the view of an
    assets-only project)."""
    if archetype == "assets" and view == "side":
        archetype = ASSETS_VIEW_SIDE_INPUT
    bindings: dict[str, dict[str, Any]] = {
        "move_up": {"keys": ["W", "Up"], "joy_buttons": [11], "joy_axes": [[1, -1.0]]},
        "move_down": {"keys": ["S", "Down"], "joy_buttons": [12], "joy_axes": [[1, 1.0]]},
        "move_left": {"keys": ["A", "Left"], "joy_buttons": [13], "joy_axes": [[0, -1.0]]},
        "move_right": {"keys": ["D", "Right"], "joy_buttons": [14], "joy_axes": [[0, 1.0]]},
        "interact": {"keys": ["E", "Space"], "joy_buttons": [0]},
        "confirm": {"keys": ["Enter", "Space"], "joy_buttons": [0]},
        "cancel": {"keys": ["Escape", "Backspace"], "joy_buttons": [1]},
        "menu": {"keys": ["Escape", "Tab"], "joy_buttons": [6]},
    }
    if archetype == "arpg":
        bindings["attack"] = {"keys": ["J"], "mouse_buttons": [1], "joy_buttons": [2]}
        bindings["secondary_attack"] = {"keys": ["K"], "mouse_buttons": [2], "joy_buttons": [3]}
        bindings["dodge"] = {"keys": ["Shift"], "joy_buttons": [1]}
        bindings["quick_item"] = {"keys": ["Q"], "joy_buttons": [9]}
    if archetype == "metroidvania" or archetype == ASSETS_VIEW_SIDE_INPUT:
        # Space jumps, so it no longer interacts; `down` with jump drops through a platform
        bindings["interact"] = {"keys": ["E", "Up"], "joy_buttons": [3]}
        bindings["jump"] = {"keys": ["Space", "Z"], "joy_buttons": [0]}
        bindings["dash"] = {"keys": ["Shift", "C"], "joy_buttons": [10]}
        bindings["attack"] = {"keys": ["J", "X"], "mouse_buttons": [1], "joy_buttons": [2]}
        bindings["down"] = {"keys": ["S", "Down"], "joy_buttons": [12], "joy_axes": [[1, 1.0]]}
    if archetype == "run_and_gun":
        # the metroidvania's bindings are the starting point: Space jumps, J fires, K throws
        bindings["interact"] = {"keys": ["E"], "joy_buttons": [9]}
        bindings["jump"] = {"keys": ["Space", "Z"], "joy_buttons": [0]}
        bindings["shoot"] = {"keys": ["J", "X"], "mouse_buttons": [1], "joy_buttons": [2]}
        bindings["grenade"] = {"keys": ["K", "C"], "joy_buttons": [3]}
        bindings["aim_lock"] = {"keys": ["Shift"], "joy_axes": [[4, 1.0]]}
        # the grapple arm (T16.11): fires along the aim, and lets go again
        bindings["grapple"] = {"keys": ["L", "V"], "joy_buttons": [1]}
        bindings["down"] = {"keys": ["S", "Down"], "joy_buttons": [12], "joy_axes": [[1, 1.0]]}
    if archetype == "racing":
        # the pedal and the brake (which reverses); left and right steer (T16.12)
        bindings["accelerate"] = {"keys": ["Up", "W"], "joy_buttons": [0], "joy_axes": [[5, 1.0]]}
        bindings["brake"] = {"keys": ["Down", "S"], "joy_buttons": [1], "joy_axes": [[4, 1.0]]}
        bindings["boost"] = {"keys": ["Shift", "Space"], "joy_buttons": [2]}
        # the weapon the car has picked up (T16.14): a missile ahead, a bomb behind
        bindings["fire"] = {"keys": ["X", "K"], "joy_buttons": [3]}
    if archetype == "shmup":
        # Z fires and X bombs, as the genre has it; Shift flies slowly (the left trigger)
        bindings["shoot"] = {"keys": ["Z", "J"], "mouse_buttons": [1], "joy_buttons": [0]}
        bindings["bomb"] = {"keys": ["X", "K"], "joy_buttons": [1]}
        bindings["focus"] = {"keys": ["Shift"], "joy_axes": [[4, 1.0]]}
    if archetype == "farm":
        # Space uses what is held on the tile ahead (T17.04), so it no longer interacts
        bindings["interact"] = {"keys": ["E"], "joy_buttons": [2]}
        bindings["use"] = {"keys": ["Space", "J"], "mouse_buttons": [1], "joy_buttons": [0]}
        bindings["next_item"] = {"keys": ["R"], "joy_buttons": [10]}
        bindings["prev_item"] = {"keys": ["Q"], "joy_buttons": [9]}
        for slot in range(1, FARM_HOTBAR_SLOTS + 1):  # the number keys; 0 is the tenth slot
            bindings[f"hotbar_{slot}"] = {"keys": [str(slot % 10)]}
    return bindings


FARM_HOTBAR_SLOTS = 10  # RpgHotbar.SLOTS
FARM_STARTING_MONEY = 100  # FarmBuild.START_MONEY: five bags of the cheapest seeds, or a sickle
# The calendar of a farm (T17.16): the days of a season (RpgCalendar.SEASON_LENGTHS) and how
# long a day is, as the real seconds of a game minute (RpgCalendar.minute_s; a day has 1200
# of them, so 10, 14 or 20 minutes).
FARM_SEASON_DAYS = (7, 14, 28)
FARM_DAYS_PER_SEASON = 28  # RpgCalendar.DAYS_PER_SEASON
FARM_DAY_LENGTHS = {"short": 0.5, "normal": 0.7, "long": 1.0}
FARM_DAY_LENGTH = "normal"  # RpgCalendar.MINUTE_S
STARTER_MAP_SIZE_RANGE = (24, 96)
STARTER_MAP_COUNTS = {  # key -> (minimum, maximum)
    "buildings": (0, 4),
    "npcs": (0, 6),
    "enemies": (0, 8),
    "chests": (0, 4),
    "decorations": (0, 40),
    "ground_patches": (0, 20),
}


def starter_map_defaults(archetype: str = "turn_based") -> dict[str, Any]:
    """The starter map of every project before M11 (so the defaults reproduce it exactly). A
    metroidvania has a *starter world* of rooms instead (T14.06), with options of its own."""
    if archetype == "metroidvania":
        from rpggen.core import room_plan

        return room_plan.defaults()
    if archetype == "shmup":
        # a run of stages (T16.06): how it scrolls, how many, how long, how hard
        from rpggen.core import wave_plan

        return wave_plan.defaults()
    if archetype == "run_and_gun":
        # a run of stages seen from the side (T16.10); one hit is a death, the left edge kills
        from rpggen.core import stage_plan

        return stage_plan.defaults()
    if archetype == "racing":
        # the tracks (T16.13), how the car is steered and what the camera does (T16.12)
        from rpggen.core import track_plan

        return track_plan.defaults()
    if archetype in ARCADE_KINDS or archetype == ASSETS_KIND:
        return {}  # an assets-only project has no maps (T17.33)
    options: dict[str, Any] = {
        "size": [40, 24],
        "buildings": 1,
        "npcs": 1,
        "enemies": 2 if archetype == "arpg" else 1,
        "chests": 1,
        "decorations": 8,
        "ground_patches": 6,
        "ground": "",
    }
    if archetype == "farm":
        # money (T17.08): what a new game starts with, and whether staying up to 2:00 costs any
        options["starting_money"] = FARM_STARTING_MONEY
        options["pass_out_loss"] = True
        # fishing (T17.10): false keeps the rod out of the shop of a farm that has a pond
        options["fishing"] = True
        # the calendar (T17.03, an option since T17.16): the days of a season and of what
        # length a day is
        options["days_per_season"] = FARM_DAYS_PER_SEASON
        options["day_length"] = FARM_DAY_LENGTH
        # festivals and birthdays (T17.25): false plans neither
        options["festivals"] = True
        # marriage (T17.26): how many people of the village can be courted; 0 turns it off
        from rpggen.core import people_plan

        options["courtable"] = people_plan.COURTABLE_DEFAULT
        # the farm's own map (T17.06) beside the village's: how large the field and the plot
        # are, which animal houses stand on it, how much there is to clear, and the added maps
        from rpggen.core import farm_plan

        options.update(farm_plan.defaults())
        # what a farm of 1.5 adds that an older config lacks (M18): off, unless a new farm
        # chose it (NEW_FARM_OPTIONS)
        options["exhaustion"] = False
        options["cooking"] = False
        options["children"] = False
    return options


# What a new farm chooses that a farm made before these keys did not (M18): its config writes
# them, so an older config, which lacks them, keeps the defaults above and what it had.
#   animals     T18.05: the animal houses whose animals the packs have
#   exhaustion  T18.11: working at zero energy ends the day
#   cooking     T18.16: a kitchen in the farmhouse, dishes and recipes to learn
#   children    T18.17: a married farmer can have children
NEW_FARM_OPTIONS: dict[str, Any] = {
    "animals": "auto",
    "exhaustion": True,
    "cooking": True,
    "children": True,
}


ARCADE_KINDS = ("shmup", "run_and_gun", "racing")
# The kinds that are seen from the side: their packs get the side-view kit and their tile sets
# the one-way platforms, ladders and hazards (T14.03, T16.08).
SIDE_VIEW_KINDS = ("metroidvania", "run_and_gun")
# What an arcade kind (M16) has switched off until somebody switches it on: a run through
# stages has nobody to talk to and no enemy that looks for a path, and no skills to learn.
ARCADE_OFF = ("dialogue", "navigation", "progression", "crafting")


# A farm (M17) has nothing to fight until somebody switches combat on.
FARM_OFF = ("combat", "navigation")

# A project of the packs' assets only (T17.33): their TileSets, the scenes the editor's dock
# places and the catalog, with the runtime the scenes need, and no game (no maps, no menus, no
# loop, no smoke run). The owner builds the levels by hand. Seen from above (top-down or
# isometric, ``projection``) or from the side (``view``), as the packs are drawn.
ASSETS_KIND = "assets"
VIEW_TOP = "top"
VIEW_SIDE = "side"
VIEWS = (VIEW_TOP, VIEW_SIDE)
# what an assets-only project has: the editor's tools; nothing of a game
ASSETS_ON = ("tilesets", "collision", "terrain", "animations", "editor_tools")


def side_view(archetype: str, view: str = "") -> bool:
    """True for a project seen from the side: a side-view kind, or an assets-only project whose
    view is the side's (T17.33)."""
    return archetype in SIDE_VIEW_KINDS or (archetype == ASSETS_KIND and view == VIEW_SIDE)


# How the maps of a project are seen (T17.13): from above on squares, or at an angle on the
# diamonds of an isometric pack. A config without the key is top-down.
PROJECTION_TOP_DOWN = "top_down"
PROJECTION_ISOMETRIC = "isometric"
PROJECTIONS = (PROJECTION_TOP_DOWN, PROJECTION_ISOMETRIC)
# The kinds that have an isometric view: the top-down ones and the racing game.
ISOMETRIC_KINDS = ("turn_based", "arpg", "farm", "racing", "assets")
# ... and those of them whose isometric maps are not made yet (T17.14 made the turn-based game
# and the action RPG): asked for, they are refused before anything is built
ISOMETRIC_NOT_YET: tuple[str, ...] = ()  # the race was the last (T17.15)
# How the pad moves the player on an isometric map (T17.14): up is up on the screen, or the
# four directions follow the diamond's axes. ``iso_math.CONTROLS``.
ISO_CONTROLS_SCREEN = "screen"
ISO_CONTROLS_GRID = "grid"
ISO_CONTROLS = (ISO_CONTROLS_SCREEN, ISO_CONTROLS_GRID)
# The kinds whose player walks, and so reads the setting. A race is steered (relative to the car,
# or by the stick as a direction of the screen: ``starter_map.steering``): its config may carry
# the key, which is then neither read nor written back.
ISO_CONTROLS_KINDS = ("turn_based", "arpg", "farm")


def iso_controls_for(archetype: str, wanted: str) -> str:
    """``wanted`` for a kind that reads ``iso_controls``, the default for one that does not."""
    return wanted if archetype in ISO_CONTROLS_KINDS else ISO_CONTROLS_SCREEN


def default_features(archetype: str = "turn_based") -> dict[str, bool]:
    if archetype == ASSETS_KIND:
        return {key: key in ASSETS_ON for key in FEATURE_KEYS}
    off: tuple[str, ...] = ARCADE_OFF if archetype in ARCADE_KINDS else ("navigation",)
    if archetype == "metroidvania":  # crafting is for the kinds with a bag to craft into (T18.14)
        off = (*off, "crafting")
    if archetype == "farm":
        off = FARM_OFF
    return {key: key not in off for key in FEATURE_KEYS}


@dataclass(slots=True)
class GeneratorConfig:
    project_name: str
    packs: list[PackRef]
    archetype: str = "turn_based"
    base_tile_size: int = 16
    resolution: tuple[int, int] = (640, 360)
    window_size: tuple[int, int] = (1280, 720)
    map_layers: list[str] = field(default_factory=lambda: list(DEFAULT_MAP_LAYERS))
    features: dict[str, bool] = field(default_factory=default_features)
    validation: dict[str, Any] = field(default_factory=lambda: {"smoke_test": True})
    seed: int = 12345
    input: dict[str, dict[str, Any]] = field(default_factory=dict)
    starter: dict[str, str] = field(default_factory=dict)  # role key -> asset or object id
    sounds: dict[str, str] = field(default_factory=dict)  # sound slot -> audio asset id
    starter_map: dict[str, Any] = field(default_factory=dict)  # overrides of starter_map_defaults
    # Tiled and LDtk maps to build (T12.49): {"include": [map id, ...], "starter": map id}
    imported_maps: dict[str, Any] = field(default_factory=dict)
    git: dict[str, str] = field(default_factory=dict)  # {"pack_art": "commit" | "lfs" | "ignore"}
    # platforms that get an export preset and the export check (T12.52)
    export_targets: list[str] = field(default_factory=lambda: list(EXPORT_TARGET_DEFAULT))
    # after a build, mend the doors and unreachable maps of the maps rpggen made (T13.24)
    repair_world: bool = True
    # how the maps are seen (T17.13): "top_down" or "isometric"; fixed once a project is made
    projection: str = PROJECTION_TOP_DOWN
    # how the pad moves the player on an isometric map (T17.14): "screen" or "grid"
    iso_controls: str = ISO_CONTROLS_SCREEN
    # an assets-only project (T17.33): "top" or "side"; "" until the packs decide it (the
    # catalog phase writes what they are drawn as)
    view: str = ""
    config_version: int = CONFIG_VERSION
    generator_version: str = __version__
    godot_version: str = GODOT_VERSION

    def __post_init__(self) -> None:
        if not self.input:
            self.input = default_input(self.archetype)

    def to_json(self) -> dict[str, Any]:
        out = self._base_json()
        if self.starter:
            out["starter"] = dict(sorted(self.starter.items()))
        if self.sounds:
            out["sounds"] = dict(sorted(self.sounds.items()))
        options = self.starter_map_options()
        if options != starter_map_defaults(self.archetype):
            out["starter_map"] = options
        git = {k: v for k, v in sorted(self.git.items()) if v != GIT_DEFAULTS.get(k)}
        if git:
            out["git"] = git
        targets = self.selected_export_targets()
        if targets != list(EXPORT_TARGET_DEFAULT):
            out["export_targets"] = targets
        if not self.repair_world:
            out["repair_world"] = False
        if self.projection != PROJECTION_TOP_DOWN:  # a top-down config is what it was
            out["projection"] = self.projection
        if self.archetype == ASSETS_KIND and self.view:
            out["view"] = self.view
        controls = iso_controls_for(self.archetype, self.iso_controls)
        if controls != ISO_CONTROLS_SCREEN:  # the default is not written, nor what is not read
            out["iso_controls"] = controls
        imported = self.imported_map_selection()
        if imported["include"] or imported["starter"]:
            out["imported_maps"] = {
                k: v for k, v in imported.items() if v
            }  # a key that holds its default is left out
        return out

    def imported_map_selection(self) -> dict[str, Any]:
        """``{"include": [...], "starter": id}``: the maps to build and the one that becomes the
        starter map (it is built even when it is not listed in ``include``)."""
        starter = str(self.imported_maps.get("starter", ""))
        include = sorted({str(i) for i in self.imported_maps.get("include", [])} | {starter} - {""})
        return {"include": include, "starter": starter}

    def selected_export_targets(self) -> list[str]:
        """The export targets in the fixed order; Windows when none is chosen."""
        chosen = set(self.export_targets)
        return [t for t in EXPORT_TARGETS if t in chosen] or list(EXPORT_TARGET_DEFAULT)

    @property
    def pack_art(self) -> str:
        """How the purchased art is handled by git: ``commit`` (default), ``lfs`` or ``ignore``."""
        return self.git.get("pack_art", GIT_DEFAULTS["pack_art"])

    def starter_map_options(self) -> dict[str, Any]:
        """The starter map options with the archetype's defaults filled in (a deep copy)."""
        return copy.deepcopy({**starter_map_defaults(self.archetype), **self.starter_map})

    def _base_json(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "generator_version": self.generator_version,
            "godot_version": self.godot_version,
            "project_name": self.project_name,
            "archetype": self.archetype,
            "packs": [p.to_json() for p in self.packs],
            "base_tile_size": self.base_tile_size,
            "resolution": list(self.resolution),
            "window_size": list(self.window_size),
            "map_layers": list(self.map_layers),
            "features": dict(sorted(self.features.items())),
            "validation": dict(self.validation),
            "seed": self.seed,
            "input": copy.deepcopy(self.input),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> GeneratorConfig:
        return cls(
            project_name=data["project_name"],
            packs=split_bundles([PackRef.from_json(p) for p in data["packs"]]),
            archetype=data["archetype"],
            base_tile_size=data["base_tile_size"],
            resolution=(data["resolution"][0], data["resolution"][1]),
            window_size=(data["window_size"][0], data["window_size"][1]),
            map_layers=list(data["map_layers"]),
            features=dict(data["features"]),
            validation=dict(data["validation"]),
            seed=data["seed"],
            input=copy.deepcopy(data["input"]),
            starter=dict(data.get("starter", {})),
            sounds=dict(data.get("sounds", {})),
            starter_map=copy.deepcopy(data.get("starter_map", {})),
            imported_maps=copy.deepcopy(data.get("imported_maps", {})),
            git=dict(data.get("git", {})),
            export_targets=list(data.get("export_targets", EXPORT_TARGET_DEFAULT)),
            repair_world=bool(data.get("repair_world", True)),
            projection=str(data.get("projection", PROJECTION_TOP_DOWN)),
            iso_controls=iso_controls_for(
                data["archetype"], str(data.get("iso_controls", ISO_CONTROLS_SCREEN))
            ),
            view=str(data.get("view", "")),
            config_version=data["config_version"],
            generator_version=data["generator_version"],
            godot_version=data["godot_version"],
        )


def default_for(
    project_name: str,
    packs: list[PackRef],
    archetype: str = "turn_based",
    base_tile_size: int = 16,
) -> GeneratorConfig:
    """A config with every default filled in (and a new farm's choices, NEW_FARM_OPTIONS)."""
    return GeneratorConfig(
        project_name=project_name,
        packs=list(packs),
        archetype=archetype,
        base_tile_size=base_tile_size,
        features=default_features(archetype),
        resolution=resolution_for(base_tile_size),
        starter_map=dict(NEW_FARM_OPTIONS) if archetype == "farm" else {},
    )


DEFAULT_RESOLUTION = (640, 360)
# the largest tile the default resolution is made for: 640 x 360 shows 20 x 11 tiles of 32 px
RESOLUTION_TILE = 32


def resolution_for(base_tile_size: int) -> tuple[int, int]:
    """The default resolution for a tile size (T17.33): 640 x 360 up to 32 px tiles; for larger
    tiles as much larger as the tile, so the view shows as many tiles (a room of 128 px tiles
    in 2560 x 1440, the stretch mode scaling it to the window)."""
    tile = int(base_tile_size or 0)
    if tile <= RESOLUTION_TILE:
        return DEFAULT_RESOLUTION
    w = int(round(DEFAULT_RESOLUTION[0] * tile / RESOLUTION_TILE / 2.0)) * 2
    h = int(round(DEFAULT_RESOLUTION[1] * tile / RESOLUTION_TILE / 2.0)) * 2
    return (w, h)


def check_sound_names(data: Any) -> None:
    """CAT-006 for a ``sounds`` key that is no slot name (the schema would say CAT-002 with a
    pattern nobody can read)."""
    from rpggen.core import sound_slots

    sounds = data.get("sounds") if isinstance(data, dict) else None
    bad = sound_slots.invalid_names(sounds)
    if bad:
        raise RpgGenError("CAT-006", slot=bad[0])


def check_projection(data: Any) -> None:
    """CAT-002 for ``projection: isometric`` on a kind that has no isometric view (T17.13): a
    metroidvania and the two arcade kinds that scroll are seen from the side or from above."""
    if not isinstance(data, dict) or data.get("projection") != PROJECTION_ISOMETRIC:
        return
    archetype = data.get("archetype")
    if archetype not in ISOMETRIC_KINDS:
        raise RpgGenError(
            "CAT-002",
            file="config",
            reason=f"/projection: a {archetype} game has no isometric view (the kinds that have "
            f"one: {', '.join(ISOMETRIC_KINDS)})",
        )
    if archetype in ISOMETRIC_NOT_YET:
        made = ", ".join(k for k in ISOMETRIC_KINDS if k not in ISOMETRIC_NOT_YET)
        raise RpgGenError(
            "CAT-002",
            file="config",
            reason=f"/projection: the isometric view of a {archetype} game is not made yet (it "
            f"is made for: {made}); generate it with projection top_down",
        )


def check_projection_kept(cfg: GeneratorConfig, project: Path) -> None:
    """CAT-002 when ``project`` was generated in another projection than ``cfg`` asks for
    (T17.13): its maps are painted on squares or on diamonds, and a painted map is never
    painted again. A project whose saved config cannot be read says nothing here."""
    from rpggen import paths

    saved = paths.from_posix_rel(paths.CONFIG, Path(project))
    if not saved.is_file():
        return
    try:
        data = jsonio.read(saved)
    except (OSError, ValueError, RpgGenError):
        return
    before = data.get("projection", PROJECTION_TOP_DOWN) if isinstance(data, dict) else None
    if before in PROJECTIONS and before != cfg.projection:
        raise RpgGenError(
            "CAT-002",
            file="config",
            reason=f"/projection: this project was generated as {before}, and a generated "
            f"project cannot change its projection (its maps are painted in one); make a new "
            f"project for {cfg.projection}",
        )


def load(path: Path) -> GeneratorConfig:
    data = jsonio.read(path)
    check_sound_names(data)
    schema.validate("config", data)
    check_projection(data)
    return GeneratorConfig.from_json(data)


def save(cfg: GeneratorConfig, path: Path) -> None:
    data = cfg.to_json()
    check_sound_names(data)
    schema.validate("config", data)
    check_projection(data)
    jsonio.write(path, data)


def hash_file_list(entries: list[tuple[str, str]]) -> str:
    """sha256 of the sorted ``path:sha256`` lines (the identity of a folder pack)."""
    lines = sorted(f"{path}:{digest}" for path, digest in entries)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def folder_sha256(folder: Path) -> str:
    """Identity hash of a folder pack: the sorted ``path:sha256`` lines of its files, junk
    (``Thumbs.db``, ``.DS_Store``, ...) left out. It is the hash the inventory computes too, so
    the config and the catalog agree on one identity."""
    from rpggen.core import archive

    entries: list[tuple[str, str]] = []
    files, _links = archive.walk_files(Path(folder))  # a link is never followed or hashed
    for rel in files:
        if rel == archive.COMPLETE_MARKER or rel.endswith(".partial") or archive.is_junk(rel):
            continue
        entries.append((rel, archive.sha256_file(Path(folder) / rel)))
    return hash_file_list(entries)


def pack_ref_from_source(source: Path, pack_id: str, known_sha256: str | None = None) -> PackRef:
    """PackRef for a pack folder or a .zip / .7z / .rar archive.

    ``known_sha256`` is the identity the analysis already computed (``Inventory.source_sha256``);
    with it no pack file is read. Without it an archive is streamed, never read into memory.
    """
    from rpggen.core import archive, pack_sniff

    source = Path(source)
    member = None if source.exists() else pack_sniff.split_member(source)
    if member is not None:  # a pack folder of a bundle: the archive and the folder (T16.22)
        bundle, folder = member
        kind = bundle.suffix.lower().lstrip(".")
        digest = known_sha256 or archive.sha256_file(bundle)
        return PackRef(pack_id, str(bundle.resolve()), digest, kind, (folder,))
    if source.is_dir():
        return PackRef(
            pack_id, str(source.resolve()), known_sha256 or folder_sha256(source), "folder"
        )
    if not source.is_file():
        raise RpgGenError("ARCH-001", path=str(source), reason="does not exist")
    kind = source.suffix.lower().lstrip(".")
    if kind not in ("zip", "7z", "rar"):
        raise RpgGenError("ARCH-001", path=str(source), reason="unsupported file type")
    digest = known_sha256 or archive.sha256_file(source)
    return PackRef(pack_id, str(source.resolve()), digest, kind)


def pack_refs_from_bundle(source: Path, folders: list[str]) -> list[PackRef]:
    """One PackRef per folder of the bundle ``source`` (``--pack-folder``), named by its
    folder. ``ARCH-001`` when ``source`` is not a bundle or has no such folder."""
    from rpggen import ids
    from rpggen.core import archive, pack_sniff

    source = Path(source)
    names = [pack_sniff.folder_in_bundle(source, folder).name for folder in folders]
    kind = "folder" if source.is_dir() else source.suffix.lower().lstrip(".")
    digest = "" if source.is_dir() else archive.sha256_file(source)
    used: set[str] = set()
    refs: list[PackRef] = []
    for name in dict.fromkeys(names):
        pack_id = ids.pack_id_from_name(name, used)
        used.add(pack_id)
        refs.append(PackRef(pack_id, str(source.resolve()), digest, kind, (name,)))
    return refs


def pack_ref_from_folder(folder: Path, pack_id: str) -> PackRef:
    folder = Path(folder)
    if not folder.is_dir():
        raise RpgGenError("ARCH-001", path=str(folder), reason="not a folder")
    return pack_ref_from_source(folder, pack_id)
