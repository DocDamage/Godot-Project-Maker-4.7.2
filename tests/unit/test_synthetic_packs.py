from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "make_synthetic_packs", REPO / "tools" / "make_synthetic_packs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_two_runs_are_identical(tmp_path: Path) -> None:
    tool = _load_tool()
    a, b = tmp_path / "a", tmp_path / "b"
    assert tool.main(["--out", str(a)]) == 0
    assert tool.main(["--out", str(b)]) == 0
    ha, hb = _hashes(a), _hashes(b)
    assert ha == hb
    assert "basic16/tiles/terrain.png" in ha


def test_committed_pack_matches_generator(tmp_path: Path) -> None:
    tool = _load_tool()
    tool.main(["--out", str(tmp_path)])
    committed = REPO / "test_packs" / "synthetic"
    assert _hashes(tmp_path) == _hashes(committed)


def test_image_sizes_and_pixels(tmp_path: Path) -> None:
    tool = _load_tool()
    tool.main(["--out", str(tmp_path)])
    terrain = Image.open(tmp_path / "basic16" / "tiles" / "terrain.png")
    hero = Image.open(tmp_path / "basic16" / "characters" / "hero.png")
    assert terrain.size == (128, 64)
    assert hero.size == (64, 96)
    assert terrain.mode == "RGBA"
    assert terrain.getpixel((0, 0)) == tool.GROUND_COLORS[0]
    assert terrain.getpixel((16, 16)) == tool.WALL_BORDER
    assert terrain.getpixel((20, 20)) == tool.WALL_FILL
    assert terrain.getpixel((5, 40)) == tool.WATER
    assert terrain.getpixel((20, 40)) == tool.SAND
    assert terrain.getpixel((40, 40))[3] == 0
    # hero: transparent corner, baseline row, row colors, eye shifts per column
    assert hero.getpixel((0, 0))[3] == 0
    assert hero.getpixel((8, 23)) == tool.BLACK
    assert hero.getpixel((8, 6)) == tool.HERO_ROW_COLORS[0]
    assert hero.getpixel((8, 24 + 6)) == tool.HERO_ROW_COLORS[1]
    assert hero.getpixel((5, 9)) == tool.EYE
    assert hero.getpixel((16 + 6, 9)) == tool.EYE
    assert hero.getpixel((16 + 5, 9)) != tool.EYE


def test_nonempty_tile_count(tmp_path: Path) -> None:
    tool = _load_tool()
    tool.main(["--out", str(tmp_path)])
    img = Image.open(tmp_path / "basic16" / "tiles" / "terrain.png")
    nonempty = 0
    for cy in range(4):
        for cx in range(8):
            cell = img.crop((cx * 16, cy * 16, cx * 16 + 16, cy * 16 + 16))
            if cell.getchannel("A").getbbox() is not None:
                nonempty += 1
    assert nonempty == 18


def test_m2_pack_geometry(tmp_path: Path) -> None:
    tool = _load_tool()
    tool.main(["--out", str(tmp_path)])
    sizes = {
        "gutter32/tiles/world.png": (199, 166),
        "gutterless48/Tilesets/ground.png": (240, 144),
        "mixed/backgrounds/sky.png": (512, 288),
        "mixed/tiles/ground32.png": (128, 96),
        "rpgmaker_like/img/tilesets/Outside_A2.png": (768, 576),
        "rpgmaker_like/img/tilesets/Outside_B.png": (768, 768),
        "rpgmaker_like/img/characters/Actor1.png": (576, 384),
        "rpgmaker_like/img/characters/$Big.png": (144, 192),
        "rpgmaker_like/img/faces/Actor1.png": (576, 288),
        "lpc_like/characters/body.png": (832, 1344),
        "tiled_meta/tiles.png": (135, 135),
        "objects_in_sheet/town.png": (160, 128),
    }
    for rel, size in sizes.items():
        with Image.open(tmp_path / rel) as im:
            assert im.size == size, rel
    assert len(list((tmp_path / "mixed" / "items").glob("*.png"))) == 12


def test_weird_names_zip_contents(tmp_path: Path) -> None:
    import zipfile

    tool = _load_tool()
    tool.main(["--out", str(tmp_path)])
    with zipfile.ZipFile(tmp_path / "weird_names.zip") as zf:
        names = zf.namelist()
    assert "\u00c1rbol Grande.png" in names
    assert {"Tree.PNG", "tree.png", "extra.zip", "__MACOSX/._tree.png", ".DS_Store"} <= set(names)
    with zipfile.ZipFile(tmp_path / "zipped.zip") as zf:
        assert "tiles/terrain.png" in zf.namelist()
