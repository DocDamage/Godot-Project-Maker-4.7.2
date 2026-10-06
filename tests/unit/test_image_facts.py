from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from rpggen.core.analyzer import image_facts as f


def _rgba(w: int, h: int, fill=(0, 0, 0, 0)) -> np.ndarray:
    a = np.zeros((h, w, 4), dtype=np.uint8)
    a[:, :] = fill
    return a


def test_single_opaque_pixel_bbox() -> None:
    a = _rgba(10, 8)
    a[3, 6] = (255, 0, 0, 255)
    mask = f.occupancy(a)
    assert mask.sum() == 1
    assert f.opaque_bbox(mask) == (6, 3, 1, 1)
    assert not f.is_fully_opaque(a)


def test_empty_image_has_no_bbox() -> None:
    mask = f.occupancy(_rgba(4, 4))
    assert f.opaque_bbox(mask) is None
    assert f.dominant_colors(_rgba(4, 4)) == []


def test_semi_transparent_counts_as_occupied() -> None:
    a = _rgba(4, 4)
    a[0, 0] = (1, 2, 3, 1)
    assert f.occupancy(a)[0, 0]


def test_opaque_image_with_uniform_border_excludes_border() -> None:
    a = _rgba(10, 10, (30, 30, 30, 255))
    a[3:7, 3:7] = (200, 10, 10, 255)
    mask = f.occupancy(a)
    assert f.is_fully_opaque(a)
    assert mask.sum() == 16
    assert f.opaque_bbox(mask) == (3, 3, 4, 4)


def test_opaque_background_tolerance() -> None:
    a = _rgba(6, 6, (100, 100, 100, 255))
    a[2, 2] = (108, 100, 100, 255)  # diff 8: still background
    a[3, 3] = (109, 100, 100, 255)  # diff 9: occupied
    mask = f.occupancy(a)
    assert not mask[2, 2] and mask[3, 3]


def test_corner_majority_and_tie_rules() -> None:
    a = _rgba(6, 6, (10, 10, 10, 255))
    a[0, 0] = (200, 0, 0, 255)  # top-left differs; the other three corners agree
    mask = f.occupancy(a)
    assert mask[0, 0] and not mask[5, 5]
    b = _rgba(6, 6, (50, 50, 50, 255))
    b[0, 0] = (250, 0, 0, 255)  # all four corners distinct -> tie -> top-left wins
    b[0, 5] = (0, 250, 0, 255)
    b[5, 0] = (0, 0, 250, 255)
    b[5, 5] = (250, 250, 0, 255)
    mb = f.occupancy(b)
    assert not mb[0, 0] and mb[5, 5] and mb[0, 5] and mb[3, 3]


def test_dominant_colors() -> None:
    a = _rgba(10, 10)
    a[0:5, :] = (255, 0, 0, 255)
    a[5:7, :] = (0, 255, 0, 255)
    a[7:8, :] = (0, 0, 255, 255)
    colors = f.dominant_colors(a, k=3)
    assert colors == ["#fc0404", "#04fc04", "#0404fc"]
    assert len(f.dominant_colors(a, k=2)) == 2


def test_load_rgba(tmp_path: Path) -> None:
    Image.new("RGB", (5, 3), (1, 2, 3)).save(tmp_path / "a.png")
    a = f.load_rgba(tmp_path / "a.png")
    assert a.shape == (3, 5, 4) and a.dtype == np.uint8
    assert tuple(a[0, 0]) == (1, 2, 3, 255)
    frames = []
    for i in range(2):
        fr = Image.new("P", (4, 4), 0)
        fr.putpixel((i, i), 1)
        frames.append(fr)
    frames[0].save(tmp_path / "g.gif", save_all=True, append_images=frames[1:])
    assert f.load_rgba(tmp_path / "g.gif").shape == (4, 4, 4)
