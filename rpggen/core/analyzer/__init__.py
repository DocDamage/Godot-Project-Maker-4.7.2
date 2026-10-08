from __future__ import annotations

import concurrent.futures
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rpggen.core import cache
from rpggen.core.archive import Control, Progress
from rpggen.core.inventory import Inventory

log = logging.getLogger(__name__)

ANALYZER_VERSION = 4
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


POOL_THRESHOLD = 32  # use the process pool for at least this many images to analyze
CHUNK = 4  # images per task of the pool
HUGE_PIXELS = 64_000_000  # an image this large is analyzed in the parent, one at a time


def _analyze_chunk(
    jobs: list[tuple[str, str, str, bool]],
) -> list[tuple[str, dict[str, Any] | None]]:
    """Worker: analyze a few images (each writes its own cache entry); a failure gives None, and
    the adapter that needs that image meets the same error where it can handle it."""
    out: list[tuple[str, dict[str, Any] | None]] = []
    for rel, path, sha256, use_cache in jobs:
        try:
            out.append((rel, analyze_file(Path(path), sha256, use_cache=use_cache)))
        except Exception:  # noqa: BLE001 - reported again, with its context, by the caller
            log.debug("could not analyze %s", rel, exc_info=True)
            out.append((rel, None))
    return out


def prewarm(
    inv: Inventory,
    root: Path,
    *,
    use_cache: bool = True,
    is_cancelled: Callable[[], bool] | None = None,
    on_progress: Progress | None = None,
) -> dict[str, dict[str, Any]]:
    """Analyze every image of a pack whose ``(sha256, ANALYZER_VERSION)`` is not cached, in a
    process pool, and return ``{pack path: analysis}`` for those (it seeds ``analyzer_for``).

    Each worker writes the cache entry of its image. With ``use_cache=False`` nothing is read or
    written and the results stay in memory. Images over 64 megapixels are analyzed here, one at
    a time, to bound memory. ``on_progress`` receives ``("Analyzing images", done, total)`` and a
    cancel raises ``archive.Cancelled`` (the pool is shut down without starting what is queued).
    """
    ctl = Control(on_progress, is_cancelled)
    todo = [
        f
        for f in inv.files
        if f.kind == "image" and (not use_cache or cache.get(f.sha256, ANALYZER_VERSION) is None)
    ]
    total = len(todo)
    if not total:
        return {}
    results: dict[str, dict[str, Any]] = {}
    label = "Analyzing images"

    def done_with(batch: list[tuple[str, dict[str, Any] | None]]) -> None:
        for rel, data in batch:
            if data is not None:
                results[rel] = data
        ctl.report(label, len(results), total)

    def job(f: Any) -> tuple[str, str, str, bool]:
        return (f.path, str(root / f.path), f.sha256, use_cache)

    huge = [f for f in todo if f.image and f.image["w"] * f.image["h"] > HUGE_PIXELS]
    pooled = [f for f in todo if f not in huge]
    if len(pooled) >= POOL_THRESHOLD:
        workers = min(8, os.cpu_count() or 1)
        pool = concurrent.futures.ProcessPoolExecutor(max_workers=workers)
        try:
            futures = [
                pool.submit(_analyze_chunk, [job(f) for f in pooled[i : i + CHUNK]])
                for i in range(0, len(pooled), CHUNK)
            ]
            for future in concurrent.futures.as_completed(futures):
                ctl.check()
                done_with(future.result())
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
    else:
        for f in pooled:
            ctl.check()
            done_with(_analyze_chunk([job(f)]))
    for f in huge:
        ctl.check()
        done_with(_analyze_chunk([job(f)]))
    ctl.report(label, total, total)
    return results


def analyzer_for(
    inv: Inventory,
    root: Path,
    *,
    use_cache: bool = True,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    prewarmed: dict[str, dict[str, Any]] | None = None,
) -> Callable[[str], dict]:
    """A callback ``pack path -> analysis`` for adapters (memoized on top of the cache).

    ``prewarmed`` is the result of ``prewarm``. ``progress`` receives ``("Analyzing images", done,
    total)`` as images are analyzed here (total is the pack's image count); a cancel raises
    ``archive.Cancelled`` before the next image.
    """
    hashes = {f.path: f.sha256 for f in inv.files}
    total = sum(1 for f in inv.files if f.kind == "image")
    ctl = Control(progress, is_cancelled)
    memo: dict[str, dict[str, Any]] = dict(prewarmed or {})

    def analyze(rel: str) -> dict[str, Any]:
        if rel not in memo:
            ctl.check()
            memo[rel] = analyze_file(root / rel, hashes[rel], use_cache=use_cache)
            ctl.report("Analyzing images", min(len(memo), total), total)
        return memo[rel]

    return analyze
