from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Any

from rpggen.core.adapters import naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile

GENERIC_CONSTANTS = {
    "TILES_MIN_SCORE": 0.6,
    "STRIP_CONFIDENCE": 0.7,
    "SHEET_BASE": 0.5,
    "SHEET_GRID_WEIGHT": 0.3,
    "SHEET_INFERRED_CAP": 0.7,  # inferred row directions keep sheets in NEEDS_REVIEW
    "SMALL_SPRITE_MAX": 64,
    "SMALL_SPRITE_CONFIDENCE": 0.6,
    "BACKGROUND_MIN": 256,
    "BACKGROUND_CONFIDENCE": 0.8,
    "FALLBACK_CONFIDENCE": 0.3,
    "BUILDING_MIN_CELLS": 4,  # objects at least 4x4 cells are buildings, others decoration
    "FOOTPRINT_FRACTION": 0.3,
    "NUMBERED_SHEET_CONFIDENCE": 0.6,  # needs review: what stands on the sheet is not known
}
# A numbered sheet (T16.21) has no name to read its grid from. 768 x 768 is the B-E sheet of
# RPG Maker MV and MZ (16 x 16 tiles of 48 px), which a bundle of tile sets is mostly made of.
NUMBERED_SHEET_CELLS = {(768, 768): 48}
NUMBERED_SHEET_FALLBACK = (48, 32, 16)
STANDARD_ACTIONS = {"idle", "walk", "attack", "hurt", "death"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
PHOTO_EXTS = {".jpg", ".jpeg"}  # a format without transparency (T16.21)


def build_pack_prior(results: list[AdapterResult]) -> dict[int, float]:
    """Tile-size prior from the adapters that already ran: counts normalized to 0..1."""
    counts: dict[int, int] = {}
    for res in results:
        for frag in res.assets:
            if frag.facets.get("usage") == "tiles" and "grid" in frag.facets:
                size = int(frag.facets["grid"]["cell"][0])
                counts[size] = counts.get(size, 0) + 1
    if not counts:
        return {}
    top = max(counts.values())
    return {size: n / top for size, n in counts.items()}


def _grid_facet(g: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell": list(g["cell"]),
        "margin": list(g["margin"]),
        "separation": list(g["separation"]),
    }


def _footprint(w: int, h: int) -> list[int]:
    fh = max(1, round(h * GENERIC_CONSTANTS["FOOTPRINT_FRACTION"]))
    return [0, h - fh, w, fh]


class GenericGridAdapter:
    name = "generic_grid"
    priority = 100

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        if ctx.analyze is None:
            return result
        prior = build_pack_prior(ctx.results)
        self._pack_words = ctx.pack_id.replace("_", " ")
        for f in inv.files:
            if (
                f.kind != "image"
                or f.image is None
                or f.ext not in IMAGE_EXTS
                or f.path in ctx.claimed
            ):
                continue
            if f.ext == ".gif" and f.image["frames"] > 1:
                continue
            analysis = ctx.analyze(f.path)
            self._classify_image(f, analysis, prior, result)
        return result

    # ------------------------------------------------------------------ decision tree

    def _classify_image(
        self, f: InventoryFile, a: dict[str, Any], prior: dict[int, float], result: AdapterResult
    ) -> None:
        K = GENERIC_CONSTANTS
        w, h = a["w"], a["h"]
        candidates = a["grid_candidates"]
        top = candidates[0] if candidates else None

        strip = a.get("strip")
        if strip and strip["axis"] == "x":  # 1. single-row strip
            fw, fh = strip["frame"]
            name = naming.normalize_name(posixpath.splitext(posixpath.basename(f.path))[0])
            anim = name.name if name.action in STANDARD_ACTIONS else "idle_down"
            facets: dict[str, Any] = {
                "usage": "sprite",
                "grid": {"cell": [fw, fh], "margin": [0, 0], "separation": [0, 0]},
                "frame": [fw, fh],
                "origin": [fw // 2, a["baseline_y"]],
                "animations": {
                    anim: {
                        "frames": [[i, 0] for i in range(strip["frames"])],
                        "fps": 8.0,
                        "loop": naming.is_looping(anim.split("_")[0]),
                    }
                },
            }
            result.assets.append(AssetFragment(f.path, facets, K["STRIP_CONFIDENCE"], "partial"))
            return

        sheet = a.get("character_sheet")
        if sheet and sheet["rows"] == 4 and sheet["row_directions"]:  # 2. directional sheet
            fw, fh = sheet["frame"]
            animations: dict[str, Any] = {}
            for row, direction in enumerate(sheet["row_directions"]):
                animations[f"walk_{direction}"] = {
                    "frames": [[c, row] for c in range(sheet["cols"])],
                    "fps": 8.0,
                    "loop": True,
                }
                animations[f"idle_{direction}"] = {"frames": [[0, row]], "fps": 1.0, "loop": True}
            grid_conf = a["grid_confidence"] if top and tuple(top["cell"]) == (fw, fh) else 0.5
            confidence = min(
                K["SHEET_BASE"] + K["SHEET_GRID_WEIGHT"] * grid_conf, K["SHEET_INFERRED_CAP"]
            )
            facets = {
                "usage": "sprite",
                "grid": {"cell": [fw, fh], "margin": [0, 0], "separation": [0, 0]},
                "frame": [fw, fh],
                "origin": [fw // 2, a["baseline_y"] if a["baseline_y"] else fh - 1],
                "directions": 4,
                "animations": {k: animations[k] for k in sorted(animations)},
            }
            result.assets.append(AssetFragment(f.path, facets, confidence, "partial"))
            return

        if f.ext in PHOTO_EXTS:  # 2a. no transparency: a background or a preview, never tiles
            big = w >= K["BACKGROUND_MIN"] and h >= K["BACKGROUND_MIN"]
            facets = {"usage": "background"} if big else self._single_frame(w, h)
            confidence = K["BACKGROUND_CONFIDENCE"] if big else K["FALLBACK_CONFIDENCE"]
            result.assets.append(AssetFragment(f.path, facets, confidence, "partial"))
            return

        numbered = self._numbered_sheet(f.path, a)
        if numbered is not None:  # 2b. "3.png" in a folder of tile sheets
            result.assets.append(
                AssetFragment(f.path, numbered, K["NUMBERED_SHEET_CONFIDENCE"], "partial")
            )
            if top and list(top["cell"]) == numbered["grid"]["cell"]:
                result.objects.extend(self._objects(f.path, a))
            return

        if (
            top
            and top["score"] >= K["TILES_MIN_SCORE"]
            and w // top["cell"][0] >= 2
            and h // top["cell"][1] >= 2
        ):
            facets = {"usage": "tiles", "grid": _grid_facet(top)}  # 3. tile sheet
            result.assets.append(AssetFragment(f.path, facets, a["grid_confidence"], "partial"))
            result.objects.extend(self._objects(f.path, a))
            return

        if w <= K["SMALL_SPRITE_MAX"] and h <= K["SMALL_SPRITE_MAX"] and a["has_alpha"]:  # 4.
            result.assets.append(
                AssetFragment(
                    f.path, self._single_frame(w, h), K["SMALL_SPRITE_CONFIDENCE"], "partial"
                )
            )
            return

        if a["fully_opaque"] and w >= K["BACKGROUND_MIN"] and h >= K["BACKGROUND_MIN"]:  # 5.
            result.assets.append(
                AssetFragment(
                    f.path, {"usage": "background"}, K["BACKGROUND_CONFIDENCE"], "partial"
                )
            )
            return

        result.assets.append(  # 6. unknown: a single frame that needs review
            AssetFragment(f.path, self._single_frame(w, h), K["FALLBACK_CONFIDENCE"], "partial")
        )

    def _numbered_sheet(self, path: str, a: dict[str, Any]) -> dict[str, Any] | None:
        """The facets of a sheet named by a number only, in a folder (or a pack) that says it
        holds tile sets: a tile sheet, with the grid of a known sheet size, else the measured
        one, else the largest usual tile that divides it, and the folders' words as tags.
        None for every other picture."""
        from rpggen.core import classifier

        w, h = a["w"], a["h"]
        if not classifier.is_numbered_name(path) or min(w, h) < classifier.SHEET_MIN_SIDE:
            return None
        pack_words = getattr(self, "_pack_words", "")
        words = set(classifier.folder_words(path, pack_words))
        if not words & classifier.TILE_SHEET_WORDS and (w, h) not in NUMBERED_SHEET_CELLS:
            return None
        top = a["grid_candidates"][0] if a["grid_candidates"] else None
        cell = NUMBERED_SHEET_CELLS.get((w, h))
        measured = (
            cell is None
            and top is not None
            and top["score"] >= GENERIC_CONSTANTS["TILES_MIN_SCORE"]
            and list(top["margin"]) == [0, 0]
            and list(top["separation"]) == [0, 0]
            and top["cell"][0] == top["cell"][1]
        )
        if measured and top is not None:
            cell = int(top["cell"][0])
        if cell is None:
            cell = next((c for c in NUMBERED_SHEET_FALLBACK if w % c == 0 and h % c == 0), None)
        if cell is None:
            return None
        facets: dict[str, Any] = {
            "usage": "tiles",
            "grid": {"cell": [cell, cell], "margin": [0, 0], "separation": [0, 0]},
        }
        tags = classifier.folder_tags(path, pack_words)
        if tags:
            facets["tags"] = sorted(tags)
        return facets

    @staticmethod
    def _single_frame(w: int, h: int) -> dict[str, Any]:
        return {"usage": "sprite", "frame": [w, h], "origin": [w // 2, h - 1]}

    def _objects(self, path: str, a: dict[str, Any]) -> list[dict[str, Any]]:
        K = GENERIC_CONSTANTS
        top = a["grid_candidates"][0]
        cw, ch = top["cell"]
        out = []
        for n, (x, y, w, h) in enumerate(a["regions"], start=1):
            big = (w // cw) >= K["BUILDING_MIN_CELLS"] and (h // ch) >= K["BUILDING_MIN_CELLS"]
            fx, fy, fw, fh = _footprint(w, h)
            out.append(
                {
                    "sheet_path": path,
                    "name": f"object_{n}",
                    "role": "BUILDING" if big else "DECORATION",
                    "region": [x, y, w, h],
                    "origin": [w // 2, h - 1],
                    "footprint": [fx, fy, fw, fh],
                    "collision": {
                        "profile": "CUSTOM",
                        "polygon": [[fx, fy], [fx + fw, fy], [fx + fw, fy + fh], [fx, fy + fh]],
                    },
                    "tags": [],
                    "status": "AUTO_DETECTED",
                    "source": "auto",
                }
            )
        return out
