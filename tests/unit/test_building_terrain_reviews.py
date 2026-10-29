from __future__ import annotations

import copy
import hashlib

import numpy as np
from PIL import Image

from rpggen import schema
from rpggen.core import inventory, metadata_reviews
from rpggen.core.adapters import reviewed_segments, sheet_parts


def _tile():
    sides = [
        "top_left_corner",
        "top_side",
        "top_right_corner",
        "right_side",
        "bottom_right_corner",
        "bottom_side",
        "bottom_left_corner",
        "left_side",
    ]
    return {
        "usage": "tiles",
        "role": "GROUND",
        "size": [32, 32],
        "grid": {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]},
        "tileset": "floor",
        "tags": ["tiled_atlas"],
        "collision": {"profile": "NONE"},
        "tile_overrides": {
            "0,0": {"terrain": {"set": "Rugs", "terrain": 0, "peering": dict.fromkeys(sides, -1)}}
        },
    }


def test_tiled_confirmation_binds_companion_bytes_and_terrain_context(tmp_path, monkeypatch):
    picture = tmp_path / "floor.png"
    Image.new("RGBA", (32, 32), "red").save(picture)
    companion = tmp_path / "floor.tsx"
    companion.write_text("original")
    facets = _tile()
    context = {
        "terrain_sets": [
            {"name": "Rugs", "mode": "corners", "terrains": [{"name": "red", "color": "#ff0000"}]}
        ]
    }
    record = {
        "kind": "tiled_atlas",
        "input": facets,
        "approved": copy.deepcopy(facets),
        "pixel_sha256": metadata_reviews.pixel_hash(picture),
        "dependencies": [
            {"path": "floor.tsx", "sha256": hashlib.sha256(companion.read_bytes()).hexdigest()}
        ],
        "context": context,
    }
    monkeypatch.setattr(metadata_reviews, "readings", lambda: {"assets": {"sha": {"": record}}})

    def check(root=tmp_path, ctx=context):
        return metadata_reviews.decision("sha", "", facets, picture, root, lambda: ctx)

    assert check() == facets
    assert check(root=None) is None
    assert check(ctx={"terrain_sets": []}) is None
    companion.write_text("changed")
    assert check() is None
    companion.write_text("original")
    record["dependencies"][0]["path"] = "../floor.tsx"
    assert check() is None
    record["dependencies"][0]["path"] = str(companion)
    assert check() is None
    record["dependencies"][0]["path"] = "floor.tsx"
    record["approved"]["tile_overrides"]["0,0"]["terrain"]["peering"]["top_left_corner"] = 3
    assert check() is None
    record["dependencies"] = []
    assert check() is None


def test_tiled_contract_rejects_unsafe_or_out_of_bounds_cell_metadata():
    f = _tile()
    assert metadata_reviews.complete(f, "tiled_atlas")
    for change in (
        {"size": [31, 32]},
        {"role": "WATER"},
        {"tags": []},
        {"collision": {"profile": "FULL"}},
    ):
        assert not metadata_reviews.complete({**f, **change}, "tiled_atlas")
    for key, value in [("2,0", f["tile_overrides"]["0,0"]), ("0,0", {"custom": {"hazard": True}})]:
        assert not metadata_reviews.complete({**f, "tile_overrides": {key: value}}, "tiled_atlas")


def test_building_contract_and_door_schema_include_clear_frontage():
    f = {
        "usage": "object",
        "role": "BUILDING",
        "frame": [80, 100],
        "size": [80, 100],
        "origin": [40, 99],
        "grid": {"cell": [80, 100], "margin": [0, 0], "separation": [0, 0]},
        "tags": ["building_art"],
        "animations": {},
        "door": [52, 86],
        "collision": {"profile": "CUSTOM", "polygon": [[8, 60], [72, 60], [72, 82], [8, 82]]},
    }
    assert metadata_reviews.complete(f, "building_art")
    for changes in (
        {"door": [80, 86]},
        {"door": [52, 81]},
        {"door": [True, 86]},
        {"role": "DECORATION"},
        {"animations": {"open": {}}},
        {"collision": {"profile": "FULL"}},
    ):
        assert not metadata_reviews.complete({**f, **changes}, "building_art")
    # The same field supports explicit clearing through ordinary project overrides.
    from rpggen.core import catalog

    a = catalog.Asset("p.house", "p", "assets/packs/p/house.png", "a" * 64, "image", "CONFIRMED", f)
    a.overrides = {"door": None}
    schema.validate("catalog", catalog.Catalog(assets=[a]).to_json())


def test_reviewed_segmentation_owns_every_pixel_and_preserves_parent_keys(monkeypatch):
    rgba = np.zeros((8, 12, 4), dtype=np.uint8)
    rgba[1:3, 1:4] = [100, 150, 200, 255]
    rgba[5:7, 8:11] = [200, 150, 100, 255]
    layouts = {
        "sha": {
            "group": {
                "children": [
                    {"variant": "group_cat0", "rect": [1, 1, 3, 2]},
                    {"variant": "group_cat1", "rect": [8, 5, 3, 2]},
                ]
            }
        }
    }
    monkeypatch.setattr(reviewed_segments, "layouts", lambda: layouts)
    f = inventory.InventoryFile("cats.png", "sha", 1, ".png", "image")
    parent = sheet_parts._Part("group", rgba, {"role": "ANIMAL"}, 0.5)
    cut = sheet_parts._reviewed_segments(f, sheet_parts._Cut([parent]))
    assert cut.parts[0] is parent and parent.facets["role"] == "NONE"
    assert len(cut.parts) == 3
    assert sum(int((p.picture[..., 3] > 0).sum()) for p in cut.parts[1:]) == 12
    for part in cut.parts[1:]:
        assert metadata_reviews.complete(part.facets, "static_animal")
    name = sheet_parts._render_name(f, "group")
    cache = sheet_parts._cache_render_name(f, "group")
    layouts["sha"]["group"]["children"][0]["rect"][2] = 4
    assert (
        sheet_parts._render_name(f, "group") == name
        and sheet_parts._cache_render_name(f, "group") != cache
    )
