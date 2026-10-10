"""What a sprite-cutting tool left in a pack (T16.21).

Some packs carry, beside their sheets, the output of a tool that cut the props out of them: a
folder ``_organized_sprites`` with one PNG per prop, preview pictures and a manifest
(``manifest/sprites.json`` or ``sprites.csv``) that says which rectangle of which sheet each
prop is. The manifest is the valuable part: its rectangles become the objects of the sheets,
so the props are placed from the sheets they were drawn on, and the cut copies are not needed.
"""

from __future__ import annotations

import csv
import io
import json
import posixpath
import re
from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

MANIFEST_NAMES = ("sprites.json", "sprites.csv")  # the JSON first: it names the sheet's file
MANIFEST_FOLDER = "manifest"
OUTPUT_PREFIX = "_organized_sprites"
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
UNUSED_CUT_COPY = "cut_copy"
UNUSED_CUT_PREVIEW = "cut_preview"
FOOTPRINT_FRACTION = 0.3
_SHEET_NUMBER = re.compile(r"(\d+)\D*$")
_FIELDS = ("x", "y", "width", "height")


def _is_manifest(path: str) -> bool:
    parts = path.casefold().split("/")
    return (
        len(parts) >= 2
        and parts[-1] in MANIFEST_NAMES
        and (parts[-2] == MANIFEST_FOLDER or any(p.startswith(OUTPUT_PREFIX) for p in parts[:-1]))
    )


def _output_root(manifest: str) -> str:
    """The folder the tool wrote into: the manifest's folder without ``manifest``."""
    folder = posixpath.dirname(manifest)
    return (
        posixpath.dirname(folder)
        if posixpath.basename(folder).casefold() == MANIFEST_FOLDER
        else folder
    )


def _rows(root: Path, manifest: str) -> list[dict[str, Any]]:
    """The manifest's entries as ``{id, source_sheet, source_name, category, x, y, width,
    height}``; ``ValueError`` when it is not such a file."""
    path = root / manifest
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("the manifest is larger than 32 MB")
    text = path.read_text(encoding="utf-8-sig")
    if manifest.casefold().endswith(".json"):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("the manifest is not a list of sprites")
        raw = [{**d, **d["bbox"]} if isinstance(d.get("bbox"), dict) else d for d in data]
    else:
        raw = list(csv.DictReader(io.StringIO(text)))
    rows: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict) or "source_sheet" not in entry:
            raise ValueError("an entry has no source_sheet")
        try:
            rect = {key: int(entry[key]) for key in _FIELDS}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"an entry has no rectangle ({exc})") from exc
        # the path the tool wrote is of the artist's own disk: only the file's name is used
        source_file = str(entry.get("source_file") or "").replace("\\", "/")
        rows.append(
            {
                "id": str(entry.get("id") or f"sprite_{len(rows) + 1}"),
                "source_sheet": str(entry["source_sheet"]),
                "source_name": posixpath.basename(source_file),
                "category": str(entry.get("category") or ""),
                **rect,
            }
        )
    return rows


def _sheet_for(row: dict[str, Any], sheets: list[InventoryFile]) -> InventoryFile | None:
    """The sheet a manifest entry was cut from: by the file name the manifest gives, else by
    the number in ``sheet_05`` (the sheet called ``5.png``, or else the fifth sheet)."""
    if row["source_name"]:
        named = [
            f
            for f in sheets
            if posixpath.basename(f.path).casefold() == row["source_name"].casefold()
        ]
        if named:
            return named[0]
    m = _SHEET_NUMBER.search(row["source_sheet"])
    if m is None:
        return None
    number = int(m.group(1))
    for f in sheets:
        stem = posixpath.splitext(posixpath.basename(f.path))[0].strip()
        if stem.isdigit() and int(stem) == number:
            return f
    return sheets[number - 1] if 0 < number <= len(sheets) else None


def _object(sheet: str, row: dict[str, Any]) -> dict[str, Any]:
    w, h = row["width"], row["height"]
    fh = max(1, round(h * FOOTPRINT_FRACTION))
    fy = h - fh
    return {
        "sheet_path": sheet,
        "name": row["id"],
        "role": "DECORATION",
        "region": [row["x"], row["y"], w, h],
        "origin": [w // 2, h - 1],
        "footprint": [0, fy, w, fh],
        "collision": {"profile": "CUSTOM", "polygon": [[0, fy], [w, fy], [w, h], [0, h]]},
        "tags": [row["category"]] if row["category"] else [],
        "status": "AUTO_DETECTED",
        "source": "auto",
        "authoritative": True,  # the rectangles of the manifest replace the guessed ones
    }


class CutterAdapter:
    name = "cutter"
    priority = 45  # after the readers of whole formats, before frames and strips

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if any(_is_manifest(f.path) for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        outputs: dict[str, str] = {}  # output folder -> its manifest (the JSON before the CSV)
        for name in MANIFEST_NAMES:
            for f in inv.files:
                if _is_manifest(f.path) and posixpath.basename(f.path).casefold() == name:
                    outputs.setdefault(_output_root(f.path), f.path)
        for output in sorted(outputs):
            self._output(inv, root, ctx, output, outputs[output], result, issues)
        result.issues = list(issues)
        return result

    def _output(
        self,
        inv: Inventory,
        root: Path,
        ctx: AdapterContext,
        output: str,
        manifest: str,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        home = posixpath.dirname(output)  # where the sheets are
        inside = output + "/"
        pictures = [f for f in inv.files if f.kind == "image" and f.image is not None]
        sheets = [f for f in pictures if posixpath.dirname(f.path) == home]
        copies = [f for f in pictures if f.path.startswith(inside) and f.path not in ctx.claimed]
        previews = [f for f in copies if "/previews/" in f.path[len(output) :].casefold()]
        problem = ""
        objects: list[dict[str, Any]] = []
        try:
            rows = _rows(root, manifest)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            rows, problem = [], str(exc)
        for row in rows:
            sheet = _sheet_for(row, sheets)
            if sheet is None or sheet.image is None:
                problem = (
                    f"{row['id']} names the sheet {row['source_sheet']}, which is not in the pack"
                )
                break
            right, bottom = row["x"] + row["width"], row["y"] + row["height"]
            fits = row["x"] >= 0 and row["y"] >= 0 and row["width"] > 0 and row["height"] > 0
            if not fits or right > sheet.image["w"] or bottom > sheet.image["h"]:
                problem = (
                    f"the rectangle of {row['id']} is outside {posixpath.basename(sheet.path)}"
                )
                break
            objects.append(_object(sheet.path, row))
        unused = previews
        if problem or not objects:
            # the manifest does not describe these sheets: the cut pictures are what there is
            issues.add("ADAPT-007", file=manifest, reason=problem or "it lists no sprite")
        else:
            result.objects.extend(objects)
            unused = copies
        for f in unused:
            reason = UNUSED_CUT_PREVIEW if f in previews else UNUSED_CUT_COPY
            w, h = (f.image or {}).get("w", 1), (f.image or {}).get("h", 1)
            facets = {
                "usage": "sprite",
                "frame": [w, h],
                "origin": [w // 2, h - 1],
                "role": "NONE",
                "tags": [f"unused_because:{reason}"],
            }
            result.assets.append(AssetFragment(f.path, facets, 0.9, "full"))
