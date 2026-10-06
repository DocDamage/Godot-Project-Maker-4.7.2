from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rpggen.core.analyzer import frames, grid, image_facts

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _load(rel: str) -> tuple[np.ndarray, np.ndarray]:
    a = image_facts.load_rgba(SYNTH / rel)
    return a, image_facts.occupancy(a)


def test_hero_sheet_is_4x4_with_baseline_23() -> None:
    a, m = _load("basic16/characters/hero.png")
    layout = frames.detect_character_sheet(a, m, None)
    assert layout is not None
    assert layout.frame == (16, 24) and layout.cols == 4 and layout.rows == 4
    assert layout.row_directions == ["down", "left", "right", "up"]
    assert layout.direction_confidence <= 0.5
    rects = frames.frame_rects(layout.frame, layout.cols, layout.rows)
    assert len(rects) == 16
    assert frames.baseline_y(m, rects) == 23


def test_sheet_accepts_a_matching_grid_hint() -> None:
    a, m = _load("basic16/characters/hero.png")
    hint = grid.GridCandidate((16, 24), (0, 0), (0, 0), 0.8, 16, 16)
    layout = frames.detect_character_sheet(a, m, hint)
    assert layout is not None and layout.frame == (16, 24)


def test_rpgmaker_actor_sheet() -> None:
    a, m = _load("rpgmaker_like/img/characters/Actor1.png")
    layout = frames.detect_character_sheet(a, m, None)
    assert layout is not None
    assert layout.frame == (48, 48) and layout.cols == 12 and layout.rows == 8
    assert layout.row_directions is None  # only 4-row sheets get direction inference


@pytest.mark.parametrize(
    ("rel", "count"),
    [
        ("strips/hero_walk_down.png", 4),
        ("strips/hero_walk_right.png", 4),
        ("strips/hero_attack_down.png", 3),
        ("strips/slime_idle.png", 4),
    ],
)
def test_strips(rel: str, count: int) -> None:
    _a, m = _load(rel)
    info = frames.detect_strip(m)
    assert info == frames.StripInfo("x", count, (16, 16))


def test_vertical_strip() -> None:
    a, m = _load("strips/slime_idle.png")
    vertical = np.rot90(m)
    info = frames.detect_strip(np.ascontiguousarray(vertical))
    assert info is not None and info.axis == "y" and info.frames == 4


@pytest.mark.parametrize(
    "rel",
    [
        "mixed/tiles/ground16.png",
        "mixed/tiles/ground32.png",
        "mixed/items/item_01.png",
        "basic16/tiles/terrain.png",
        "tiled_meta/tiles.png",
        "gutter32/tiles/world.png",
    ],
)
def test_tile_sheets_and_icons_are_not_strips(rel: str) -> None:
    _a, m = _load(rel)
    assert frames.detect_strip(m) is None


@pytest.mark.parametrize(
    "rel",
    ["mixed/tiles/ground16.png", "lpc_like/characters/body.png", "mixed/items/item_01.png"],
)
def test_non_character_sheets_are_rejected(rel: str) -> None:
    a, m = _load(rel)
    assert frames.detect_character_sheet(a, m, None) is None


def test_frame_bboxes_are_relative() -> None:
    m = np.zeros((10, 20), dtype=bool)
    m[2:5, 3:6] = True
    boxes = frames.frame_bboxes(m, [(0, 0, 10, 10), (10, 0, 10, 10)])
    assert boxes == [(3, 2, 3, 3), None]
    assert frames.baseline_y(m, [(0, 0, 10, 10), (10, 0, 10, 10)]) == 4
    assert frames.baseline_y(np.zeros((4, 4), dtype=bool), [(0, 0, 4, 4)]) == 0


def test_direction_inference_with_a_decisive_mirror_pair() -> None:
    fw, fh = 16, 24
    m = np.zeros((fh * 4, fw * 3), dtype=bool)
    # row 1 and row 3 are mirror images (left/right candidates); rows 0 and 2 differ
    m[0 * fh + 6 : 0 * fh + 12, 4:12] = True  # face area occupied -> "down"
    m[1 * fh + 8 : 1 * fh + 20, 2:6] = True
    m[3 * fh + 8 : 3 * fh + 20, 10:14] = True
    m[2 * fh + 18 : 2 * fh + 22, 4:12] = True  # little art in the face area -> "up"
    for r in range(4):
        for c in range(1, 3):
            m[r * fh : (r + 1) * fh, c * fw : (c + 1) * fw] = m[r * fh : (r + 1) * fh, :fw]
    order, conf = frames._infer_directions(m, (fw, fh), 3)
    assert order[1] == "left" and order[3] == "right"
    assert order[0] == "down" and order[2] == "up"
    assert conf == 0.5
