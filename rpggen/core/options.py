"""Pure logic of the Options page: feature dependencies, presets, layers, input bindings."""

from __future__ import annotations

import copy
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


def tiles_hint(resolution: tuple[int, int], tile: int) -> str:
    return f"≈ {resolution[0] / tile:g} × {resolution[1] / tile:g} tiles on screen"


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


def config_errors(cfg: config_mod.GeneratorConfig) -> list[str]:
    """Schema violations of the option values. The pack list is the project page's concern and
    the layers have friendlier messages in ``layer_issues``."""
    return [
        f"{path}: {message}"
        for path, message in schema.errors("config", cfg.to_json())
        if not path.startswith(("/packs", "/map_layers"))
    ]
