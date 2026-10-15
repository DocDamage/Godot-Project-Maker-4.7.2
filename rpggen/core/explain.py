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
    "atlas_copy": (
        "a sheet the pack's pictures are packed into; the pack has them as single pictures "
        "too, and those are used. Give it a role to use the sheet as well."
    ),
    "other_view": (
        "the same model seen from another angle; the pack has it in a folder Isometric too, "
        "and that one is used. Give it a role to use this one as well."
    ),
    "slope": (
        "a heading of a vehicle on a slope going up or down; a game drives on the flat ones. "
        "Give it a role to use it."
    ),
    "layered_piece": (
        "a piece of the pack's character (a body, eyes, hair, clothes or an accessory): the "
        "character is put together from its pieces and is an asset of its own; this piece is "
        "one of its choices. Give it a role to use it alone."
    ),
    "engine_copy": (
        "in a folder of RPG Maker beside the pack's own pictures: the same art laid out for "
        "another engine at its own size. Give it a role to use it as well."
    ),
    "aseprite_copy": (
        "the pack's pictures once more as its Aseprite files export them, beside a folder PNG "
        "that is used. Give it a role to use it as well."
    ),
    "many_buildings": (
        "a picture of several buildings side by side, too large to be one house of the "
        "village. Give it a role to use it whole, or cut it into objects."
    ),
    "character_sheet": (
        "a sheet of a character or an animal (or the guide to its rows) that rpggen could not "
        "read as one; it is no ground. Give it a role to use it."
    ),
    "portrait_piece": (
        "a piece of a portrait drawn in layers (its eyes, its hair): rpggen does not put a "
        "portrait together. Give it a role to use it alone."
    ),
    "same_tiles": (
        "the same tiles as another picture of this pack (a sheet with spacing, a packed sheet "
        "or single files of one set); one form is used. Give it a role to use this one as well."
    ),
    "compiled_sheet": (
        "a sheet of pictures this pack also has a file each; those are used. Give it a role "
        "to use the sheet as well."
    ),
    "other_size": (
        "the pack is drawn in several sizes and another size is used (the pack's card says "
        "which and lets you choose). Give it a role to use it as well."
    ),
    "preview_gif": (
        "an animated GIF that shows a sheet the pack also has as a PNG; the sheet is used. "
        "Give it a role to use the GIF as well."
    ),
    classifier.UNUSED_PREVIEW_FOLDER: (
        "in a preview folder: a picture of the pack, not a part of it. Give it a role to use it."
    ),
    classifier.UNUSED_GUIDE_PICTURE: (
        "the name says preview, test or layout guide, not game art. Give it a role to use it."
    ),
}


def unused_reason(eff: dict[str, Any]) -> str:
    """Why rpggen left an asset unused by itself ("" when it did not)."""
    tags = [t for t in eff.get("tags") or [] if isinstance(t, str)]
    for tag in tags:
        if tag == classifier.UNUSED_TAG + classifier.UNUSED_USE_ANIM:
            return _use_anim_reason(tags)
        if tag.startswith(classifier.UNUSED_TAG):
            return UNUSED_REASONS.get(tag[len(classifier.UNUSED_TAG) :], "")
    return ""


def _use_anim_reason(tags: list[str]) -> str:
    """A character using a tool (T17.10): whose animation it is, and of which tool."""

    def said(prefix: str) -> str:
        return next((t[len(prefix) :] for t in tags if t.startswith(prefix)), "")

    owner, tool = said(classifier.USE_ANIM_OF_TAG), said(classifier.USE_ANIM_TAG)
    whose = _named(owner) if owner else "a character of this pack"
    return (
        f"an animation of {whose} using a tool ({tool}), not a character of its own. rpggen "
        "does not put it on that character yet. Give it a role to use it alone."
    )


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
    if "roof_half_cell" in (eff.get("tags") or []):
        # T17.33: why a house of these pieces has a roof drawn in their colours
        parts.append(
            "a roof piece over half a cell: laid a cell each it makes no one roof, so a house's "
            "roof is drawn in its colours"
        )
    for tag in eff.get("tags") or []:
        if isinstance(tag, str) and tag.startswith(classifier.VARIANT_TAG):
            other = _named(tag[len(classifier.VARIANT_TAG) :])
            coloured = any(str(t).startswith(classifier.COLOUR_TAG) for t in eff.get("tags") or [])
            seasonal = any(str(t).startswith(classifier.SEASON_TAG) for t in eff.get("tags") or [])
            turned = any(str(t).startswith(catalog_mod.TURN_TAG) for t in eff.get("tags") or [])
            if turned and not coloured:
                parts.append(f"{other} turned")
            elif seasonal and not coloured:
                parts.append(f"{other} drawn for another season")
            else:
                parts.append(f"a colour variant of {other}")
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
