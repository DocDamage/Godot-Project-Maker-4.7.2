from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from rpggen.core import catalog as catalog_mod
from rpggen.errors import IssueList

MAGENTA = (255, 0, 255, 255)
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
CHECKER = 4
CHARACTER_ROLES = {"PLAYER", "NPC", "ENEMY"}
DIRECTIONS = ["down", "left", "right", "up"]
PLACEHOLDER_PACK = "debug_placeholders"
PLACEHOLDER_DIR = "generated/debug_placeholders"
MIN_TEXT_WIDTH = 48


def default_size(role: str, base_tile_size: int = 16) -> tuple[int, int]:
    """Frame size for characters (16x24 scaled by tile size), tile size for everything else."""
    if role in CHARACTER_ROLES:
        return (base_tile_size, base_tile_size * 3 // 2)
    return (base_tile_size, base_tile_size)


def _checker(img: Image.Image, box: tuple[int, int, int, int]) -> None:
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            on = ((x - x0) // CHECKER + (y - y0) // CHECKER) % 2 == 0
            d.point((x, y), fill=MAGENTA if on else BLACK)


def _border(img: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    ImageDraw.Draw(img).rectangle([x0, y0, x1 - 1, y1 - 1], outline=WHITE, width=1)


def _outlined_text(img: Image.Image, box: tuple[int, int, int, int], text: str) -> None:
    x0, y0, x1, y1 = box
    if x1 - x0 < MIN_TEXT_WIDTH:
        return  # too small to be readable; the checkerboard alone says "missing"
    d = ImageDraw.Draw(img)
    # The built-in bitmap font is pixel exact; load_default() may return an anti-aliased TTF.
    font = ImageFont.load_default_imagefont()
    left, top, right, bottom = d.multiline_textbbox((0, 0), text, font=font, align="center")
    x = x0 + (x1 - x0 - (right - left)) // 2 - left
    y = y0 + (y1 - y0 - (bottom - top)) // 2 - top
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                d.multiline_text((x + dx, y + dy), text, font=font, fill=BLACK, align="center")
    d.multiline_text((x, y), text, font=font, fill=WHITE, align="center")


def _arrow(img: Image.Image, box: tuple[int, int, int, int], direction: str) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    r = max(3, min(x1 - x0, y1 - y0) // 3)
    tip = {
        "down": [(cx, cy + r), (cx - r, cy - r), (cx + r, cy - r)],
        "up": [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)],
        "left": [(cx - r, cy), (cx + r, cy - r), (cx + r, cy + r)],
        "right": [(cx + r, cy), (cx - r, cy - r), (cx - r, cy + r)],
    }[direction]
    ImageDraw.Draw(img).polygon(tip, fill=WHITE, outline=BLACK)


def make_placeholder(role: str, size: tuple[int, int], out: Path) -> Path:
    """Write a debug placeholder PNG for ``role`` and return its path.

    Characters (PLAYER, NPC, ENEMY): a 4x4 sheet of ``size`` frames (rows down/left/right/up) with
    an arrow per row so movement is visible. GROUND: a strip of four tiles. Everything else: a
    single image of ``size``. All of them carry a magenta/black checkerboard, a white border and,
    when large enough, the text MISSING / ROLE / WxH.
    """
    w, h = size
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if role in CHARACTER_ROLES:
        img = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
        for row, direction in enumerate(DIRECTIONS):
            for col in range(4):
                box = (col * w, row * h, (col + 1) * w, (row + 1) * h)
                _checker(img, box)
                _border(img, box)
                _arrow(img, box, direction)
                _outlined_text(img, box, f"MISSING\n{role}\n{w}x{h}")
    elif role == "GROUND":
        img = Image.new("RGBA", (w * 4, h), (0, 0, 0, 0))
        for col in range(4):
            box = (col * w, 0, (col + 1) * w, h)
            _checker(img, box)
            _border(img, box)
        _outlined_text(img, (0, 0, w * 4, h), f"MISSING {role} {w}x{h}")
    else:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        box = (0, 0, w, h)
        _checker(img, box)
        _border(img, box)
        _outlined_text(img, box, f"MISSING\n{role}\n{w}x{h}")
    img.save(out, format="PNG", optimize=False, pnginfo=None)
    return out


def add_placeholder_assets(
    catalog: catalog_mod.Catalog,
    roles: list[str],
    base_tile_size: int,
    staging_root: Path,
) -> tuple[list[Path], IssueList]:
    """Create placeholder files and catalog assets for the requested roles that are missing.

    Returns the written files and ASSET-011 info issues. Roles that already have an asset are
    skipped. The assets live in the pack ``debug_placeholders`` with the tag ``debug_placeholder``.
    """
    issues = IssueList()
    written: list[Path] = []
    added = False
    for role in sorted(set(roles)):
        if any(
            a.status not in ("UNUSED", "MISSING") and catalog_mod.effective(a).get("role") == role
            for a in catalog.assets
        ):
            continue
        w, h = default_size(role, base_tile_size)
        rel = f"{PLACEHOLDER_DIR}/{role.lower()}.png"
        target = make_placeholder(role, (w, h), staging_root / rel)
        written.append(target)
        facets: dict = {"role": role, "tags": ["debug_placeholder"]}
        if role in CHARACTER_ROLES:
            animations = {}
            for row, direction in enumerate(DIRECTIONS):
                animations[f"walk_{direction}"] = {
                    "frames": [[c, row] for c in range(4)],
                    "fps": 8.0,
                    "loop": True,
                }
                animations[f"idle_{direction}"] = {"frames": [[0, row]], "fps": 1.0, "loop": True}
            facets.update(
                usage="sprite",
                grid={"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
                frame=[w, h],
                origin=[w // 2, h - 1],
                directions=4,
                animations=animations,
            )
        elif role == "GROUND":
            facets.update(
                usage="tiles",
                grid={"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
                collision={"profile": "NONE"},
            )
        else:
            facets.update(usage="sprite", frame=[w, h], origin=[w // 2, h - 1])
        facets["size"] = (
            [w * 4, h * 4]
            if role in CHARACTER_ROLES
            else ([w * 4, h] if role == "GROUND" else [w, h])
        )
        catalog.assets.append(
            catalog_mod.Asset(
                id=f"{PLACEHOLDER_PACK}.{role.lower()}",
                pack_id=PLACEHOLDER_PACK,
                path=rel,
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                kind="image",
                status="CONFIRMED",
                detected=copy.deepcopy(facets),
                detected_by="placeholder",
                confidence=1.0,
            )
        )
        issues.add("ASSET-011", role=role, file=rel)
        added = True
    if added:
        if not any(p.pack_id == PLACEHOLDER_PACK for p in catalog.packs):
            catalog.packs.append(
                catalog_mod.CatalogPack(
                    PLACEHOLDER_PACK, "0" * 64, PLACEHOLDER_DIR, [], [], None, []
                )
            )
        previous = catalog_mod.Catalog.from_json(catalog.to_json())
        catalog_mod.assign_tilesets(catalog, previous)
        catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    return written, issues
