"""Pure logic of the Options page: feature dependencies, presets, layers, input bindings."""

from __future__ import annotations

import copy
import dataclasses
from typing import Any

from rpggen import schema
from rpggen.core import config as config_mod

# feature -> the features it needs
FEATURE_DEPS: dict[str, tuple[str, ...]] = {"demo": ("dialogue", "combat", "save")}
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


def effective_features(wanted: dict[str, bool]) -> dict[str, bool]:
    """``wanted`` with every feature whose dependencies are off forced off."""
    out = dict(wanted)
    for key in FEATURE_DEPS:
        if missing_deps(out, key):
            out[key] = False
    return out


def _tiles(value: float) -> str:
    """40, 22.5 and 11.25 as they are; an unending fraction (13.333...) to one decimal."""
    exact = round(value, 2)
    return f"{exact:g}" if abs(value - exact) < 1e-9 else f"{round(value, 1):g}"


def tiles_hint(resolution: tuple[int, int], tile: int) -> str:
    return f"≈ {_tiles(resolution[0] / tile)} × {_tiles(resolution[1] / tile)} tiles on screen"


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
    if isinstance(preset.get("starter_map"), dict):
        known = config_mod.starter_map_defaults(cfg.archetype)
        changes["starter_map"] = {
            k: copy.deepcopy(v) for k, v in preset["starter_map"].items() if k in known
        }
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
