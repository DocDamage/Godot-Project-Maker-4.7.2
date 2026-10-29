"""Complete metadata decisions tied to source bytes and the rendered sprite pixels.

Partial readings remain in pack_readings and never confer confirmation. These records
also guard the input facets: a changed reader must be reviewed again, even if it happens
to render the same picture. User overrides, rules and installed profiles take precedence.
"""

from __future__ import annotations

import copy
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import jsonio


@lru_cache(maxsize=1)
def readings() -> dict[str, Any]:
    return jsonio.read(Path(__file__).parents[1] / "data" / "confirmed_metadata.json")


def pixel_hash(path: Path) -> str:
    """Hash decoded RGBA pixels, ignoring invisible RGB and image-file encoding."""
    with Image.open(path) as im:
        rgba = np.asarray(im.convert("RGBA")).copy()
        rgba[rgba[..., 3] == 0] = 0
        return hashlib.sha256(f"{im.width}x{im.height}\n".encode() + rgba.tobytes()).hexdigest()


def decision(
    source_sha256: str, variant: str, facets: dict[str, Any], picture: Path
) -> dict[str, Any] | None:
    record = readings().get("assets", {}).get(source_sha256, {}).get(variant)
    if not record or facets != record["input"]:
        return None
    approved = record.get("approved", {})
    if not complete(approved, record.get("kind", "static_object")):
        return None
    try:
        if pixel_hash(picture) != record["pixel_sha256"]:
            return None
    except (OSError, ValueError):
        return None
    return copy.deepcopy(approved)


def complete(facets: dict[str, Any], kind: str = "static_object") -> bool:
    if kind == "static_object":
        return complete_static(facets)
    if kind == "static_battler":
        return complete_static_battler(facets)
    if kind == "static_animal":
        return _complete_static_sprite(facets, "ANIMAL", "static_animal")
    if kind == "actor_art":
        return _complete_actor_art(facets)
    if kind == "crop_art":
        return _complete_crop_art(facets)
    return False


