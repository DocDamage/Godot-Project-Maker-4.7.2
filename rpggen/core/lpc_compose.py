"""LPC characters put together from a body and its layers (M16).

The LPC collection ships a character in parts: a body, and hair, a head, clothes and a weapon
drawn over it, each with the same animations in the same cells. The LPC adapter reads every
part as a sprite of its own. A **character** is a definition in the catalog,
``{id, name, body, layers}``, and this module renders it: the pictures of each animation are
laid over one another in the order of their parts, into one universal sheet, which is an asset
like a sheet a pack ships whole. As with a recolour variant, the definition is what is kept and
the sheet is rendered again on every analysis, so a new version of a pack is followed.

A pack that leaves no choice (one body, at most one layer of every part for it) gets its
character by itself; where there is a choice, somebody makes it in the audit.
"""

from __future__ import annotations

import copy
import hashlib
import io
import re
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen import paths
from rpggen.core.adapters import lpc

CHARACTER_DIR = "generated/lpc_characters"
BODY_TAG = "lpc_body"
LAYER_TAG = "lpc_layer"
PART_TAG = "lpc_part:"
CHARACTER_TAG = "lpc_character"
USED_IN_TAG = "unused_because:lpc_in_character"
# From the back to the front. A part that is not listed goes over the clothes, under the head.
PART_ORDER = (
    "shadow", "cape_behind", "behind", "body", "feet", "legs", "dress", "torso", "arms",
    "shoulders", "neck", "backpack", "quiver", "tail", "wings", "cape", "capes", "head", "heads",
    "ears", "eyes", "facial", "beards", "hair", "hat", "hats", "tools", "weapon", "weapons",
    "shield", "shields",
)  # fmt: skip
UNLISTED = PART_ORDER.index("head") - 0.5
BEHIND_FOLDERS = frozenset({"behind", "background", "bg", "universal_behind"})
# the build of a body a layer is drawn for, as the collection names its folders
BUILDS = frozenset({"male", "female", "teen", "child", "muscular", "pregnant", "adult", "thin"})
_SLUG = re.compile(r"[^a-z0-9]+")


class CharacterError(ValueError):
    """A character's definition cannot be rendered."""


def slug(name: str) -> str:
    return _SLUG.sub("_", name.casefold()).strip("_") or "character"


def new_id(existing: set[str], pack_id: str, name: str) -> str:
    base = f"{pack_id}.lpc_character.{slug(name)}"
    candidate, n = base, 1
    while candidate in existing:
        n += 1
        candidate = f"{base}_{n}"
    return candidate


def path_of(character_id: str) -> str:
    return f"{CHARACTER_DIR}/{character_id.replace('.', '__')}.png"


def cache_dir() -> Path:
    return paths.cache_dir() / "lpc_characters"


def cached_file(sha256: str) -> Path:
    return cache_dir() / f"{sha256}.png"


def normalized(definition: dict[str, Any]) -> dict[str, Any]:
    """The definition with its keys checked and its layers once each, in the order given."""
    try:
        ident, body, name = str(definition["id"]), str(definition["body"]), str(definition["name"])
    except KeyError as exc:
        raise CharacterError(f"it has no {exc.args[0]}") from exc
    if not ident or not body or not name.strip():
        raise CharacterError("its id, its body and its name must not be empty")
    layers: list[str] = []
    for layer in definition.get("layers") or []:
        if str(layer) not in layers and str(layer) != body:
            layers.append(str(layer))
    out: dict[str, Any] = {"id": ident, "name": name.strip(), "body": body, "layers": layers}
    if definition.get("auto"):
        out["auto"] = True
    if definition.get("removed"):  # somebody took it away: it is kept so that it stays away
        out["removed"] = True
    return out


# --------------------------------------------------------------------------- the parts


def _tags(asset: Any) -> list[str]:
    from rpggen.core import catalog as catalog_mod

    return [str(t) for t in catalog_mod.effective(asset).get("tags") or []]


