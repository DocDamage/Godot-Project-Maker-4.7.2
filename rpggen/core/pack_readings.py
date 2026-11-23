"""Reviewed region facts, bound to the complete source image hash (no pack art).

Only the fields actually checked are supplied. Unreviewed regions retain their normal
confidence; renaming or changing a sheet never applies facts to a different picture.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

from rpggen import jsonio


@lru_cache(maxsize=1)
def readings() -> dict[str, dict[str, Any]]:
    return jsonio.read(Path(__file__).parents[1] / "data" / "reviewed_regions.json")


def region_facts(source_sha256: str, variant: str) -> dict[str, Any]:
    return copy.deepcopy(readings().get(source_sha256, {}).get(variant, {}))


def apply_facts(facets: dict[str, Any], checked: dict[str, Any]) -> None:
    """Apply checked fields without changing confidence or losing unrelated tags."""
    if not checked:
        return
    tags = set(facets.get("tags") or []) | set(checked.get("tags") or [])
    facets.update(copy.deepcopy(checked))
    if checked.get("role") not in (None, "BUILDING"):
        tags.discard("house")
        facets.pop("roles_alt", None)
    if tags:
        facets["tags"] = sorted(tags)
    if checked.get("usage") == "tiles":
        facets.pop("frame", None)
