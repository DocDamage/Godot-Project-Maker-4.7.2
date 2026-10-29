"""Character layouts verified in the real-pack study, before generic object cutting."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen.core import pack_readings
from rpggen.core.adapters import iso_sheets, naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.adapters.rpgmaker import RpgMakerAdapter
from rpggen.core.adapters.strips import StripsAdapter
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

MONSTER_LEGEND = "d964785741f8308696174e1c0eef7f4d30dc14e06a8eeebdf2c622128ed4c2c4"
MONSTER_ROWS = (
    "idle",
    "walk",
    "victory",
    "jump",
    "crouch",
    "attack",
    "hurt",
    "attack_fast",
    "attack_fast_2",
    "levelup",
    "appear",
    "active",
    "death",
    "death_2",
    "teleport",
    "anim_15",
    "power",
    "anim_17",
)
WALK_GIF = re.compile(
    r"(?P<base>.+?)[_-](?P<action>walk|idle|run)(?P<dir>down|up|left|right)[_-]", re.I
)


def sprite(frame: tuple[int, int], animations: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "usage": "sprite",
        "role": role,
        "frame": list(frame),
        "grid": {"cell": list(frame), "margin": [0, 0], "separation": [0, 0]},
        "origin": [frame[0] // 2, frame[1] - 1],
        "animations": animations,
    }


class PackLayoutsAdapter:
    name = "pack_layouts"
    priority = 51  # metadata/standard formats first; before generic island cutting

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        files = [
            f for f in inv.files if f.kind == "image" and f.image and f.path not in ctx.claimed
        ]
        legend = any(f.sha256 == MONSTER_LEGEND for f in inv.files)
        issues = IssueList()
        self._modern(files, ctx, result)
        taken = {f.path for f in result.assets}
        for f in files:
            if f.path in taken:
                continue
            stem = Path(f.path).stem
            w, h = int(f.image["w"]), int(f.image["h"])  # type: ignore[index]
            checked = pack_readings.region_facts(f.sha256, "")
            # A role-only review must leave frame grouping to the normal readers.
            # Claim the image here only when its layout or exclusion is explicit.
            if checked and (
                checked.get("role") == "NONE"
                or checked.get("usage") == "tiles"
                and "grid" in checked
                or "frame" in checked
                and "animations" in checked
                or checked.get("usage") in ("object", "portrait", "ui", "background")
                and "frame" in checked
            ):
                facts = {"usage": "sprite", "frame": [w, h], "size": [w, h]}
                pack_readings.apply_facts(facts, checked)
                result.assets.append(AssetFragment(f.path, facts, 0.5, "full"))
            elif legend and re.fullmatch(r"\d{2}", stem) and (w, h) == (640, 1440):
                with Image.open(root / f.path) as im:
                    mask = np.asarray(im.convert("RGBA"))[..., 3] >= 128
                animations = {}
                for row, action in enumerate(MONSTER_ROWS):
                    frames = [
                        [col, row]
                        for col in range(8)
                        if mask[row * 80 : (row + 1) * 80, col * 80 : (col + 1) * 80].any()
                    ]
                    if frames:
                        animations[f"{action}_down"] = {
                            "frames": frames,
                            "fps": 8.0,
                            "loop": naming.is_looping(action),
                        }
                facts = sprite((80, 80), animations, "ENEMY")
                facts["tags"] = ["view:top"]
                result.assets.append(AssetFragment(f.path, facts, 0.9, "full"))
            elif re.fullmatch(r"rt(?:dragon|goblin|slime|orc|skeleton)\d*", stem, re.I):
                idle = {"idle_down": {"frames": [[0, 0]], "fps": 1.0, "loop": True}}
                result.assets.append(
                    AssetFragment(f.path, sprite((w, h), idle, "ENEMY"), 0.9, "full")
                )
            elif (
                "rpgmaker" in f.path.casefold()
                and stem.casefold().startswith("characters")
                and w % 12 == 0
                and h % 8 == 0
            ):
                RpgMakerAdapter()._character_fragments(root, f, result, issues)
        self._gifs(files, root, ctx, result, issues)
        result.issues = list(issues)
        return result

    @staticmethod
    def _modern(files: list[InventoryFile], ctx: AdapterContext, result: AdapterResult) -> None:
        by_path = {f.path: f for f in files}
        for f in files:
            if (
                not f.path.endswith("_idle_anim_16x16.png")
                or (f.image or {}).get("h") != 32
                or (f.image or {}).get("w") != 384
            ):
                continue
            prefix = f.path.removesuffix("_idle_anim_16x16.png")
            full = by_path.get(prefix + "_16x16.png")
            if (
                full is None
                or (full.image or {}).get("w") != 384
                or (full.image or {}).get("h") != 224
            ):
                continue  # this layout's 7-row combined sheet corroborates the strip
            animations = {}
            for suffix, action in (("_idle_anim_16x16.png", "idle"), ("_run_16x16.png", "walk")):
                source = by_path.get(prefix + suffix)
                if (
                    source is None
                    or (source.image or {}).get("w") != 384
                    or (source.image or {}).get("h") != 32
                ):
                    continue
                for d, direction in enumerate(("right", "up", "left", "down")):
                    animations[f"{action}_{direction}"] = {
                        "frames": [[d * 6 + c, 0] for c in range(6)],
                        "fps": 8.0,
                        "loop": True,
                        "source": f"assets/packs/{ctx.pack_id}/{source.path}",
                    }
                if source.path != f.path:
                    result.assets.append(iso_sheets.aside(source, "animation_source"))
            result.assets.append(
                AssetFragment(f.path, sprite((16, 32), animations, "NPC"), 0.9, "full")
            )
            result.assets.append(iso_sheets.aside(full, "same_frames"))
            # Sitting sprites are wider than standing sprites despite the 16x16 suffix.
            # Keep each optional action's own frame size; do not slice a seated person
            # in half or force a 32px-wide pose into the primary actor's 16px frames.
            for suffix, frame, directions in (
                ("_phone_16x16.png", (16, 32), ("down",)),
                ("_sit_16x16.png", (32, 32), ("right", "left")),
                ("_sit2_16x16.png", (32, 32), ("right", "left")),
                ("_sit3_16x16.png", (16, 32), ("right", "left")),
            ):
                source = by_path.get(prefix + suffix)
                if source is None or (source.image or {}).get("h") != 32:
                    continue
                width = int((source.image or {}).get("w", 0))
                expected = 144 if "phone" in suffix else 192 if "sit3" in suffix else 384
                if width != expected:
                    continue
                count = width // frame[0] // len(directions)
                action = suffix.split("_")[1]
                optional = {
                    f"{action}_{direction}": {
                        "frames": [[i * count + c, 0] for c in range(count)],
                        "fps": 8.0,
                        "loop": True,
                    }
                    for i, direction in enumerate(directions)
                }
                result.assets.append(
                    AssetFragment(source.path, sprite(frame, optional, "NPC"), 0.5, "full")
                )

    @staticmethod
    def _gifs(
        files: list[InventoryFile],
        root: Path,
        ctx: AdapterContext,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        groups: dict[str, list[tuple[InventoryFile, re.Match[str]]]] = {}
        for f in files:
            m = WALK_GIF.match(posixpath.basename(f.path))
            if m and f.ext == ".gif" and (f.image or {}).get("frames", 0) > 1:
                parent = posixpath.dirname(posixpath.dirname(f.path))
                groups.setdefault(parent + "/" + m["base"], []).append((f, m))
        for members in groups.values():
            if len(members) < 2:
                continue
            animations = {}
            for f, m in sorted(members, key=lambda pair: pair[0].path):
                one = AdapterResult("strips")
                StripsAdapter()._gif(root, f, ctx, one, issues)
                if not one.assets:
                    continue
                old = next(iter(one.assets[0].facets["animations"].values()))
                animations[f"{m['action'].lower()}_{m['dir'].lower()}"] = old
                if m["action"].lower() in ("walk", "run"):
                    animations.setdefault(
                        f"idle_{m['dir'].lower()}",
                        {
                            **old,
                            "frames": old["frames"][:1],
                            "fps": 1.0,
                        },
                    )
                result.generated.update(one.generated)
            if not animations:
                continue
            primary = members[0][0]
            frame = (int(primary.image["w"]), int(primary.image["h"]))  # type: ignore[index]
            result.assets.append(
                AssetFragment(primary.path, sprite(frame, animations, "NPC"), 0.9, "full")
            )
            for f, _m in members[1:]:
                result.assets.append(iso_sheets.aside(f, "animation_source"))
            for f in files:
                # The matching per-frame PNGs and tiled export repeat these exact GIFs.
                if f.ext != ".gif" and any(
                    posixpath.basename(f.path).startswith(Path(g.path).stem)
                    or f.path.startswith(
                        str(Path(g.path).with_suffix("")).replace("\\", "/") + "_frames/"
                    )
                    for g, _m in members
                ):
                    result.assets.append(iso_sheets.aside(f, "same_frames"))
