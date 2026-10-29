"""Read-only image geometry checks. Passing proves structural validity, not semantic accuracy.

Uses image headers, never full-sheet pixel masks. The resolver accepts catalog paths, including
animation sources and generated helpers, so callers can audit saved analyses without importing.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen.core import catalog as catalog_mod


def validate_images(
    catalog: catalog_mod.Catalog, resolve: Callable[[str], Path | None]
) -> dict[str, Any]:
    sizes: dict[str, tuple[int, int] | None] = {}
    failures: list[dict[str, Any]] = []
    checked, animations, frames = 0, 0, 0

    def size(path: str) -> tuple[int, int] | None:
        if path not in sizes:
            file = resolve(path)
            if file is None:
                sizes[path] = None
                return None
            try:
                with Image.open(file) as im:
                    sizes[path] = im.size
            except (OSError, ValueError, Image.DecompressionBombError):
                sizes[path] = None
        return sizes[path]

    for asset in sorted(catalog.assets, key=lambda a: a.id):
        if asset.kind != "image" or asset.status in ("UNUSED", "MISSING"):
            continue
        checked += 1
        eff = catalog_mod.effective(asset)

        def fail(
            code: str, animation: str = "", index: int | None = None, asset_id: str = asset.id
        ) -> None:
            failures.append(
                {"asset": asset_id, "code": code, "animation": animation, "frame": index}
            )

        base = size(asset.path)
        if base is None:
            fail("image_unavailable")
            continue
        frame = eff.get("frame") or [0, 0]
        if eff.get("usage") == "growth_strip":
            stages = eff.get("stages", 0)
            if stages < 2 or frame[0] <= 0 or frame[1] <= 0:
                fail("crop_geometry")
            elif base != (stages * frame[0], frame[1]):
                fail("crop_strip_size")
        grid = eff.get("grid") or {}
        margin = grid.get("margin", [0, 0])
        gap = grid.get("separation", [0, 0])
        for name, spec in sorted((eff.get("animations") or {}).items()):
            animations += 1
            rects = spec.get("rects") or []
            cells = spec.get("frames") or []
            count = len(rects or cells)
            frames += count
            if count == 0:
                fail("empty_animation", name)
            fps = spec.get("fps", 0)
            if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
                fail("animation_speed", name)
            source = size(spec.get("source", asset.path))
            if source is None:
                fail("animation_source_unavailable", name)
                continue
            durations = spec.get("durations") or []
            if durations and (
                len(durations) != count
                or any(
                    not isinstance(d, (int, float)) or not math.isfinite(d) or d <= 0
                    for d in durations
                )
            ):
                fail("animation_durations", name)
            offsets = spec.get("offsets") or []
            if offsets and (not rects or len(offsets) != count):
                fail("animation_offsets", name)
            if any(
                not isinstance(i, int) or not 0 <= i < count for i in spec.get("active_frames", [])
            ):
                fail("active_frame_index", name)
            for i in range(count):
                if rects:
                    x, y, w, h = rects[i]
                else:
                    col, row = cells[i]
                    w, h = frame
                    x, y = margin[0] + col * (w + gap[0]), margin[1] + row * (h + gap[1])
                    if col < 0 or row < 0:
                        fail("negative_frame_cell", name, i)
                if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > source[0] or y + h > source[1]:
                    fail("frame_outside_image", name, i)
                if rects and offsets and i < len(offsets):
                    ox, oy = offsets[i]
                    if ox < 0 or oy < 0 or ox + w > frame[0] or oy + h > frame[1]:
                        fail("frame_outside_canvas", name, i)
    return {
        "images": checked,
        "animations": animations,
        "frames": frames,
        "image_headers": len(sizes),
        "failures": failures,
        "passed": not failures,
    }
