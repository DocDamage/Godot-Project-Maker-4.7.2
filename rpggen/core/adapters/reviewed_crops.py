"""Exact-source field-crop art layouts. Harvest rules and timing are project defaults.

Stable variants retain existing project references. Rectangles exclude harvested ITEM art;
offsets preserve the native canvas while omitting adjacent-row soil fragments.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def layouts() -> dict[str, Any]:
    return json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "crop_layouts.json").read_text(
            encoding="utf-8"
        )
    )


def reviewed(sha256: str) -> list[dict[str, Any]]:
    return layouts().get(sha256, [])


def layout_key(sha256: str, variant: str) -> str:
    record = next((r for r in reviewed(sha256) if r["variant"] == variant), None)
    if record is None:
        return ""
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