def _complete_crop_art(facets: dict[str, Any]) -> bool:
    """A source-bound field growth strip; timing, seasons and harvest yields stay defaults."""
    if set(facets) - {"usage", "role", "size", "frame", "origin", "grid", "stages", "tags"}:
        return False
    frame, stages = facets.get("frame"), facets.get("stages")
    if facets.get("usage") != "growth_strip" or facets.get("role") != "CROP":
        return False
    if (
        not isinstance(frame, list)
        or len(frame) != 2
        or any(type(v) is not int or v <= 0 for v in frame)
        or type(stages) is not int
        or not 2 <= stages <= 32
    ):
        return False
    if facets.get("size") != [frame[0] * stages, frame[1]]:
        return False
    if facets.get("grid") != {"cell": frame, "margin": [0, 0], "separation": [0, 0]}:
        return False
    if facets.get("origin") != [frame[0] // 2, frame[1] - 1]:
        return False
    tags = facets.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        return False
    produce = [t for t in tags if re.fullmatch(r"produce:[a-z][a-z0-9_]*", t)]
    return (
        len(produce) == 1
        and len(tags) == 4
        and set(tags) == {"crop", "crop_art", "growth_by:reviewed_sheet", produce[0]}
    )


def _complete_actor_art(facets: dict[str, Any]) -> bool:
    """Reviewed NPC art cells/facing, with explicit playback and pivot defaults.

    This kind does not approve collision, movement, interaction or source-authored timing.
    Separate animation sources and trimmed frames need a different review contract.
    """
    allowed = {
        "usage",
        "role",
        "size",
        "frame",
        "origin",
        "grid",
        "animations",
        "tags",
        "directions",
        "character_index",
    }
    if set(facets) - allowed or facets.get("usage") != "sprite" or facets.get("role") != "NPC":
        return False
    size, frame = facets.get("size"), facets.get("frame")
    if not isinstance(size, list) or not isinstance(frame, list):
        return False
    if any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(type(v) is not int or v <= 0 for v in pair)
        for pair in (size, frame)
    ):
        return False
    if any(size[i] % frame[i] for i in range(2)):
        return False
    if facets.get("origin") != [frame[0] // 2, frame[1] - 1]:
        return False
    if facets.get("grid") != {"cell": frame, "margin": [0, 0], "separation": [0, 0]}:
        return False
    tags = facets.get("tags")
    if (
        not isinstance(tags, list)
        or "actor_art" not in tags
        or any(tag not in ("actor_art", "size_form:16") for tag in tags)
    ):
        return False
    if "directions" in facets and (
        type(facets["directions"]) is not int or facets["directions"] != 4
    ):
        return False
    cols, rows = size[0] // frame[0], size[1] // frame[1]
    index = facets.get("character_index")
    if "character_index" in facets and (
        type(index) is not int or not 0 <= index < 8 or (cols, rows) != (12, 8)
    ):
        return False
    animations = facets.get("animations")
    if not isinstance(animations, dict) or not animations:
        return False
    for name, spec in animations.items():
        if not re.fullmatch(r"(?:idle|walk|phone|sit[23]?)_(?:down|up|left|right)", name):
            return False
        if not isinstance(spec, dict) or set(spec) != {"frames", "fps", "loop"}:
            return False
        if type(spec["fps"]) not in (int, float) or spec["fps"] not in (1, 6, 8):
            return False  # explicit presentation defaults, never inferred artist timing
        if (
            type(spec["loop"]) is not bool
            or not isinstance(spec["frames"], list)
            or not spec["frames"]
        ):
            return False
        for cell in spec["frames"]:
            if (
                not isinstance(cell, list)
                or len(cell) != 2
                or any(type(v) is not int for v in cell)
            ):
                return False
            x, y = cell
            if not (0 <= x < cols and 0 <= y < rows):
                return False
            if index is not None and not (
                index % 4 * 3 <= x < index % 4 * 3 + 3 and index // 4 * 4 <= y < index // 4 * 4 + 4
            ):
                return False
    return True


def complete_static_battler(facets: dict[str, Any]) -> bool:
    """A reviewed whole enemy illustration, not a moving actor or a combat-behavior claim.

    One-frame idle is a presentation default. Collision and attack/movement behavior are
    not inferred from the illustration and must remain absent from this kind of record.
    """
    return _complete_static_sprite(facets, "ENEMY", "static_battler")


def _complete_static_sprite(facets: dict[str, Any], role: str, tag: str) -> bool:
    size, origin = facets.get("size"), facets.get("origin")
    return bool(
        facets.get("usage") == "sprite"
        and facets.get("role") == role
        and facets.get("tags") == [tag]
        and isinstance(size, list)
        and len(size) == 2
        and all(isinstance(v, int) and v > 0 for v in size)
        and facets.get("frame") == size
        and isinstance(origin, list)
        and len(origin) == 2
        and all(isinstance(v, int) and 0 <= v < size[i] for i, v in enumerate(origin))
        and facets.get("grid") == {"cell": size, "margin": [0, 0], "separation": [0, 0]}
        and facets.get("animations")
        == {"idle_down": {"fps": 1.0, "frames": [[0, 0]], "loop": True}}
        and set(facets)
        <= {"usage", "role", "size", "frame", "origin", "grid", "animations", "tags"}
    )


def complete_static(facets: dict[str, Any]) -> bool:
    """The scope of this review: a complete, non-blocking single-frame object."""
    size, origin = facets.get("size"), facets.get("origin")
    return bool(
        facets.get("usage") == "object"
        and facets.get("role") in ("DECORATION", "ITEM", "TOOL", "WEAPON", "EFFECT")
        and isinstance(size, list)
        and len(size) == 2
        and all(isinstance(v, int) and v > 0 for v in size)
        and facets.get("frame") == size
        and isinstance(origin, list)
        and len(origin) == 2
        and all(isinstance(v, int) and 0 <= v < size[i] for i, v in enumerate(origin))
        and facets.get("animations") == {}
        and facets.get("collision") == {"profile": "NONE"}
    )