def is_body(asset: Any) -> bool:
    return BODY_TAG in asset.detected.get("tags", [])


def is_layer(asset: Any) -> bool:
    return LAYER_TAG in asset.detected.get("tags", [])


def is_character(asset: Any) -> bool:
    return asset.detected_by == "lpc_compose"


def part_of(asset: Any) -> str:
    """The part a layer is (``hair``), ``body`` for a body."""
    if is_body(asset):
        return "body"
    for tag in asset.detected.get("tags", []):
        if str(tag).startswith(PART_TAG):
            return str(tag)[len(PART_TAG) :]
    return ""


def depth(asset: Any) -> float:
    """Where a part is drawn: a lower number is farther back. A layer in a ``behind`` folder
    (the back of a cape, a weapon held behind the body) goes under the body."""
    folders = set(asset.path.casefold().split("/"))
    if not is_body(asset) and folders & BEHIND_FOLDERS:
        return PART_ORDER.index("behind")
    part = part_of(asset)
    return float(PART_ORDER.index(part)) if part in PART_ORDER else UNLISTED


def build_of(asset: Any) -> str:
    """The build the part is drawn for (``male``, ``adult``), "" when its folders name none."""
    folders = asset.path.casefold().split("/")
    return next((f for f in reversed(folders) if f in BUILDS), "")


def fits(layer: Any, body: Any) -> bool:
    """A layer fits a body of its own build, and one drawn for every build (``adult``, or no
    build in its folders) fits every body."""
    theirs, ours = build_of(layer), build_of(body)
    return theirs in ("", "adult") or not ours or theirs == ours


def bodies(catalog: Any, pack_id: str | None = None) -> list[Any]:
    return [
        a
        for a in catalog.assets
        if is_body(a) and a.status != "MISSING" and pack_id in (None, a.pack_id)
    ]


def layers_for(catalog: Any, body: Any) -> dict[str, list[Any]]:
    """The layers of the body's pack that fit it, by part, each list by id."""
    out: dict[str, list[Any]] = {}
    for asset in catalog.assets:
        mine = is_layer(asset) and asset.pack_id == body.pack_id and asset.status != "MISSING"
        if mine and fits(asset, body):
            behind = depth(asset) < PART_ORDER.index("body")
            out.setdefault(part_of(asset) + ("_behind" if behind else ""), []).append(asset)
    for found in out.values():
        found.sort(key=lambda a: (a.id.casefold(), a.id))
    return dict(sorted(out.items()))


def auto_definitions(catalog: Any) -> list[dict[str, Any]]:
    """The characters a pack leaves no choice about: for a body, every part that has exactly
    one layer that fits it, when that is at least one part. A part with two candidates is left
    out (somebody has to choose), and so is a pack with nothing but a body."""
    found: list[dict[str, Any]] = []
    taken: set[str] = set()
    for body in sorted(bodies(catalog), key=lambda a: (a.id.casefold(), a.id)):
        parts = layers_for(catalog, body)
        chosen = [candidates[0].id for candidates in parts.values() if len(candidates) == 1]
        if not chosen:
            continue
        name = (build_of(body) or "character").capitalize()
        ident = new_id(taken, body.pack_id, name)
        taken.add(ident)
        found.append({"id": ident, "name": name, "body": body.id, "layers": chosen, "auto": True})
    return found


# --------------------------------------------------------------------------- rendering


def _file(asset_path: str, pack_roots: dict[str, Path]) -> Path | None:
    parts = asset_path.split("/", 3)
    if len(parts) != 4 or parts[:2] != ["assets", "packs"]:
        return None
    root = pack_roots.get(parts[2])
    file = Path(root) / parts[3] if root is not None else None
    return file if file is not None and file.is_file() else None


