"""Pure logic of the Options page: feature dependencies, presets, layers, input bindings."""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from typing import Any

from rpggen import schema
from rpggen.core import config as config_mod

# feature -> the features it needs. The demo map is painted with the tile set and its villager,
# enemy and save point need their systems; the navigation layer is only read by enemies.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "demo": ("tilesets", "dialogue", "combat", "save"),
    "navigation": ("combat",),
}
FEATURE_DEPS = DEPENDENCIES  # the name before 1.1
RESOLUTION_PRESETS = [(320, 180), (384, 216), (480, 270), (640, 360)]
WINDOW_PRESETS = [(960, 540), (1280, 720), (1600, 900), (1920, 1080)]
# editable binding fields of the input table and the type of their entries
BINDING_FIELDS: tuple[tuple[str, type], ...] = (
    ("keys", str),
    ("mouse_buttons", int),
    ("joy_buttons", int),
)

# Every feature of config.FEATURE_KEYS: (group, label, one sentence). A test checks that none is
# missing.
FEATURE_GROUPS = ("World", "Game systems", "Tools")
FEATURE_INFO: dict[str, tuple[str, str, str]] = {
    "tilesets": (
        "World",
        "Tilesets",
        "Cuts your tile sheets into a Godot TileSet you can paint with.",
    ),
    "collision": (
        "World",
        "Collision",
        "Walls, water and tall objects block the player and the enemies.",
    ),
    "terrain": (
        "World",
        "Terrain",
        "Autotiles: terrains that join their edges and corners while you paint.",
    ),
    "animations": (
        "World",
        "Animations",
        "Builds walk, idle and attack animations from your character sheets.",
    ),
    "navigation": (
        "World",
        "Navigation",
        "Adds a navigation layer to the TileSet so enemies can path around walls. Off by "
        "default: enemies walk straight at the player.",
    ),
    "save": ("Game systems", "Save / load", "Three save slots, an autosave and a Load menu."),
    "dialogue": (
        "Game systems",
        "Dialogue",
        "A dialogue box with choices, conditions and events (items, flags).",
    ),
    "combat": (
        "Game systems",
        "Combat",
        "Battles (turn-based) or real-time fighting (action), with enemies and rewards.",
    ),
    "demo": (
        "Game systems",
        "Demo scene",
        "A starter map with a villager, a chest, an enemy, a house and a second area. You can "
        "remove it later.",
    ),
    "editor_tools": (
        "Tools",
        "Editor tools",
        "The Assets dock in the Godot editor: drag buildings, props and enemies into maps.",
    ),
    "debug_tools": (
        "Tools",
        "Debug tools",
        "An overlay with the frame rate and a few shortcuts while you test (debug builds only).",
    ),
}


def features_in_group(group: str) -> list[str]:
    """The feature keys of a group, in the order they are shown."""
    return [k for k, (g, _label, _text) in FEATURE_INFO.items() if g == group]


def feature_label(key: str) -> str:
    return FEATURE_INFO.get(key, ("", key, ""))[1]


LAYER_GROUND_REQUIRED = "The Ground layer is required."
LAYER_EMPTY = "Layer names cannot be empty."
LAYER_DUPLICATE = "Layer names must be unique."


def missing_deps(features: dict[str, bool], key: str) -> list[str]:
    """Features ``key`` needs that are currently switched off."""
    return [dep for dep in FEATURE_DEPS.get(key, ()) if not features.get(dep, False)]


def stages_text(archetype: str, starter_map: dict[str, Any]) -> str:
    """What an arcade kind's options make: "1 stage, scrolling up"."""
    if archetype == "shmup":
        sideways = starter_map.get("orientation") == "horizontal"
        return "1 stage, scrolling " + ("right" if sideways else "up")
    return "stages"


def effective_features(wanted: dict[str, bool]) -> dict[str, bool]:
    """``wanted`` with every feature whose dependencies are off forced off."""
    out = dict(wanted)
    for key in DEPENDENCIES:
        if missing_deps(out, key):
            out[key] = False
    return out


def _tiles(value: float) -> str:
    """40, 22.5 and 11.25 as they are; an unending fraction (13.333...) to one decimal."""
    exact = round(value, 2)
    return f"{exact:g}" if abs(value - exact) < 1e-9 else f"{round(value, 1):g}"


def tiles_hint(resolution: tuple[int, int], tile: int) -> str:
    return f"≈ {_tiles(resolution[0] / tile)} × {_tiles(resolution[1] / tile)} tiles on screen"


