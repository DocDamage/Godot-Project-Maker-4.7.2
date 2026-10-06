from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, inventory
from rpggen.core.adapters import AdapterContext
from rpggen.core.adapters.rpgmaker import RpgMakerAdapter

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _run(pack_dir: Path):
    pack = archive.open_pack(pack_dir, set())
    inv = inventory.build_inventory(pack)
    adapter = RpgMakerAdapter()
    return (
        adapter,
        inv,
        pack.root,
        adapter.extract(inv, pack.root, AdapterContext(pack_id=inv.pack_id)),
    )


def _by(res, path: str, variant: str = ""):
    return next(f for f in res.assets if f.path == path and f.variant == variant)


def test_rpgmaker_like_pack() -> None:
    adapter, inv, root, res = _run(SYNTH / "rpgmaker_like")
    assert adapter.match(inv, root) == 1.0
    assert "rpgmaker_tile_size_48" in res.pack_warnings
    a2 = _by(res, "img/tilesets/Outside_A2.png").facets
    assert a2["usage"] == "tiles" and a2["role"] == "AUTOTILE"
    assert a2["tags"] == ["rpgmaker_autotile", "A2"]
    assert a2["grid"] == {"cell": [48, 48], "margin": [0, 0], "separation": [0, 0]}
    assert a2["tileset"] == "overworld"
    b = _by(res, "img/tilesets/Outside_B.png").facets
    assert b["role"] == "DECORATION" and "tags" not in b

    actor = [f for f in res.assets if f.path == "img/characters/Actor1.png"]
    assert [f.variant for f in actor] == [f"c{i}" for i in range(8)]
    c0 = actor[0].facets
    assert c0["role"] == "PLAYER" and c0["character_index"] == 0
    assert c0["frame"] == [48, 48] and c0["origin"] == [24, 47]
    assert c0["animations"]["walk_down"] == {
        "frames": [[1, 0], [0, 0], [1, 0], [2, 0]],
        "fps": 6.0,
        "loop": True,
    }
    assert c0["animations"]["idle_up"]["frames"] == [[1, 3]]
    c5 = actor[5].facets  # block (1, 1): columns 3..5, rows 4..7
    assert c5["role"] == "NPC" and c5["animations"]["walk_left"]["frames"][0] == [4, 5]
    assert all(f.claim == "full" for f in res.assets)

    big = _by(res, "img/characters/$Big.png")
    assert big.variant == "" and "character_index" not in big.facets
    assert big.facets["frame"] == [48, 48] and big.facets["role"] == "NPC"
    assert big.confidence == 0.6

    faces = [f for f in res.assets if f.path == "img/faces/Actor1.png"]
    assert [f.variant for f in faces] == [f"f{i}" for i in range(8)]
    assert faces[0].facets == {"usage": "portrait", "role": "PORTRAIT", "region": [0, 0, 144, 144]}
    assert faces[5].facets["region"] == [144, 144, 144, 144]
    assert faces[0].confidence == 0.95


def test_rtp_names_are_reported_but_never_block() -> None:
    _, _, _, res = _run(SYNTH / "rpgmaker_like")
    flagged = sorted(i.file for i in res.issues if i.code == "ASSET-020")
    assert flagged == [
        "img/characters/Actor1.png",
        "img/faces/Actor1.png",
        "img/tilesets/Outside_A2.png",
        "img/tilesets/Outside_B.png",
    ]
    assert all(i.severity.value == "warning" for i in res.issues)
    assert "rpgmaker_rtp_detected" in res.pack_warnings


def test_non_rpgmaker_packs_do_not_match() -> None:
    for pack in ("basic16", "mixed", "gutter32", "strips"):
        adapter, inv, root, _ = _run(SYNTH / pack)
        assert adapter.match(inv, root) < 0.5, pack


def test_vx_ace_tile_size_and_empty_blocks(tmp_path: Path) -> None:
    pk = tmp_path / "pk" / "img"
    (pk / "tilesets").mkdir(parents=True)
    (pk / "characters").mkdir()
    Image.new("RGBA", (512, 384), (9, 9, 9, 255)).save(pk / "tilesets" / "Custom_A2.png")
    Image.new("RGBA", (256, 512), (9, 9, 9, 255)).save(pk / "tilesets" / "Custom_A5.png")
    sheet = Image.new("RGBA", (384, 256), (0, 0, 0, 0))
    sheet.paste(Image.new("RGBA", (96, 128), (200, 0, 0, 255)), (96, 0))  # only block 1 is used
    sheet.save(pk / "characters" / "!Chest.png")
    _, _, _, res = _run(tmp_path / "pk")
    assert "rpgmaker_tile_size_32" in res.pack_warnings
    assert _by(res, "img/tilesets/Custom_A5.png").facets["role"] == "GROUND"
    assert _by(res, "img/tilesets/Custom_A2.png").facets["grid"]["cell"] == [32, 32]
    chest = [f for f in res.assets if f.path == "img/characters/!Chest.png"]
    assert [f.variant for f in chest] == ["c1"]
    assert chest[0].facets["role"] == "DECORATION" and chest[0].facets["tags"] == [
        "rpgmaker_object"
    ]
    assert chest[0].facets["frame"] == [32, 32]
    assert not any(i.code == "ASSET-020" for i in res.issues)  # custom names are not RTP


def test_odd_character_sheet_size_warns(tmp_path: Path) -> None:
    pk = tmp_path / "pk" / "img" / "characters"
    pk.mkdir(parents=True)
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(pk / "Weird.png")
    _, _, _, res = _run(tmp_path / "pk")
    assert res.assets == []
    assert [i.code for i in res.issues] == ["ADAPT-001"]
