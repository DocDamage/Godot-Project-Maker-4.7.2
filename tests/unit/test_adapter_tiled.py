from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import archive, inventory
from rpggen.core.adapters import AdapterContext
from rpggen.core.adapters.tiled import TiledAdapter, _convex_hull

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _extract(pack_dir: Path):
    pack = archive.open_pack(pack_dir, set())
    inv = inventory.build_inventory(pack)
    adapter = TiledAdapter()
    return (
        adapter,
        inv,
        pack.root,
        adapter.extract(inv, pack.root, AdapterContext(pack_id=inv.pack_id)),
    )


def test_tiled_meta_pack() -> None:
    adapter, inv, root, res = _extract(SYNTH / "tiled_meta")
    assert adapter.match(inv, root) == 1.0
    assert [(f.path, f.claim, f.confidence) for f in res.assets] == [("tiles.png", "full", 1.0)]
    facets = res.assets[0].facets
    assert facets["usage"] == "tiles"
    assert facets["grid"] == {"cell": [16, 16], "margin": [0, 0], "separation": [1, 1]}
    ov = facets["tile_overrides"]
    # tile ids -> coords with 8 columns: 5 -> (5,0), 9 -> (1,1), 17 -> (1,2)
    assert ov["5,0"]["collision"] == {
        "profile": "CUSTOM",
        "polygon": [[0, 8], [16, 8], [16, 16], [0, 16]],
    }
    assert ov["1,1"]["collision"]["polygon"] == [[0, 0], [16, 0], [16, 16]]
    assert ov["1,2"]["collision"]["polygon"] == [[0, 0], [16, 0], [16, 16], [0, 16]]
    assert ov["5,0"]["custom"] == {"footstep": "grass"}
    assert ov["0,0"]["terrain"] == {"set": "ground", "wangid": [0, 1, 0, 1, 0, 1, 0, 1]}
    assert ov["1,0"]["terrain"]["wangid"] == [0, 2, 0, 2, 0, 2, 0, 2]
    assert sum(1 for v in ov.values() if "collision" in v) == 3
    assert res.tilesets == [
        {
            "name": "ground",
            "tile_size": [16, 16],
            "sources": [{"path": "tiles.png"}],
            "terrain_sets": [
                {
                    "name": "ground",
                    "mode": "corners",
                    "terrains": [
                        {"name": "grass", "color": "#00ff00"},
                        {"name": "dirt", "color": "#aa5500"},
                    ],
                }
            ],
        }
    ]
    assert res.pack_warnings == ["tiled_ignored_properties:comment"]
    assert res.issues == []


def _pack(tmp_path: Path, files: dict[str, str | bytes]) -> Path:
    for rel, data in files.items():
        p = tmp_path / "pk" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return tmp_path / "pk"


def _png(tmp_path: Path, w: int = 32, h: int = 16) -> bytes:
    from PIL import Image

    p = tmp_path / "x.png"
    Image.new("RGBA", (w, h), (255, 0, 0, 255)).save(p)
    return p.read_bytes()


def test_missing_image_gives_adapt002(tmp_path: Path) -> None:
    tsx = '<tileset name="t" tilewidth="16" tileheight="16" columns="2"><image source="gone.png" width="32" height="16"/></tileset>'
    _, _, _, res = _extract(_pack(tmp_path, {"t.tsx": tsx}))
    assert res.assets == []
    assert [i.code for i in res.issues] == ["ADAPT-002"]


def test_image_path_is_resolved_relative_to_the_tsx(tmp_path: Path) -> None:
    tsx = '<tileset name="t" tilewidth="16" tileheight="16" columns="2"><image source="../art/t.png" width="32" height="16"/></tileset>'
    pack = _pack(tmp_path, {"sets/t.tsx": tsx, "art/t.png": _png(tmp_path)})
    _, _, _, res = _extract(pack)
    assert [f.path for f in res.assets] == ["art/t.png"]


