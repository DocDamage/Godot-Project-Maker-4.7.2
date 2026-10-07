from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory
from rpggen.core.terrain import tiled_wang

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
KEYS = {
    "right_side",
    "bottom_right_corner",
    "bottom_side",
    "bottom_left_corner",
    "left_side",
    "top_left_corner",
    "top_side",
    "top_right_corner",
}


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def test_corner_wangid_fills_only_corner_keys() -> None:
    center, peering = tiled_wang.wangid_to_peering([0, 1, 0, 1, 0, 1, 0, 1], "corners")
    assert center == 0
    assert set(peering) == KEYS
    assert [k for k, v in peering.items() if v >= 0] == [
        "bottom_right_corner",
        "bottom_left_corner",
        "top_left_corner",
        "top_right_corner",
    ]


def test_sides_wangid_ignores_corners() -> None:
    center, peering = tiled_wang.wangid_to_peering([2, 1, 2, 1, 2, 1, 2, 1], "sides")
    assert center == 1
    assert peering["top_side"] == peering["right_side"] == 1
    assert peering["top_right_corner"] == -1


def test_wangid_order_is_top_first() -> None:
    # [top, top_right, right, bottom_right, bottom, bottom_left, left, top_left]
    _c, peering = tiled_wang.wangid_to_peering([1, 2, 3, 4, 5, 6, 7, 8], "corners_and_sides")
    assert peering == {
        "right_side": 2,
        "bottom_right_corner": 3,
        "bottom_side": 4,
        "bottom_left_corner": 5,
        "left_side": 6,
        "top_left_corner": 7,
        "top_side": 0,
        "top_right_corner": 1,
    }


def test_center_is_most_frequent_ties_lowest_and_none_is_minus_one() -> None:
    assert tiled_wang.wangid_to_peering([2, 2, 2, 1, 1, 0, 0, 0], "corners_and_sides")[0] == 1
    assert tiled_wang.wangid_to_peering([1, 1, 2, 2, 0, 0, 0, 0], "corners_and_sides")[0] == 0
    center, peering = tiled_wang.wangid_to_peering([0] * 8, "corners")
    assert center == -1 and set(peering.values()) == {-1}
    with pytest.raises(ValueError):
        tiled_wang.wangid_to_peering([0] * 8, "bogus")
    with pytest.raises(ValueError):
        tiled_wang.wangid_to_peering([0] * 7, "corners")


def test_apply_to_tile_overrides_keeps_other_keys() -> None:
    overrides = {
        "0,0": {"terrain": {"set": "w", "wangid": [1, 0, 1, 0, 1, 0, 1, 0]}, "custom": {"a": 1}},
        "1,0": {"collision": {"profile": "FULL"}},
    }
    sets = [{"name": "w", "mode": "sides", "terrains": [{"name": "a", "color": "#fff"}]}]
    out = tiled_wang.apply_to_tile_overrides(overrides, sets)
    assert out["0,0"]["terrain"]["set"] == "w" and out["0,0"]["terrain"]["terrain"] == 0
    assert out["0,0"]["terrain"]["peering"]["top_side"] == 0
    assert out["0,0"]["terrain"]["peering"]["top_right_corner"] == -1
    assert "wangid" not in out["0,0"]["terrain"] and out["0,0"]["custom"] == {"a": 1}
    assert out["1,0"] == overrides["1,0"]
    assert "wangid" in overrides["0,0"]["terrain"]  # input untouched
    assert tiled_wang.apply_to_tile_overrides(out, sets) == out  # idempotent


def test_tiled_meta_pack_gets_peering_in_the_catalog() -> None:
    opened = archive.open_pack(SYNTH / "tiled_meta", set())
    cat, _issues, _gen = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    asset = next(a for a in cat.assets if a.detected.get("tile_overrides"))
    ov = catalog.effective(asset)["tile_overrides"]
    grass, dirt = ov["0,0"]["terrain"], ov["1,0"]["terrain"]
    assert (grass["set"], grass["terrain"]) == ("ground", 0)
    assert (dirt["set"], dirt["terrain"]) == ("ground", 1)
    assert grass["peering"]["top_left_corner"] == 0 and grass["peering"]["top_side"] == -1
    assert dirt["peering"]["bottom_right_corner"] == 1
    assert [t["name"] for t in cat.tilesets[0].terrain_sets] == ["ground"]
