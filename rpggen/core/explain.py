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


def _named(asset_id: str) -> str:
    """ "forest/tree from pack_a" for the id ``pack_a.forest.tree`` (T13.04's duplicate tag)."""
    pack, _, rest = asset_id.partition(".")
    return f"{rest.replace('.', '/')} from {pack}" if rest else asset_id


UNUSED_REASONS = {
    "lpc_in_character": (
        "the body of an LPC character that is put together with its layers; the character is "
        "an asset of its own. Give the body a role to use it bare as well."
    ),
    "lpc_layer": (
        "a layer of an LPC character (hair, clothes, a weapon): it is drawn over a body, "
        "which rpggen does not do yet. Its animations are read; give it a role to use it alone."
    ),
    classifier.UNUSED_COPY: (
        "its name says it is a copy of the file beside it. Give it a role to use it as well."
    ),
    classifier.UNUSED_OTHER_ENGINE: (
        "the same art laid out for another engine; this pack has it for several, and one "
        "is used. Give it a role to use this one as well."
    ),
    classifier.UNUSED_OTHER_LAYOUT: (
        "another layout of an autotile the pack also has as a 47-tile sheet, which is the "
        "one used. Give it a role to use this one as well."
    ),
    "cut_copy": (
        "a copy that another tool cut out of a sheet of this pack; the sheet has it as an "
        "object. Give it a role to use the copy as well."
    ),
    "cut_preview": "a preview picture a sprite-cutting tool made. Give it a role to use it.",
    classifier.UNUSED_PREVIEW_FOLDER: (
        "in a preview folder: a picture of the pack, not a part of it. Give it a role to use it."
    ),
    classifier.UNUSED_GUIDE_PICTURE: (
        "the name says preview, test or layout guide, not game art. Give it a role to use it."
    ),
}


def unused_reason(eff: dict[str, Any]) -> str:
    """Why rpggen left an asset unused by itself ("" when it did not)."""
    for tag in eff.get("tags") or []:
        if isinstance(tag, str) and tag.startswith(classifier.UNUSED_TAG):
            return UNUSED_REASONS.get(tag[len(classifier.UNUSED_TAG) :], "")
    return ""


def why(asset: catalog_mod.Asset) -> str:
    """One or two lines: the keywords, the shape and the other roles that were considered."""
    eff = catalog_mod.effective(asset)
    role = str(eff.get("role", ""))
    if asset.status == "CONFIRMED" and asset.overrides.get("role"):
        return "You chose this role."
    if role == "NONE" and unused_reason(eff):
        return "unused: " + unused_reason(eff)
    parts: list[str] = []
    folders, names = matched_keywords(asset.path, role)
    if folders:
        parts.append("folder " + ", ".join(folders))
    if names:
        parts.append("name " + ", ".join(names))
    shape = _shape(eff)
    if shape:
        parts.append(shape)
    if asset.detected_by == "learned":
        from rpggen.core import learned_rules

        rules = learned_rules.cached().rules
        times = learned_rules.times_learned(rules, learned_rules.pack_relative(asset.path))
        parts.insert(
            0,
            f"learned from your earlier fixes ({times} times)"
            if times
            else "learned from your earlier fixes",
        )
    elif asset.detected_by and asset.detected_by not in ("inventory", "generic_grid"):
        parts.append(f"read by the {asset.detected_by} reader")
    for tag in eff.get("tags") or []:
        if isinstance(tag, str) and tag.startswith(classifier.VARIANT_TAG):
            parts.append(f"a colour variant of {_named(tag[len(classifier.VARIANT_TAG) :])}")
    if classifier.is_numbered_name(asset.path) and eff.get("usage") == "tiles":
        parts.insert(0, "the file name is only a number: read by its folder's words")
    for written, read in sorted(classifier.folded_typos(asset.path).items()):
        parts.append(f"{written} read as {read}")
    text = "; ".join(parts) if parts else "no strong hint in the name or the picture"
    for tag in eff.get("tags") or []:
        if isinstance(tag, str) and tag.startswith("duplicate_of:"):
            text += ". Looks like " + _named(tag.partition(":")[2])
    alts = [(r, c) for r, c in (eff.get("roles_alt") or []) if r != role][:MAX_ALTERNATIVES]
    if alts:
        text += ". Also considered: " + ", ".join(
            f"{labels.role_label(r)} {round(c * 100)}%" for r, c in alts
        )
    return text
