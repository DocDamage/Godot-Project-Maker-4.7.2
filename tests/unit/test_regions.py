from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from rpggen.core.analyzer import grid, image_facts, regions

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
G16 = grid.GridCandidate((16, 16), (0, 0), (0, 0), 1.0, 0, 0)


def _mask(rel: str) -> np.ndarray:
    return image_facts.occupancy(image_facts.load_rgba(SYNTH / rel))


def test_objects_in_sheet_has_house_and_tree() -> None:
    expected = json.loads((SYNTH / "objects_in_sheet.expected.json").read_text(encoding="utf-8"))
    want = [tuple(r) for r in expected["town.png"]["regions"]]
    got = regions.detect_regions(_mask("objects_in_sheet/town.png"), G16)
    assert got == sorted(want, key=lambda r: (r[1], r[0]))
    assert len(got) == 2


def test_regions_are_sorted_by_y_then_x() -> None:
    got = regions.detect_regions(_mask("objects_in_sheet/town.png"), G16)
    assert got == sorted(got, key=lambda r: (r[1], r[0]))


def test_terrain_sheet_has_no_regions() -> None:
    assert regions.detect_regions(_mask("basic16/tiles/terrain.png"), G16) == []
    assert regions.detect_regions(_mask("mixed/tiles/ground16.png"), G16) == []


def test_min_cells_and_single_tiles() -> None:
    m = np.zeros((32, 32), dtype=bool)
    m[2:14, 2:14] = True  # one 12x12 object inside one cell
    assert regions.detect_regions(m, G16) == []


def test_two_cell_object_is_found_and_tightened() -> None:
    m = np.zeros((48, 48), dtype=bool)
    m[20:30, 4:28] = True  # 24x10 object crossing the border between two cells
    m[0:3, 40:43] = True  # a lone speck elsewhere keeps the object under the terrain limit
    m[5:8, 33:36] = True
    m[44:47, 2:5] = True
    got = regions.detect_regions(m, G16)
    assert got == [(4, 20, 24, 10)]


def test_art_not_continuing_across_the_border_is_not_joined() -> None:
    m = np.zeros((32, 32), dtype=bool)
    m[4:8, 0:15] = True  # touches only 4/16 rows... but stops one pixel before the border
    m[4:8, 17:32] = True
    assert regions.detect_regions(m, G16) == []


def test_degenerate_grids() -> None:
    assert regions.detect_regions(np.zeros((4, 4), dtype=bool), G16) == []
