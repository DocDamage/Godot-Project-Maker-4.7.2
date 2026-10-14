"""A pack drawn for the tests of T17.28 (imported maps in the isometric view), in the manner of
Kenney's *Isometric Miniature* packs: the pack is a zip in its folder beside a preview, with one
picture a tile (``Isometric/<name>_<N|E|S|W>.png``) and, in ``Samples/``, a zip with a Tiled
sample: two isometric maps (``Sample.tmx``, ``Cellar.tmx``) on an external tile set that is a
collection of images (``Sample.tsx``) whose pictures lie in the sample's ``Sprites/`` folder.

The pictures are drawn here with the helpers of ``tools/make_synthetic_packs.py``; nothing is
written into the repository. ``draw(folder)`` returns the pack's folder.

What the sample holds, cell by cell (x east, y south, Tiled's columns and rows):

* ``Sample`` (8 x 8, diamonds of 64 x 32): the ``Floor`` is wood but for the stone of row 7;
  the ``Walls`` layer has a wall along row 0 and column 0 and a crate on (5, 5); a layer
  ``Upper`` drawn 16 px higher has one stone tile on (6, 2); objects: a spawn on (3, 4), a sign
  ``notice`` on (5, 2) and a door ``to_cellar`` on (6, 6) to the map ``Cellar``, spawn
  ``from_sample``.
* ``Cellar`` (4 x 4): stone; a spawn ``from_sample`` on (1, 1) and a door ``back`` on (3, 3) to
  the map ``Sample``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
CANVAS = (64, 96)
FOOT = (64, 32)
SIDE = 6
COMPASS = ("N", "E", "S", "W")
SAMPLE_SIZE = (8, 8)
CELLAR_SIZE = (4, 4)
# the tile ids of Sample.tsx and the pictures they show
TILES = {0: "floorWood_E", 1: "wall_E", 2: "crate_E", 3: "floorStone_E"}
WALL_CELLS = [(x, 0) for x in range(8)] + [(0, y) for y in range(1, 8)]
CRATE = (5, 5)
UPPER = (6, 2)
UPPER_OFFSET = -16
SPAWN = (3, 4)
SIGN = (5, 2)
DOOR = (6, 6)
CELLAR_SPAWN = (1, 1)
CELLAR_DOOR = (3, 3)
PACK_ZIP = "Isometric Miniature Tiled (1.0).zip"
SAMPLE_ZIP = "Samples/Tiled Sample.zip"


def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_synthetic_packs", REPO / "tools" / "make_synthetic_packs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _crate() -> Image.Image:
    """A box on the middle of a diamond, smaller than it: an object, not a tile."""
    img = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, foot_y = CANVAS[0] // 2, CANVAS[1] - SIDE - FOOT[1] // 2
    draw.rectangle([cx - 9, foot_y - 16, cx + 8, foot_y + 2], fill=(150, 104, 58, 255))
    draw.rectangle([cx - 9, foot_y - 16, cx + 8, foot_y - 12], fill=(190, 140, 84, 255))
    return img


def _object(x: int, y: int, name: str, kind: str, props: str = "") -> str:
    """A point object in the middle of the cell (x, y): Tiled counts both axes of an isometric
    map in the height of a diamond."""
    unit = FOOT[1]
    inner = f"<properties>{props}</properties>" if props else ""
    return (
        f' <object id="{x * 10 + y}" name="{name}" type="{kind}" '
        f'x="{(x + 0.5) * unit}" y="{(y + 0.5) * unit}"><point/>{inner}</object>\n'
    )


def _csv(width: int, height: int, cells: dict[tuple[int, int], int]) -> str:
    rows = []
    for y in range(height):
        rows.append(",".join(str(cells.get((x, y), 0)) for x in range(width)))
    return ",\n".join(rows)


def sample_tmx() -> str:
    w, h = SAMPLE_SIZE
    floor = {(x, y): (4 if y == h - 1 else 1) for y in range(h) for x in range(w)}
    walls = dict.fromkeys(WALL_CELLS, 2)
    walls[CRATE] = 3
    upper = {UPPER: 4}
    door_props = (
        '<property name="target_map" value="cellar"/>'
        '<property name="target_spawn" value="from_sample"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<map version="1.2" orientation="isometric" renderorder="right-down" width="{w}" '
        f'height="{h}" tilewidth="{FOOT[0]}" tileheight="{FOOT[1]}" infinite="0">\n'
        ' <tileset firstgid="1" source="Sample.tsx"/>\n'
        f' <layer id="1" name="Upper" width="{w}" height="{h}" offsetx="0" offsety="{UPPER_OFFSET}">\n'
        f'  <data encoding="csv">\n{_csv(w, h, upper)}\n</data>\n </layer>\n'
        f' <layer id="2" name="Floor" width="{w}" height="{h}">\n'
        f'  <data encoding="csv">\n{_csv(w, h, floor)}\n</data>\n </layer>\n'
        f' <layer id="3" name="Walls" width="{w}" height="{h}">\n'
        f'  <data encoding="csv">\n{_csv(w, h, walls)}\n</data>\n </layer>\n'
        ' <objectgroup id="4" name="Objects">\n'
        + _object(*SPAWN, "start", "spawn")
        + _object(*SIGN, "notice", "sign", '<property name="text" value="A cellar below."/>')
        + _object(*DOOR, "to_cellar", "door", door_props)
        + " </objectgroup>\n</map>\n"
    )


def cellar_tmx() -> str:
    w, h = CELLAR_SIZE
    floor = {(x, y): 4 for y in range(h) for x in range(w)}
    door_props = '<property name="target_map" value="sample"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<map version="1.2" orientation="isometric" renderorder="right-down" width="{w}" '
        f'height="{h}" tilewidth="{FOOT[0]}" tileheight="{FOOT[1]}" infinite="0">\n'
        ' <tileset firstgid="1" source="Sample.tsx"/>\n'
        f' <layer id="1" name="Floor" width="{w}" height="{h}">\n'
        f'  <data encoding="csv">\n{_csv(w, h, floor)}\n</data>\n </layer>\n'
        ' <objectgroup id="2" name="Objects">\n'
        + _object(*CELLAR_SPAWN, "from_sample", "spawn")
        + _object(*CELLAR_DOOR, "back", "door", door_props)
        + " </objectgroup>\n</map>\n"
    )


def sample_tsx() -> str:
    tiles = "".join(
        f' <tile id="{tid}">\n  <image width="{CANVAS[0]}" height="{CANVAS[1]}" '
        f'source="Sprites/{name}.png"/>\n </tile>\n'
        for tid, name in TILES.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tileset version="1.2" name="Sample" tilewidth="{CANVAS[0]}" '
        f'tileheight="{CANVAS[1]}" tilecount="{len(TILES)}" columns="0">\n'
        ' <grid orientation="orthogonal" width="1" height="1"/>\n' + tiles + "</tileset>\n"
    )


def draw(folder: Path) -> Path:
    """Draws the pack into ``folder`` (a new folder ``iso_tiled`` in it) and returns it."""
    mod = tool()
    block = mod._iso_block
    wood, stone = (176, 132, 84, 255), (150, 150, 158, 255)
    entries: list[tuple[str, bytes]] = []
    for turn, letter in enumerate(COMPASS):
        things = {
            "floorWood": block(CANVAS, FOOT, SIDE, wood, turn=turn),
            "floorStone": block(CANVAS, FOOT, SIDE, stone, turn=turn),
            "dirt": block(CANVAS, FOOT, SIDE, (128, 92, 60, 255), turn=turn),
            "grass": block(CANVAS, FOOT, SIDE, (92, 150, 70, 255), turn=turn),
        }
        for name, img in things.items():
            entries.append((f"Isometric/{name}_{letter}.png", mod._png_bytes(img)))
    sprites = {
        "floorWood_E": block(CANVAS, FOOT, SIDE, wood, turn=1),
        "floorStone_E": block(CANVAS, FOOT, SIDE, stone, turn=1),
        "wall_E": block(CANVAS, FOOT, SIDE + 30, (120, 120, 132, 255), turn=1),
        "crate_E": _crate(),
    }
    sample: list[tuple[str, bytes]] = [
        ("Cellar.tmx", cellar_tmx().encode("utf-8")),
        ("Sample.tmx", sample_tmx().encode("utf-8")),
        ("Sample.tsx", sample_tsx().encode("utf-8")),
    ]
    sample += [(f"Sprites/{name}.png", mod._png_bytes(img)) for name, img in sprites.items()]
    sample.sort(key=lambda e: e[0])
    staging = folder / "_sample_staging"
    mod._write_zip(staging / "sample.zip", sample)
    entries.append((SAMPLE_ZIP, (staging / "sample.zip").read_bytes()))
    preview = Image.new("RGBA", (96, 54), (58, 58, 58, 255))
    preview.alpha_composite(block((64, 44), FOOT, SIDE, wood), (16, 6))
    entries.append(("Preview.png", mod._png_bytes(preview)))
    entries.append(("License.txt", b"CC0-1.0 synthetic test pack\n"))
    entries.sort(key=lambda e: e[0])
    pack = folder / "iso_tiled"
    mod._write_zip(pack / PACK_ZIP, entries)
    mod._save_png(preview, pack / "Preview.png")
    (staging / "sample.zip").unlink()
    staging.rmdir()
    return pack