IMPORT_OVERHEAD = 1.8  # project bytes / pack bytes, measured on sample_pack: 3,378,223 / 1,860,386
# (the copied art, Godot's import cache and the runtime, tests and scripts every project carries)


@dataclass(frozen=True)
class Summary:
    """What the Options page's summary card shows (plain data, no widgets)."""

    archetype: str
    maps: list[str]  # "Starter map", "Second area", "3 interiors"
    systems: list[str]  # the labels of the features that are on
    tile_size: int
    tiles: str  # "≈ 40 × 22.5 tiles on screen"
    world: str = ""  # a metroidvania's starter world: "6 rooms, 2 abilities, a guardian"


def summarize(
    archetype: str,
    features: dict[str, bool],
    starter_map: dict[str, Any],
    tile_size: int,
    resolution: tuple[int, int],
    imported_maps: dict[str, Any] | None = None,
) -> Summary:
    """The summary of the current (unsaved) options. The demo feature makes the starter map and
    its second area; each building of the starter map has an interior. An imported map chosen as
    the starter map replaces the starter map and its second area (T12.49)."""
    if archetype in config_mod.ARCADE_KINDS:
        # a run through stages (M16): no starter map, no imported maps
        on = effective_features(features)
        systems = [FEATURE_INFO[key][1] for key in FEATURE_INFO if on.get(key)]
        hint = tiles_hint(resolution, tile_size)
        return Summary(archetype, [], systems, tile_size, hint, stages_text(archetype, starter_map))
    if archetype == "metroidvania":
        # a world of rooms (T14.06): no starter map, no imported maps, no pathfinding
        from rpggen.core import room_plan

        try:
            world = room_plan.describe(starter_map)
        except room_plan.RoomPlanError:
            world = ""
        on = effective_features({**features, "navigation": False})
        systems = [FEATURE_INFO[key][1] for key in FEATURE_INFO if on.get(key)]
        return Summary(archetype, [], systems, tile_size, tiles_hint(resolution, tile_size), world)
    maps: list[str] = []
    imported = imported_maps or {}
    extra = [m for m in imported.get("include", []) if m != imported.get("starter", "")]
    if imported.get("starter"):
        maps.append("Starter map (imported)")
    elif features.get("demo", False):
        maps.append("Starter map")
        maps.append("Second area")
        buildings = int(starter_map.get("buildings", 0) or 0)
        if buildings:
            maps.append(f"{buildings} interior" + ("s" if buildings != 1 else ""))
    if extra:
        maps.append(f"{len(extra)} imported map" + ("s" if len(extra) != 1 else ""))
    systems = [
        FEATURE_INFO[key][1] for key in FEATURE_INFO if effective_features(features).get(key)
    ]
    return Summary(archetype, maps, systems, tile_size, tiles_hint(resolution, tile_size))


def imported_map_label(imported_map: dict[str, Any]) -> str:
    """How the Options page names an imported map: ``maps/town · tiled_map · 40 × 24 tiles``."""
    stem = (
        str(imported_map["id"]).removeprefix(str(imported_map["pack_id"]) + ".").replace(".", "/")
    )
    width, height = imported_map["size"]
    return f"{stem} · {imported_map['pack_id']} · {width} × {height} tiles"


