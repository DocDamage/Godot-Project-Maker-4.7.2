from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import image_facts
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

SHEET_NAME = re.compile(r"^(.*_)?(A[1-5]|B|C|D|E)\.png$", re.IGNORECASE)
SHEET_LETTER = re.compile(r"(?:^|_)(A[1-5]|B|C|D|E)$", re.IGNORECASE)
RTP_NAME = re.compile(
    r"^(?:(?:Actor|People|Monster|Evil|Nature|Damage)\d*"
    r"|(?:Outside|Inside|Dungeon|World)_[A-E][1-5]?)\.png$",
    re.IGNORECASE,
)
DIRECTION_ROWS = ["down", "left", "right", "up"]
WALK_COLUMNS = [1, 0, 1, 2]
TILESET_NAMES = {
    "outside": "overworld",
    "inside": "interior",
    "dungeon": "dungeon",
    "world": "world",
}


def _parent_dir(path: str) -> str:
    return posixpath.basename(posixpath.dirname(path)).casefold()


def _under(path: str, *segments: str) -> bool:
    """True when the folder chain ``segments`` (e.g. "img", "tilesets") appears in the path."""
    parts = [p.casefold() for p in path.split("/")[:-1]]
    n = len(segments)
    return any(parts[i : i + n] == list(segments) for i in range(len(parts) - n + 1))


