"""A short "why" for a detected asset: what the classifier saw (T11.14).

Pure text from what the catalog already holds (the asset's path and facets) and the classifier's
keyword tables, so the audit page can show it without running the analysis again.
"""

from __future__ import annotations

from typing import Any

from rpggen.core import catalog as catalog_mod
from rpggen.core import classifier, labels

MAX_ALTERNATIVES = 3


def matched_keywords(path: str, role: str) -> tuple[list[str], list[str]]:
    """(folder keywords, file keywords) of the path that vote for ``role``."""
    keywords = classifier.KEYWORD_WEIGHTS.get(role, {})
    folders, stem = classifier.tokens(path)
    return (
        sorted({t for t in folders if t in keywords}),
        sorted({t for t in stem if t in keywords}),
    )


def _shape(eff: dict[str, Any]) -> str:
    anims = eff.get("animations") or {}
    if anims:
        frames = max((len(a.get("frames", [])) for a in anims.values()), default=0)
        rows = len(anims)
        return f"{rows} row{'s' if rows != 1 else ''} of {frames} frame{'s' if frames != 1 else ''}"
    grid = eff.get("grid") or {}
    size = eff.get("size")
    cell = grid.get("cell")
    if cell and size and cell[0] and cell[1]:
        cols, rows = size[0] // cell[0], size[1] // cell[1]
        return f"{cols} x {rows} cells of {cell[0]} x {cell[1]} px"
    return ""


def why(asset: catalog_mod.Asset) -> str:
    """One or two lines: the keywords, the shape and the other roles that were considered."""
    eff = catalog_mod.effective(asset)
    role = str(eff.get("role", ""))
    if asset.status == "CONFIRMED" and asset.overrides.get("role"):
        return "You chose this role."
    parts: list[str] = []
    folders, names = matched_keywords(asset.path, role)
    if folders:
        parts.append("folder " + ", ".join(folders))
    if names:
        parts.append("name " + ", ".join(names))
    shape = _shape(eff)
    if shape:
        parts.append(shape)
    if asset.detected_by and asset.detected_by not in ("inventory", "generic_grid"):
        parts.append(f"read by the {asset.detected_by} reader")
    text = "; ".join(parts) if parts else "no strong hint in the name or the picture"
    alts = [(r, c) for r, c in (eff.get("roles_alt") or []) if r != role][:MAX_ALTERNATIVES]
    if alts:
        text += ". Also considered: " + ", ".join(
            f"{labels.role_label(r)} {round(c * 100)}%" for r, c in alts
        )
    return text
