from __future__ import annotations

import json
import posixpath
from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

COLLISION_VALUE_NAMES = {"wall", "solid", "collision"}
MAX_LDTK_BYTES = 32 * 1024 * 1024


def _load(root: Path, rel: str) -> dict[str, Any] | None:
    path = root / rel
    if path.stat().st_size > MAX_LDTK_BYTES:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


class LdtkAdapter:
    name = "ldtk"
    priority = 30

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if any(f.ext == ".ldtk" for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        by_lower = {f.path.casefold(): f.path for f in inv.files}
        for f in inv.files:
            if f.ext != ".ldtk":
                continue
            data = _load(root, f.path)
            if data is None:
                issues.add(
                    "ADAPT-001", adapter=self.name, file=f.path, reason="not a valid LDtk project"
                )
                continue
            defs = data.get("defs", {})
            for ts in defs.get("tilesets", []):
                rel = ts.get("relPath")
                if not rel:
                    continue  # embedded atlas without an image file
                joined = posixpath.normpath(posixpath.join(posixpath.dirname(f.path), str(rel)))
                image = by_lower.get(joined.casefold())
                if image is None:
                    issues.add("ADAPT-002", file=f.path, image=str(rel))
                    continue
                size = int(ts.get("tileGridSize", 0))
                if size <= 0:
                    issues.add(
                        "ADAPT-001", adapter=self.name, file=f.path, reason="invalid tileGridSize"
                    )
                    continue
                spacing, padding = int(ts.get("spacing", 0)), int(ts.get("padding", 0))
                facets = {
                    "usage": "tiles",
                    "grid": {
                        "cell": [size, size],
                        "margin": [padding, padding],
                        "separation": [spacing, spacing],
                    },
                }
                result.assets.append(AssetFragment(image, facets, 1.0, "full"))
            for layer in defs.get("layers", []):
                names = {
                    str(v.get("identifier", "")).casefold() for v in layer.get("intGridValues", [])
                }
                if names & COLLISION_VALUE_NAMES:
                    result.pack_warnings.append("ldtk_intgrid_collision_available")
                    break
        result.issues = list(issues)
        return result
