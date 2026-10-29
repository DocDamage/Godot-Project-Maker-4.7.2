"""Source-bound segmentation corrections; parent IDs remain available for old review keys."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def layouts() -> dict[str, Any]:
    return json.loads(
        (Path(__file__).parents[2] / "data" / "reviewed_segments.json").read_text(encoding="utf-8")
    )


def reviewed(sha256: str) -> dict[str, Any]:
    return layouts().get(sha256, {})


def layout_key(sha256: str, variant: str) -> str:
    for parent, record in reviewed(sha256).items():
        if parent == variant or any(c["variant"] == variant for c in record.get("children", [])):
            return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return ""
