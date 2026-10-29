"""Complete metadata decisions tied to source bytes and the rendered sprite pixels.

Partial readings remain in pack_readings and never confer confirmation. These records
also guard the input facets: a changed reader must be reviewed again, even if it happens
to render the same picture. User overrides, rules and installed profiles take precedence.
"""

from __future__ import annotations

import copy
import hashlib
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
    return False


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
