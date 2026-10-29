from __future__ import annotations

import hashlib

import numpy as np
import pytest
from PIL import Image

from rpggen.core import inventory, metadata_reviews
from rpggen.core.adapters import reviewed_crops, sheet_parts


def test_reviewed_crop_rendering_preserves_items_and_uses_padded_source_rectangles(
    monkeypatch, tmp_path
):
    source = np.arange(16 * 24 * 4, dtype=np.uint8).reshape(16, 24, 4)
    record = {
        "variant": "crop8_0",
        "name": "garlic",
        "frame": [8, 16],
        "rects": [[0, 4, 8, 12], [8, 0, 8, 16], [16, 0, 8, 16]],
        "offsets": [[0, 4], [0, 0], [0, 0]],
    }
    monkeypatch.setattr(reviewed_crops, "layouts", lambda: {"a" * 64: [record]})
    f = inventory.InventoryFile("farm.png", "a" * 64, 1, ".png", "image")
    item = sheet_parts._Part("o4_448", source[:2, :2].copy(), {"role": "ITEM"}, 0.5)
    cut = sheet_parts._Cut(
        [item, sheet_parts._Part("old_crop", source, {"usage": "growth_strip"}, 0.6)]
    )
    result = sheet_parts._reviewed_crops(f, source, cut)
    assert result.parts[0] is item and item.facets == {"role": "ITEM"}
    crop = result.parts[1]
    assert crop.variant == "crop8_0" and crop.facets["stages"] == 3
    assert "produce:garlic" in crop.facets["tags"]
    assert not crop.picture[:4, :8].any()
    np.testing.assert_array_equal(crop.picture[4:, :8], source[4:, :8])
    np.testing.assert_array_equal(crop.picture[:, 8:], source[:, 8:])
    # Cached generic/ITEM pictures keep their names; only this reviewed crop changes.
    old = hashlib.sha256(f"sheet_part/1\n{f.sha256}\no4_448".encode()).hexdigest() + ".png"
    assert sheet_parts._render_name(f, "o4_448") == old
    project_name = sheet_parts._render_name(f, "crop8_0")
    key = sheet_parts._cache_render_name(f, "crop8_0")
    Image.new("RGBA", (8, 8), "red").save(tmp_path / project_name)  # stale pre-review cache
    expected_pixels = crop.picture.copy()
    assert not sheet_parts._saved(f, result, tmp_path).error
    with Image.open(tmp_path / key) as actual:
        np.testing.assert_array_equal(np.asarray(actual), expected_pixels)
    with Image.open(tmp_path / project_name) as stale:
        assert stale.size == (8, 8), "the legacy logical name was not reused as the new cache"
    record["rects"][0][1] = 5
    assert sheet_parts._cache_render_name(f, "crop8_0") != key
    assert sheet_parts._render_name(f, "crop8_0") == project_name
    other = inventory.InventoryFile("farm.png", "b" * 64, 1, ".png", "image")
    assert sheet_parts._reviewed_crops(other, source, result) is result
    assert reviewed_crops.layout_key(other.sha256, "crop8_0") == ""


def test_crop_art_contract_excludes_behavior_incomplete_strips_and_other_roles():
    facts = {
        "role": "CROP",
        "usage": "growth_strip",
        "frame": [16, 32],
        "size": [64, 32],
        "stages": 4,
        "origin": [8, 31],
        "grid": {"cell": [16, 32], "margin": [0, 0], "separation": [0, 0]},
        "tags": ["crop", "crop_art", "growth_by:reviewed_sheet", "produce:garlic"],
    }
    assert metadata_reviews.complete(facts, "crop_art")
    for changes in (
        {"role": "ITEM"},
        {"days": 4},
        {"regrow": 2},
        {"stages": True},
        {"size": [48, 32]},
        {"frame": [0, 32]},
        {"tags": []},
        {"animations": {}},
        {"origin": [8, 32]},
        {"collision": {"profile": "NONE"}},
    ):
        assert not metadata_reviews.complete({**facts, **changes}, "crop_art")


def test_packaged_crop_layouts_keep_owner_items_outside_growth_rectangles():
    layouts = reviewed_crops.reviewed(
        "df333ba9f08d137f17715e4b60ac35f9824d3bd0e20677fbf459de8ee791800a"
    )
    assert len(layouts) == 10 and len({r["variant"] for r in layouts}) == 10
    garlic = next(r for r in layouts if r["name"] == "garlic")
    potato = next(r for r in layouts if r["name"] == "potato")
    assert len(garlic["rects"]) == 4 and garlic["variant"] == "crop432_384"
    assert len(potato["rects"]) == 3 and potato["rects"][0][0] == 48
    for layout in layouts:
        for x, y, w, h in layout["rects"]:
            assert not (x < 44 and x + w > 4 and y < 480 and y + h > 448)
            assert not (x < 622 and x + w > 580 and y < 480 and y + h > 410)


def test_invalid_crop_rectangle_is_rejected(monkeypatch):
    layout = {
        "variant": "crop",
        "name": "crop",
        "frame": [8, 8],
        "rects": [[10, 0, 8, 8]],
        "offsets": [[0, 0]],
    }
    monkeypatch.setattr(reviewed_crops, "layouts", lambda: {"x": [layout]})
    f = inventory.InventoryFile("farm.png", "x", 1, ".png", "image")
    with pytest.raises(ValueError, match="outside source"):
        sheet_parts._reviewed_crops(f, np.zeros((8, 8, 4), dtype=np.uint8), sheet_parts._Cut())