def _is_image(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext == ".png"


class RpgMakerAdapter:
    name = "rpgmaker"
    priority = 40

    def match(self, inv: Inventory, root: Path) -> float:
        score = 0.0
        images = [f for f in inv.files if _is_image(f)]
        if any(
            _under(f.path, "img", "tilesets") or _under(f.path, "img", "characters") for f in images
        ):
            score += 0.5
        if any(SHEET_NAME.match(posixpath.basename(f.path)) for f in images):
            score += 0.3
        for f in images:
            if _parent_dir(f.path) == "characters" and f.image:
                w, h = f.image["w"], f.image["h"]
                if (w % 576 == 0 and h % 384 == 0) or (w % 384 == 0 and h % 256 == 0):
                    score += 0.2
                    break
        return min(score, 1.0)

    # ------------------------------------------------------------------ extraction

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        tilesets = [f for f in inv.files if _is_image(f) and self._is_tileset(f)]
        characters = [
            f
            for f in inv.files
            if _is_image(f) and _parent_dir(f.path) == "characters" and _under(f.path, "img")
        ]
        faces = [
            f
            for f in inv.files
            if _is_image(f) and _parent_dir(f.path) == "faces" and _under(f.path, "img")
        ]

        tile = self._tile_size(tilesets)
        result.pack_warnings.append(f"rpgmaker_tile_size_{tile}")
        for f in tilesets:
            result.assets.append(self._tileset_fragment(f, tile))
        for f in characters:
            self._character_fragments(root, f, result, issues)
        for f in faces:
            self._face_fragments(root, f, result, issues)

        rtp_seen = False
        for f in tilesets + characters + faces:
            if RTP_NAME.match(posixpath.basename(f.path)):
                issues.add("ASSET-020", file=f.path)
                rtp_seen = True
        if rtp_seen:
            result.pack_warnings.append("rpgmaker_rtp_detected")
        result.issues = list(issues)
        return result

    @staticmethod
    def _is_tileset(f: InventoryFile) -> bool:
        if _parent_dir(f.path) == "tilesets" and _under(f.path, "img"):
            return True
        if _parent_dir(f.path) in ("characters", "faces"):
            return False
        name = posixpath.basename(f.path)
        return (
            bool(SHEET_NAME.match(name))
            and bool(f.image)
            and (f.image["w"] % 48 == 0 or f.image["w"] % 32 == 0)
        )

    @staticmethod
    def _tile_size(tilesets: list[InventoryFile]) -> int:
        widths = [f.image["w"] for f in tilesets if f.image]
        c48 = sum(1 for w in widths if w % 48 == 0)
        c32 = sum(1 for w in widths if w % 32 == 0 and w % 48 != 0)
        return 48 if c48 >= c32 else 32

    def _tileset_fragment(self, f: InventoryFile, tile: int) -> AssetFragment:
        stem = posixpath.splitext(posixpath.basename(f.path))[0]
        letter_match = SHEET_LETTER.search(stem)
        letter = letter_match.group(1).upper() if letter_match else "B"
        facets: dict[str, Any] = {
            "usage": "tiles",
            "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
        }
        prefix = stem.split("_")[0].casefold()
        if prefix in TILESET_NAMES:
            facets["tileset"] = TILESET_NAMES[prefix]
        if letter == "A5":
            facets["role"] = "GROUND"
        elif letter.startswith("A"):
            facets["role"] = "AUTOTILE"
            facets["tags"] = ["rpgmaker_autotile", letter]
        else:
            facets["role"] = "DECORATION"
        return AssetFragment(f.path, facets, 0.95, "full")

    def _character_fragments(
        self, root: Path, f: InventoryFile, result: AdapterResult, issues: IssueList
    ) -> None:
        assert f.image is not None
        w, h = f.image["w"], f.image["h"]
        stem = posixpath.basename(f.path)
        prefix = stem[: len(stem) - len(stem.lstrip("!$"))]
        single = "$" in prefix
        is_object = "!" in prefix
        blocks_x, blocks_y = (1, 1) if single else (4, 2)
        if w % (3 * blocks_x) or h % (4 * blocks_y):
            issues.add(
                "ADAPT-001", adapter=self.name, file=f.path, reason=f"unexpected sheet size {w}x{h}"
            )
            return
        fw, fh = w // (3 * blocks_x), h // (4 * blocks_y)
        mask = image_facts.occupancy(image_facts.load_rgba(root / f.path))
        for i in range(blocks_x * blocks_y):
            bx, by = i % blocks_x, i // blocks_x
            x0, y0 = bx * 3 * fw, by * 4 * fh
            if not mask[y0 : y0 + 4 * fh, x0 : x0 + 3 * fw].any():
                continue
            animations: dict[str, Any] = {}
            for row, direction in enumerate(DIRECTION_ROWS):
                abs_row = by * 4 + row
                animations[f"walk_{direction}"] = {
                    "frames": [[bx * 3 + col, abs_row] for col in WALK_COLUMNS],
                    "fps": 6.0,
                    "loop": True,
                }
                animations[f"idle_{direction}"] = {
                    "frames": [[bx * 3 + 1, abs_row]],
                    "fps": 1.0,
                    "loop": True,
                }
            facets: dict[str, Any] = {
                "usage": "sprite",
                "grid": {"cell": [fw, fh], "margin": [0, 0], "separation": [0, 0]},
                "frame": [fw, fh],
                "origin": [fw // 2, fh - 1],
                "directions": 4,
                "animations": animations,
            }
            role, confidence = self._character_role(stem, i, is_object)
            facets["role"] = role
            if is_object:
                facets["tags"] = ["rpgmaker_object"]
            variant = ""
            if not single:
                facets["character_index"] = i
                variant = f"c{i}"
            result.assets.append(AssetFragment(f.path, facets, confidence, "full", variant))

    @staticmethod
    def _character_role(file_name: str, index: int, is_object: bool) -> tuple[str, float]:
        if is_object:
            return "DECORATION", 0.8
        low = file_name.casefold()
        if "actor" in low:
            return ("PLAYER", 0.9) if index == 0 else ("NPC", 0.85)
        if "people" in low:
            return "NPC", 0.9
        if "monster" in low or "evil" in low:
            return "ENEMY", 0.9
        return "NPC", 0.6

    def _face_fragments(
        self, root: Path, f: InventoryFile, result: AdapterResult, issues: IssueList
    ) -> None:
        assert f.image is not None
        w, h = f.image["w"], f.image["h"]
        if w % 4 or h % 2:
            issues.add(
                "ADAPT-001", adapter=self.name, file=f.path, reason=f"unexpected faces size {w}x{h}"
            )
            return
        bw, bh = w // 4, h // 2
        mask = image_facts.occupancy(image_facts.load_rgba(root / f.path))
        for i in range(8):
            x0, y0 = (i % 4) * bw, (i // 4) * bh
            if not mask[y0 : y0 + bh, x0 : x0 + bw].any():
                continue
            facets = {"usage": "portrait", "role": "PORTRAIT", "region": [x0, y0, bw, bh]}
            result.assets.append(AssetFragment(f.path, facets, 0.95, "full", f"f{i}"))