def _strips(asset: Any, pack_roots: dict[str, Path]) -> dict[str, Image.Image]:
    """The picture of every LPC animation an asset has, by the animation's LPC name: a file of
    the collection each, or the rows of a universal sheet."""
    from rpggen.core import catalog as catalog_mod

    animations = catalog_mod.effective(asset).get("animations") or {}
    out: dict[str, Image.Image] = {}
    whole: Image.Image | None = None
    for action in lpc.ACTIONS:
        probe = (
            "hurt"
            if action.lpc == "hurt"
            else f"{action.name}_{'up' if action.rows == 1 else 'down'}"
        )
        spec = animations.get(probe)
        if not isinstance(spec, dict):
            continue
        size = (action.frames * lpc.FRAME, action.rows * lpc.FRAME)
        source = spec.get("source")
        if source:
            file = _file(str(source), pack_roots)
            if file is None:
                continue
            with Image.open(file) as opened:
                picture = opened.convert("RGBA")
            if picture.size == size:
                out[action.lpc] = picture
            continue
        if action.lpc == "idle" and len(spec.get("frames") or []) == 1:
            continue  # a classic sheet stands on its walk: it has no idle rows
        if whole is None:
            file = _file(asset.path, pack_roots)
            if file is None:
                return out
            with Image.open(file) as opened:
                whole = opened.convert("RGBA")
        top = action.row * lpc.FRAME
        if whole.width >= size[0] and whole.height >= top + size[1]:
            out[action.lpc] = whole.crop((0, top, size[0], top + size[1]))
    return out


def render(parts: list[Any], pack_roots: dict[str, Path]) -> Image.Image:
    """One universal sheet of ``parts`` (assets) laid over one another from the back to the
    front. It has the animations the first part of the list that is a body has: a layer that
    lacks one is simply not drawn in it."""
    body = next((p for p in parts if is_body(p)), parts[0] if parts else None)
    if body is None:
        raise CharacterError("it has no body")
    base = _strips(body, pack_roots)
    if not base:
        raise CharacterError("the pictures of its body are not in the packs")
    last = max(lpc.BY_NAME[name].row + lpc.BY_NAME[name].rows for name in base)
    sheet = Image.new("RGBA", (lpc.LPC_WIDTH, last * lpc.FRAME), (0, 0, 0, 0))
    ordered = sorted(parts, key=lambda p: (depth(p), p.id.casefold(), p.id))
    for part in ordered:
        strips = base if part is body else _strips(part, pack_roots)
        for name, picture in strips.items():
            if name in base:
                sheet.alpha_composite(picture, (0, lpc.BY_NAME[name].row * lpc.FRAME))
    return sheet


def build_asset(
    definition: dict[str, Any], catalog: Any, pack_roots: dict[str, Path]
) -> tuple[Any, Path, list[str]]:
    """(the character's asset, its rendered sheet in the cache, the layers that were left out
    because they are not in the catalog any more)."""
    import numpy as np

    from rpggen.core import catalog as catalog_mod
    from rpggen.core.inventory import InventoryFile

    body = catalog.asset(definition["body"])
    if body is None or body.status == "MISSING":
        raise CharacterError(f"its body {definition['body']} is not in the packs any more")
    found = [catalog.asset(layer) for layer in definition["layers"]]
    gone = [layer for layer, a in zip(definition["layers"], found, strict=True) if a is None]
    parts = [body, *(a for a in found if a is not None and a.status != "MISSING")]
    sheet = render(parts, pack_roots)
    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    data = buffer.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    file = cached_file(digest)
    if not file.is_file():
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(file)
    mask = np.asarray(sheet.getchannel("A")) > 0
    info = InventoryFile(path_of(definition["id"]), digest, len(data), ".png", "image",
                         {"w": sheet.width, "h": sheet.height})  # fmt: skip
    facets = copy.deepcopy(lpc.LpcAdapter._fragment(info, mask).facets)
    facets["size"] = [sheet.width, sheet.height]
    role = catalog_mod.effective(body).get("role")
    facets["role"] = role if role and role != "NONE" else "NPC"
    facets["derived_from"] = body.id
    facets["tags"] = [CHARACTER_TAG]
    asset = catalog_mod.Asset(
        id=definition["id"],
        pack_id=body.pack_id,
        path=path_of(definition["id"]),
        sha256=digest,
        kind="image",
        status="CONFIRMED",
        detected=facets,
        detected_by="lpc_compose",
        confidence=1.0,
    )
    return asset, file, gone


