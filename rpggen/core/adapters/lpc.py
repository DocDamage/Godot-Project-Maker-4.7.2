from __future__ import annotations

from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import frames, image_facts
from rpggen.core.inventory import Inventory, InventoryFile

LPC_WIDTH = 832
LPC_MIN_HEIGHT = 1344
FRAME = 64
LPC_DIRECTIONS = ["up", "left", "down", "right"]  # row order inside every 4-row block
# (first row, frames in the row) per action; every action has one row per direction.
WALK_ROW, WALK_FRAMES = 8, 9
SLASH_ROW, SLASH_FRAMES = 12, 6
HURT_ROW, HURT_FRAMES = 20, 6
STANDARD_ORIGIN = (32, 60)
BASELINE_TOLERANCE = 4


def _is_lpc_sheet(f: InventoryFile) -> bool:
    return (
        f.kind == "image"
        and f.image is not None
        and f.image["w"] == LPC_WIDTH
        and f.image["h"] % FRAME == 0
        and f.image["h"] >= LPC_MIN_HEIGHT
    )


class LpcAdapter:
    name = "lpc"
    priority = 50

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if any(_is_lpc_sheet(f) for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        for f in inv.files:
            if not _is_lpc_sheet(f) or f.path in ctx.claimed:
                continue
            assert f.image is not None
            if f.image["h"] > LPC_MIN_HEIGHT:
                result.pack_warnings.append(f"lpc_expanded_sheet_rows_ignored:{f.path}")
            mask = image_facts.occupancy(image_facts.load_rgba(root / f.path))
            result.assets.append(self._fragment(f, mask))
        return result

    @staticmethod
    def _fragment(f: InventoryFile, mask) -> AssetFragment:  # noqa: ANN001
        animations: dict[str, Any] = {}
        walk_rects = []
        for i, direction in enumerate(LPC_DIRECTIONS):
            walk = WALK_ROW + i
            slash = SLASH_ROW + i
            animations[f"walk_{direction}"] = {
                "frames": [[c, walk] for c in range(1, WALK_FRAMES)],
                "fps": 10.0,
                "loop": True,
            }
            animations[f"idle_{direction}"] = {"frames": [[0, walk]], "fps": 1.0, "loop": True}
            animations[f"attack_{direction}"] = {
                "frames": [[c, slash] for c in range(SLASH_FRAMES)],
                "fps": 12.0,
                "loop": False,
                "active_frames": [3, 4],
            }
            walk_rects += [(c * FRAME, walk * FRAME, FRAME, FRAME) for c in range(WALK_FRAMES)]
        hurt = [[c, HURT_ROW] for c in range(HURT_FRAMES)]
        animations["hurt"] = {"frames": hurt, "fps": 10.0, "loop": False}
        animations["death"] = {"frames": hurt, "fps": 8.0, "loop": False}
        baseline = frames.baseline_y(mask, walk_rects)
        origin_y = (
            baseline
            if abs(baseline - STANDARD_ORIGIN[1]) > BASELINE_TOLERANCE
            else STANDARD_ORIGIN[1]
        )
        facets = {
            "usage": "sprite",
            "grid": {"cell": [FRAME, FRAME], "margin": [0, 0], "separation": [0, 0]},
            "frame": [FRAME, FRAME],
            "origin": [STANDARD_ORIGIN[0], origin_y],
            "directions": 4,
            "animations": {k: animations[k] for k in sorted(animations)},
        }
        return AssetFragment(f.path, facets, 0.9, "full")