def test_tsj_json_tileset(tmp_path: Path) -> None:
    tsj = json.dumps(
        {
            "name": "j",
            "tilewidth": 16,
            "tileheight": 16,
            "spacing": 2,
            "margin": 1,
            "columns": 2,
            "image": "t.png",
            "imagewidth": 37,
            "tiles": [
                {
                    "id": 3,
                    "properties": [{"name": "move_cost", "type": "float", "value": 2.5}],
                    "objectgroup": {
                        "objects": [
                            {
                                "x": 2,
                                "y": 2,
                                "polygon": [{"x": 0, "y": 0}, {"x": 8, "y": 0}, {"x": 8, "y": 8}],
                            }
                        ]
                    },
                    "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 200}],
                }
            ],
            "wangsets": [
                {
                    "name": "w",
                    "type": "edge",
                    "colors": [{"name": "a", "color": "#fff"}],
                    "wangtiles": [{"tileid": 2, "wangid": [1, 0, 1, 0, 1, 0, 1, 0]}],
                }
            ],
        }
    )
    pack = _pack(tmp_path, {"j.tsj": tsj, "t.png": _png(tmp_path, 37, 37)})
    adapter, inv, root, res = _extract(pack)
    assert adapter.match(inv, root) == 1.0
    f = res.assets[0].facets
    assert f["grid"] == {"cell": [16, 16], "margin": [1, 1], "separation": [2, 2]}
    ov = f["tile_overrides"]
    assert ov["1,1"]["collision"]["polygon"] == [[2, 2], [10, 2], [10, 10]]
    assert ov["1,1"]["custom"] == {"move_cost": 2.5}
    assert ov["1,1"]["anim"] == {"frames": [[0, 0], [1, 0]], "durations_ms": [100, 200]}
    assert ov["0,1"]["terrain"] == {"set": "w", "wangid": [1, 0, 1, 0, 1, 0, 1, 0]}
    assert res.tilesets[0]["terrain_sets"][0]["mode"] == "sides"


def test_tmx_with_embedded_tileset_matches_at_0_6(tmp_path: Path) -> None:
    tmx = (
        '<map version="1.10" tilewidth="16" tileheight="16" width="2" height="1">'
        '<tileset firstgid="1" name="emb" tilewidth="16" tileheight="16" tilecount="2" columns="2">'
        '<image source="emb.png" width="32" height="16"/></tileset></map>'
    )
    pack = _pack(tmp_path, {"m.tmx": tmx, "emb.png": _png(tmp_path)})
    adapter, inv, root, res = _extract(pack)
    assert adapter.match(inv, root) == 0.6
    assert [f.path for f in res.assets] == ["emb.png"]


def test_tmx_with_only_external_tilesets_does_not_match(tmp_path: Path) -> None:
    tmx = '<map version="1.10"><tileset firstgid="1" source="x.tsx"/></map>'
    adapter, inv, root, _ = _extract(_pack(tmp_path, {"m.tmx": tmx}))
    assert adapter.match(inv, root) == 0.0


def test_multiple_collision_objects_use_the_convex_hull(tmp_path: Path) -> None:
    tsx = (
        '<tileset name="t" tilewidth="16" tileheight="16" columns="2"><image source="t.png" width="32" height="16"/>'
        '<tile id="0"><objectgroup><object x="0" y="0" width="4" height="4"/><object x="12" y="12" width="4" height="4"/></objectgroup></tile></tileset>'
    )
    _, _, _, res = _extract(_pack(tmp_path, {"t.tsx": tsx, "t.png": _png(tmp_path)}))
    poly = res.assets[0].facets["tile_overrides"]["0,0"]["collision"]["polygon"]
    assert [0, 0] in poly and [16, 16] in poly and len(poly) == 6
    assert "tiled_multi_object_collision_hulled" in res.pack_warnings


def test_broken_xml_gives_adapt001(tmp_path: Path) -> None:
    _, _, _, res = _extract(_pack(tmp_path, {"t.tsx": "<tileset"}))
    assert [i.code for i in res.issues] == ["ADAPT-001"]


def test_convex_hull() -> None:
    assert sorted(_convex_hull([[0, 0], [4, 0], [4, 4], [0, 4], [2, 2]])) == [
        [0, 0],
        [0, 4],
        [4, 0],
        [4, 4],
    ]
    assert _convex_hull([[1, 1]]) == [[1, 1]]
