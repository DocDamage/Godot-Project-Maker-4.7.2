"""Hash-bound growth layouts inspected after the owner's orchard choice (2026-10-28).

Only the current, unshadowed Farm RPG sheets are canonical crops. Other versions remain
available as CROP art. Seasons come from the pack; game timing is planned separately.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def layouts() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "data" / "orchard_layouts.json"
    return json.loads(path.read_text(encoding="utf-8"))


def reviewed(sha256: str) -> dict[str, Any] | None:
    return layouts().get(sha256)