def apply(
    catalog: Any,
    definitions: list[dict[str, Any]] | None,
    pack_roots: dict[str, Path],
    issues: Any,
    previous: Any | None = None,
) -> dict[str, str]:
    """Add the asset of every character to ``catalog`` and return ``{project-relative path:
    rendered file}`` for the installer. ``definitions`` are those of the last catalog; None (a
    first analysis) or a list of none but automatic ones lets the packs say which characters
    there are. A character that cannot be rendered gets ``ASSET-033`` and no asset; its
    definition stays. A body that is in a character is left unused by itself, with the reason."""
    from rpggen.core import catalog as catalog_mod

    kept_before = [d for d in definitions or [] if isinstance(d, dict)]
    # where somebody chose, nothing is added behind their back
    chosen = any(not d.get("auto") for d in kept_before)
    raw = kept_before if chosen else auto_definitions(catalog)
    ids = {str(d.get("id")) for d in [*kept_before, *raw]}
    catalog.assets = [a for a in catalog.assets if a.id not in ids and not is_character(a)]
    generated: dict[str, str] = {}
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    used: set[str] = set()
    for item in raw:
        try:
            definition = normalized(item)
        except CharacterError as exc:
            issues.add("ASSET-033", character=str(item.get("id", "?")), reason=str(exc))
            continue
        if definition["id"] in seen:
            continue
        seen.add(definition["id"])
        kept.append(definition)
        if definition.get("removed"):
            continue
        try:
            asset, rendered, gone = build_asset(definition, catalog, pack_roots)
        except (CharacterError, OSError, ValueError) as exc:
            issues.add("ASSET-033", character=definition["id"], reason=str(exc))
            continue
        for layer in gone:
            issues.add(
                "ASSET-033",
                character=definition["id"],
                reason=f"its layer {layer} is not in the packs any more; it is drawn without it",
            )
        old = previous.asset(asset.id) if previous is not None else None
        if old is not None:  # what somebody changed on the character itself stays
            asset.overrides = copy.deepcopy(old.overrides)
            if old.status in ("UNUSED", "CONFIRMED"):
                asset.status = old.status
        catalog.assets.append(asset)
        generated[asset.path] = str(rendered)
        used.add(definition["body"])
    for asset in catalog.assets:
        tags = [t for t in asset.detected.get("tags", []) if t != USED_IN_TAG]
        freed = USED_IN_TAG in asset.detected.get("tags", []) and asset.id not in used
        if freed and is_body(asset):
            # its character was taken away: the body is what the classifier takes it for again
            from rpggen.core import classifier

            rel = asset.path.split("/", 3)[-1]
            bare = {k: v for k, v in asset.detected.items() if k not in ("role", "roles_alt")}
            asset.detected["role"] = classifier.classify(bare, rel, None)[0]
            asset.detected["tags"] = sorted(tags)
            asset.status = catalog_mod.recompute_status(asset)
        if asset.id in used and is_body(asset):
            # the bare body is in a character now: it is not also a character of its own
            asset.detected["role"] = "NONE"
            asset.detected.pop("roles_alt", None)
            tags.append(USED_IN_TAG)
            asset.status = catalog_mod.recompute_status(asset)
        if tags != asset.detected.get("tags", []):
            asset.detected["tags"] = sorted(tags)
    catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    catalog.characters = kept
    return generated


def definition_of(catalog: Any, asset_id: str) -> dict[str, Any] | None:
    """The definition of a character that is there (not one that was removed)."""
    return next(
        (d for d in catalog.characters if d.get("id") == asset_id and not d.get("removed")), None
    )
