"""Packs that describe themselves in JSON (Gridwright's isometric kits): the tiles and things of
a manifest and the characters of their own JSON, on a small pack drawn in their shape."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, catalog, inventory
from rpggen.core.adapters import gridwright

DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _png(path: Path, size: tuple[int, int], colour: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    img.paste((*colour, 255), (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1]))
    img.save(path)


SPRITES = {
    "floor_grass_01": ("floors", [32, 16], [16, 0], {"height": 0}),
    "block_grass_01": ("blocks", [32, 32], [16, 16], {"height": 16}),
    "path_dirt_05": ("paths", [32, 16], [16, 0], {"height": 0, "corners": 5}),
    "fence_wood_06": ("fences", [32, 32], [16, 16], {"joins": 6}),
    "water_floor_f1": ("liquids", [32, 16], [16, 0], {"height": 0, "frame": 1}),
    "water_floor_f2": ("liquids", [32, 16], [16, 0], {"height": 0, "frame": 2}),
    "ramp_grass_up_ne_low": ("ramps", [32, 32], [16, 16], {"height": [0, 8], "up": "ne"}),
    "tree_oak_large": ("nature", [64, 64], [32, 48], {"shadow": "tree_oak_shadow"}),
    "tree_oak_shadow": ("shadows", [64, 64], [32, 48], {}),
    "cottage_left": ("buildings", [96, 64], [48, 32], {"footprint": [2, 2], "door": "left"}),
}


def _tile_kit(root: Path) -> Path:
    pack = root / "kit" / "Gridwright Isometric Tiles"
    sprites = {}
    for name, (category, size, anchor, more) in SPRITES.items():
        rel = f"PNG/1x/{category}/{name}.png"
        for k in (1, 2):
            _png(pack / rel.replace("/1x/", f"/{k}x/"), (size[0] * k, size[1] * k), (90, 160, 60))
        sprites[name] = {"file": rel, "size": size, "footprint": [1, 1], "anchor": anchor, **more}
    _png(pack / "Sheets" / "floors_1x.png", (64, 16), (90, 160, 60))
    manifest = {"pack": "Gridwright Isometric Tiles", "grid": "ground diamond 32 x 16 px",
                "sprites": sprites}  # fmt: skip
    (pack / "isometric.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pack / "LICENSE.txt").write_text("Use it in your games.", encoding="utf-8")
    return root / "kit"


def _characters(root: Path) -> Path:
    pack = root / "chars" / "Gridwright Isometric Characters"
    for name, side in (("knight", "hero"), ("goblin", "enemy")):
        folder = pack / "Sheets" / "1x" / name
        anims = {}
        for action, frames in (("idle", 4), ("walk", 8)):
            _png(folder / f"{name}_{action}.png", (64 * frames, 64 * 8), (200, 60, 60))
            anims[action] = {"image": f"{name}_{action}.png", "frames": frames, "fps": 6,
                             "loop": True}  # fmt: skip
        data = {"character": name, "side": side, "cell": [64, 64], "anchor": [32, 46],
                "rows": DIRECTIONS, "animations": anims}  # fmt: skip
        (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
        for d in DIRECTIONS:
            _png(
                pack / "PNG" / "1x" / name / "idle" / f"{name}_idle_{d}_01.png",
                (64, 64),
                (200, 60, 60),
            )
    _png(pack / "Effects" / "1x" / "shadow.png", (32, 16), (0, 0, 0))
    (pack / "LICENSE.txt").write_text("Use it in your games.", encoding="utf-8")
    return root / "chars"


def _catalog(source: Path) -> catalog.Catalog:
    opened = archive.open_pack(source, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _eff(cat: catalog.Catalog, ending: str) -> dict:
    found = [a for a in cat.assets if a.path.endswith(ending)]
    assert len(found) == 1, (ending, [a.path for a in cat.assets])
    return catalog.effective(found[0])


def _unused(eff: dict) -> str:
    return next((t for t in eff.get("tags", []) if t.startswith("unused_because:")), "")


def test_the_origin_is_the_middle_of_the_cell_nearest_the_camera() -> None:
    assert gridwright.origin_of((16, 16), (1, 1), (32, 16)) == [16, 24]  # a block
    assert gridwright.origin_of((16, 0), (1, 1), (32, 16)) == [16, 8]  # a floor
    assert gridwright.origin_of((48, 32), (2, 2), (32, 16)) == [48, 56]  # a cottage
    assert gridwright.origin_of((32, 16), (2, 1), (32, 16)) == [48, 32]  # a stall along col
    assert gridwright.joins_of(6) == ["e", "s"]  # SE and SW


def test_a_tile_kit_is_read_by_its_manifest(tmp_path: Path) -> None:
    cat = _catalog(_tile_kit(tmp_path))
    assert "isometric:32x16:manifest" in cat.packs[0].warnings
    floor = _eff(cat, "1x/floors/floor_grass_01.png")
    assert floor["usage"] == "iso_tile" and floor["role"] == "GROUND"
    assert floor["footprint"] == [32, 16] and floor["origin"] == [16, 8] and floor["rise"] == 0
    block = _eff(cat, "1x/blocks/block_grass_01.png")
    assert block["usage"] == "iso_tile" and block["role"] == "DECORATION" and block["rise"] == 16
    assert _eff(cat, "1x/paths/path_dirt_05.png")["role"] == "ROAD"
    fence = _eff(cat, "1x/fences/fence_wood_06.png")
    assert fence["role"] == "WALL" and fence["joins"] == ["e", "s"]
    assert _eff(cat, "1x/liquids/water_floor_f1.png")["role"] == "WATER"
    tree = _eff(cat, "1x/nature/tree_oak_large.png")
    assert tree["usage"] == "sprite" and tree["stands_on"] == [1, 1] and tree["origin"] == [32, 56]
    house = _eff(cat, "1x/buildings/cottage_left.png")
    assert house["stands_on"] == [2, 2] and house["origin"] == [48, 56]
    # set aside: a later frame, a ramp, a shadow, the other size and the sheet
    assert _unused(_eff(cat, "1x/liquids/water_floor_f2.png")).endswith("animation_frame")
    assert _unused(_eff(cat, "1x/ramps/ramp_grass_up_ne_low.png")).endswith("ramp")
    assert _unused(_eff(cat, "1x/shadows/tree_oak_shadow.png")).endswith("shadow")
    assert _unused(_eff(cat, "2x/floors/floor_grass_01.png")).endswith("other_size")
    assert _unused(_eff(cat, "Sheets/floors_1x.png")).endswith("atlas_copy")


def test_a_character_is_read_by_its_own_json(tmp_path: Path) -> None:
    cat = _catalog(_characters(tmp_path))
    knight = _eff(cat, "knight/knight_idle.png")
    assert knight["role"] == "PLAYER" and knight["directions"] == 8
    assert knight["frame"] == [64, 64] and knight["origin"] == [32, 46]
    assert len(knight["animations"]) == 16  # two animations in eight directions
    assert knight["animations"]["idle_down"]["frames"][0] == [0, 0]
    assert knight["animations"]["idle_up_left"]["frames"][0] == [0, 3]  # nw is the fourth row
    walk = knight["animations"]["walk_right"]
    assert len(walk["frames"]) == 8 and walk["source"].endswith("knight/knight_walk.png")
    assert "source" not in knight["animations"]["idle_down"]  # its own picture
    assert _eff(cat, "goblin/goblin_idle.png")["role"] == "ENEMY"
    assert _unused(_eff(cat, "knight/knight_walk.png")).endswith("animation_sheet")
    assert _unused(_eff(cat, "idle/knight_idle_s_01.png")).endswith("sheet_frame")
    assert _unused(_eff(cat, "Effects/1x/shadow.png")).endswith("shadow")
