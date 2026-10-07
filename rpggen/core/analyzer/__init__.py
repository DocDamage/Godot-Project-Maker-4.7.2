from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rpggen.core import cache
from rpggen.core.inventory import Inventory

log = logging.getLogger(__name__)

ANALYZER_VERSION = 3
MIN_REGION_GRID_SCORE = 0.6


def analyze_array(a, mask) -> dict[str, Any]:  # noqa: ANN001 - numpy arrays
    """Pure analysis of one decoded image (see 02_SCHEMAS §3; adds fully_opaque/character_sheet)."""
    from rpggen.core.analyzer import frames, grid, image_facts, regions

    h, w = mask.shape
    bbox = image_facts.opaque_bbox(mask)
    candidates = grid.detect_grid(a, mask)
    strip = frames.detect_strip(mask, candidates)
    sheet = frames.detect_character_sheet(a, mask, candidates[0] if candidates else None)
    region_list: list[list[int]] = []
    if candidates and candidates[0].score >= MIN_REGION_GRID_SCORE:
        region_list = [list(r) for r in regions.detect_regions(mask, candidates[0])]
    baseline = 0
    if strip is not None:
        fw, fh = strip.frame
        rects = [
            (i * fw, 0, fw, fh) if strip.axis == "x" else (0, i * fh, fw, fh)
            for i in range(strip.frames)
        ]
        baseline = frames.baseline_y(mask, rects)
    elif sheet is not None:
        # frame-relative, like strips: the median lowest occupied row of every frame
        fw, fh = sheet.frame
        rects = [(c * fw, r * fh, fw, fh) for r in range(sheet.rows) for c in range(sheet.cols)]
        baseline = frames.baseline_y(mask, rects)
    elif bbox is not None:
        baseline = bbox[1] + bbox[3] - 1
    return {
        "w": w,
        "h": h,
        "has_alpha": bool((a[..., 3] < 255).any()),
        "fully_opaque": image_facts.is_fully_opaque(a),
        "opaque_bbox": list(bbox) if bbox else None,
        "grid_candidates": [
            {
                "cell": list(c.cell),
                "margin": list(c.margin),
                "separation": list(c.separation),
                "score": c.score,
                "nonempty_cells": c.nonempty_cells,
                "total_cells": c.total_cells,
            }
            for c in candidates
        ],
        "grid_confidence": grid.confidence(candidates),
        "regions": region_list,
        "strip": (
            {"axis": strip.axis, "frames": strip.frames, "frame": list(strip.frame)}
            if strip
            else None
        ),
        "character_sheet": (
            {
                "frame": list(sheet.frame),
                "cols": sheet.cols,
                "rows": sheet.rows,
                "row_directions": sheet.row_directions,
                "direction_confidence": sheet.direction_confidence,
            }
            if sheet
            else None
        ),
        "baseline_y": baseline,
        "dominant_colors": image_facts.dominant_colors(a),
        "nine_slice": image_facts.detect_nine_slice(a),
    }


def analyze_file(path: Path, sha256: str, *, use_cache: bool = True) -> dict[str, Any]:
    """Analysis of an image file, cached by hash and analyzer version."""
    from rpggen.core.analyzer import image_facts

    if use_cache:
        hit = cache.get(sha256, ANALYZER_VERSION)
        if hit is not None:
            return hit
    a = image_facts.load_rgba(path)
    data = analyze_array(a, image_facts.occupancy(a))
    if use_cache:
        try:
            cache.put(sha256, ANALYZER_VERSION, data)
        except OSError:
            log.debug("could not write analysis cache for %s", sha256, exc_info=True)
    data["sha256"] = sha256
    data["analyzer_version"] = ANALYZER_VERSION
    return data


def analyzer_for(inv: Inventory, root: Path, *, use_cache: bool = True) -> Callable[[str], dict]:
    """A callback ``pack path -> analysis`` for adapters (memoized on top of the cache)."""
    hashes = {f.path: f.sha256 for f in inv.files}
    memo: dict[str, dict[str, Any]] = {}

    def analyze(rel: str) -> dict[str, Any]:
        if rel not in memo:
            memo[rel] = analyze_file(root / rel, hashes[rel], use_cache=use_cache)
        return memo[rel]

    return analyze