def intgrid_rows(maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every IntGrid value of the imported maps, for the "Solid values" list: ``map`` (id),
    ``layer``, ``value``, ``name``, ``solid`` and a ``label``."""
    rows: list[dict[str, Any]] = []
    for imported_map in maps:
        for layer in imported_map["layers"]:
            for v in layer.get("values", []) if layer["kind"] == "intgrid" else []:
                shown = f"{v['value']} ({v['name']})" if v["name"] else str(v["value"])
                rows.append(
                    {
                        "map": imported_map["id"],
                        "layer": layer["name"],
                        "value": v["value"],
                        "name": v["name"],
                        "solid": v["solid"],
                        "label": f"{imported_map_label(imported_map)} · {layer['name']} · {shown}",
                    }
                )
    return rows


def set_solid(maps: list[dict[str, Any]], choices: dict[tuple[str, str, int], bool]) -> int:
    """Applies ``(map id, layer, value) -> solid`` to the catalog's maps; returns how many
    values changed. The choice is kept when the catalog is built again."""
    changed = 0
    for imported_map in maps:
        for layer in imported_map["layers"]:
            for v in layer.get("values", []) if layer["kind"] == "intgrid" else []:
                key = (imported_map["id"], layer["name"], int(v["value"]))
                if key in choices and bool(v["solid"]) != choices[key]:
                    v["solid"] = choices[key]
                    changed += 1
    return changed


def normalize_imported_maps(selection: dict[str, Any], known: list[str]) -> dict[str, Any]:
    """``selection`` without maps the catalog no longer has, the starter among the included maps,
    and without the keys that hold their default (an empty selection is ``{}``)."""
    starter = str(selection.get("starter", ""))
    starter = starter if starter in known else ""
    include = sorted(
        ({str(i) for i in selection.get("include", [])} | ({starter} if starter else set()))
        & set(known)
    )
    return {k: v for k, v in (("include", include), ("starter", starter)) if v}


def estimate_generation_seconds(
    timings: dict[str, float], saved_assets: int, assets: int
) -> float | None:
    """The saved phase timings scaled by the ratio of asset counts; None without history (no
    timings, or no count of the assets they were measured on)."""
    total = sum(v for v in timings.values() if v > 0)
    if total <= 0 or saved_assets <= 0 or assets <= 0:
        return None
    return total * assets / saved_assets


def estimate_project_bytes(pack_bytes: int) -> int:
    """The size of the generated project: the packs' bytes times ``IMPORT_OVERHEAD``."""
    return round(max(0, pack_bytes) * IMPORT_OVERHEAD)


TILES_ACROSS = 20  # about this many tiles across is a comfortable view for a 2D RPG


def suggested_preset(presets: list[tuple[int, int]], tile: int) -> tuple[int, int] | None:
    """The preset that shows about ``TILES_ACROSS`` tiles across (the larger one on a tie)."""
    if not presets or tile <= 0:
        return None
    return min(presets, key=lambda p: (abs(p[0] / tile - TILES_ACROSS), -p[0]))


def preset_index(presets: list[tuple[int, int]], value: tuple[int, int]) -> int:
    """Index of ``value`` in ``presets``, or ``len(presets)`` (Custom)."""
    return presets.index(value) if value in presets else len(presets)


def layer_issues(layers: list[str]) -> list[str]:
    out: list[str] = []
    if "Ground" not in layers:
        out.append(LAYER_GROUND_REQUIRED)
    if any(not name.strip() for name in layers):
        out.append(LAYER_EMPTY)
    if len(set(layers)) != len(layers):
        out.append(LAYER_DUPLICATE)
    return out


def add_layer(layers: list[str], name: str) -> list[str]:
    name = name.strip()
    return layers if not name or name in layers else [*layers, name]


def remove_layer(layers: list[str], name: str) -> list[str]:
    return layers if name == "Ground" else [n for n in layers if n != name]


def parse_list(text: str, kind: type) -> list[Any]:
    """``"A, B"`` -> ``["A", "B"]`` (or ints); raises ValueError on a bad integer."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return [kind(p) for p in parts]


def format_list(values: list[Any]) -> str:
    return ", ".join(str(v) for v in values)


def apply_binding_text(bindings: dict[str, Any], field: str, text: str) -> dict[str, Any]:
    """A copy of one action's ``bindings`` with ``field`` set from ``text`` (empty removes it).

    Fields the table does not edit (``joy_axes``) are kept."""
    kind = dict(BINDING_FIELDS)[field]
    out = copy.deepcopy(bindings)
    values = parse_list(text, kind)
    if values:
        out[field] = values
    else:
        out.pop(field, None)
    return out


# ---------------------------------------------------------------------------------- presets

PRESET_KEYS = (
    "features",
    "resolution",
    "window_size",
    "map_layers",
    "input",
    "validation",
    "starter_map",
)
STARTER_SIZE_PRESETS = [(32, 20), (40, 24), (64, 40)]
STARTER_COUNT_KEYS = ("buildings", "npcs", "enemies", "chests", "decorations", "ground_patches")


def to_preset(cfg: config_mod.GeneratorConfig) -> dict[str, Any]:
    """The option part of a config: never the packs, the name, the seed or the starter picks."""
    return {
        "features": dict(cfg.features),
        "resolution": list(cfg.resolution),
        "window_size": list(cfg.window_size),
        "map_layers": list(cfg.map_layers),
        "input": copy.deepcopy(cfg.input),
        "validation": dict(cfg.validation),
        "starter_map": cfg.starter_map_options(),
    }


def default_preset(archetype: str = "turn_based") -> dict[str, Any]:
    return to_preset(config_mod.default_for("x", [], archetype=archetype))


# The presets every installation has (T13.06): key -> (label, the features that are on; None for
# the defaults). They cannot be renamed or deleted; saving one under a name makes a copy.
BUILTIN_PRESETS: dict[str, tuple[str, tuple[str, ...] | None]] = {
    "everything": ("Everything", None),
    "minimal": ("Minimal", ("tilesets", "collision", "animations", "save", "dialogue")),
    "tilesets": ("Just the tilesets", ("tilesets", "collision", "terrain")),
}


def builtin_label(key: str) -> str:
    return BUILTIN_PRESETS[key][0]


def builtin_labels() -> list[str]:
    return [label for label, _on in BUILTIN_PRESETS.values()]


def builtin_preset(key: str, archetype: str = "turn_based") -> dict[str, Any] | None:
    """The options of a built-in preset: the defaults, with only the preset's features on and,
    for the two small ones, only the Windows export. None for an unknown key."""
    if key not in BUILTIN_PRESETS:
        return None
    preset = default_preset(archetype)
    wanted = BUILTIN_PRESETS[key][1]
    if wanted is not None:
        preset["features"] = {name: name in wanted for name in preset["features"]}
        preset["export_targets"] = list(config_mod.EXPORT_TARGET_DEFAULT)
    return preset


def input_fits(archetype: str, bindings: dict[str, Any]) -> bool:
    """True when ``bindings`` are the actions of ``archetype`` (the other archetype's differ)."""
    return set(bindings) == set(config_mod.default_input(archetype))


def apply_preset(
    cfg: config_mod.GeneratorConfig, preset: dict[str, Any]
) -> config_mod.GeneratorConfig:
    """A copy of ``cfg`` with the preset's options. Unknown keys are ignored; bindings of the
    other archetype are not taken over. Raises ValueError when the result is not valid."""
    changes: dict[str, Any] = {}
    if isinstance(preset.get("features"), dict):
        merged = dict(cfg.features)
        merged.update({k: bool(v) for k, v in preset["features"].items() if k in merged})
        changes["features"] = effective_features(merged)
    for key in ("resolution", "window_size"):
        value = preset.get(key)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            changes[key] = (int(value[0]), int(value[1]))
    if isinstance(preset.get("map_layers"), list):
        changes["map_layers"] = [str(n) for n in preset["map_layers"]]
    if isinstance(preset.get("input"), dict) and input_fits(cfg.archetype, preset["input"]):
        changes["input"] = copy.deepcopy(preset["input"])
    if isinstance(preset.get("validation"), dict):
        merged_validation = dict(cfg.validation)
        merged_validation.update(
            {
                k: bool(v)
                for k, v in preset["validation"].items()
                if k in ("smoke_test", "export_check")
            }
        )
        changes["validation"] = merged_validation
    if isinstance(preset.get("export_targets"), list):  # only the built-in presets carry it
        chosen = [t for t in config_mod.EXPORT_TARGETS if t in preset["export_targets"]]
        changes["export_targets"] = chosen or list(config_mod.EXPORT_TARGET_DEFAULT)
    if isinstance(preset.get("starter_map"), dict):
        known = config_mod.starter_map_defaults(cfg.archetype)
        changes["starter_map"] = {
            k: copy.deepcopy(v) for k, v in preset["starter_map"].items() if k in known
        }
    if cfg.archetype == "metroidvania":
        # rooms have no pathfinding and their layers are fixed: a preset does not change that
        changes.pop("map_layers", None)
        if "features" in changes:
            changes["features"] = {**changes["features"], "navigation": False}
    result = dataclasses.replace(cfg, **changes)
    problems = [message for message in config_errors(result) if not message.startswith("/packs")]
    if problems:
        raise ValueError("; ".join(problems))
    return result


# ------------------------------------------------------------------------- key capture

_KEY_NAMES = {
    "Return": "Enter",
    "Esc": "Escape",
    "Del": "Delete",
    "Ins": "Insert",
    "PgUp": "PageUp",
    "PgDown": "PageDown",
}


def key_name(qt_text: str) -> str | None:
    """The name the config (and Godot) uses for a key, from Qt's text for it (``QKeySequence``
    ``toString``); None for a bare modifier or nothing."""
    text = qt_text.strip()
    if not text or text in ("Ctrl", "Alt", "Meta"):
        return None
    return _KEY_NAMES.get(text, text)


def config_errors(cfg: config_mod.GeneratorConfig) -> list[str]:
    """Schema violations of the option values. The pack list is the project page's concern and
    the layers have friendlier messages in ``layer_issues``."""
    return [
        f"{path}: {message}"
        for path, message in schema.errors("config", cfg.to_json())
        if not path.startswith(("/packs", "/map_layers"))
    ]
