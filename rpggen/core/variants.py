"""Recolour variants (T13.18): a second slime from the one a pack ships.

A variant is a definition ``{id, source, name, op, params}`` (and ``stats`` for an enemy) in
``catalog.variants``. From it the catalog gets an **effective asset**: the source's picture
recoloured, written to ``generated/variants/<slug>.png``, with the source's facets (grid, frames,
animations, collision, usage and role) and ``derived_from: <source id>``. The picture is rendered
again from the current source on every analysis, so a pack update reaches its variants.

``render`` is deterministic: integer arithmetic only, no dithering, alpha untouched.
"""

from __future__ import annotations

import copy
import hashlib
import io
import re
from pathlib import Path
from typing import Any

from rpggen import paths

VARIANT_DIR = "generated/variants"
OPS = ("hue", "palette")
STAT_KEYS = ("hp", "attack", "xp", "gold")
ENEMY_ROLES = ("ENEMY", "BOSS")
HUE_STEPS = 1530  # six sectors of 255: a hue as an integer
_SLUG = re.compile(r"[^a-z0-9]+")


class VariantError(ValueError):
    """A variant definition that cannot be used (the message says why)."""


# --------------------------------------------------------------------------- definitions


def slug(name: str) -> str:
    """ "Fire slime" -> "fire_slime"."""
    return _SLUG.sub("_", name.strip().lower()).strip("_") or "variant"


def new_id(existing: set[str], pack_id: str, name: str) -> str:
    """An asset id for a new variant that nothing in ``existing`` has."""
    base = f"{pack_id}.variants.{slug(name)}"
    candidate, n = base, 2
    while candidate in existing:
        candidate = f"{base}_{n}"
        n += 1
    return candidate


def path_of(variant_id: str) -> str:
    """The project-relative file of a variant's picture."""
    return f"{VARIANT_DIR}/{variant_id.replace('.', '_').replace('#', '_')}.png"


def normalized(definition: dict[str, Any]) -> dict[str, Any]:
    """The definition with its parameters checked and in canonical form; ``VariantError``
    when it cannot be rendered."""
    for key in ("id", "source", "name", "op"):
        if not isinstance(definition.get(key), str) or not definition[key]:
            raise VariantError(f"a variant needs '{key}'")
    op = definition["op"]
    params = definition.get("params")
    if op not in OPS or not isinstance(params, dict):
        raise VariantError(f"unknown variant operation '{op}'")
    out: dict[str, Any] = {k: definition[k] for k in ("id", "source", "name", "op")}
    if op == "hue":
        try:
            out["params"] = {
                "shift": int(round(float(params.get("shift", 0)))) % 360,
                "saturation": round(max(0.0, min(4.0, float(params.get("saturation", 1.0)))), 3),
                "value": round(max(0.0, min(4.0, float(params.get("value", 1.0)))), 3),
            }
        except (TypeError, ValueError) as exc:
            raise VariantError("the hue parameters must be numbers") from exc
    else:
        pairs = params.get("map")
        if not isinstance(pairs, list):
            raise VariantError("a palette variant needs 'map'")
        clean = []
        for pair in pairs:
            ok = (
                isinstance(pair, (list, tuple))
                and len(pair) == 2
                and all(
                    isinstance(c, (list, tuple))
                    and len(c) == 3
                    and all(isinstance(v, int) and 0 <= v <= 255 for v in c)
                    for c in pair
                )
            )
            if not ok:
                raise VariantError("a palette entry is [[r, g, b], [r, g, b]] with 0 to 255")
            clean.append([list(pair[0]), list(pair[1])])
        out["params"] = {"map": clean}
    stats = definition.get("stats")
    if isinstance(stats, dict):
        kept = {}
        for key in STAT_KEYS:
            if key in stats:
                try:
                    value = round(max(0.1, min(20.0, float(stats[key]))), 2)
                except (TypeError, ValueError) as exc:
                    raise VariantError(f"the {key} multiplier must be a number") from exc
                if value != 1.0:
                    kept[key] = value
        if kept:
            out["stats"] = kept
    return out


# --------------------------------------------------------------------------- rendering


def _hue_shift(rgb: Any, shift: int, saturation: float, value: float) -> Any:
    """``rgb`` (an int64 array [..., 3]) with its hue turned by ``shift`` degrees and its
    saturation and value multiplied. Integers throughout: the same bytes on every machine."""
    import numpy

    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    high = numpy.maximum(numpy.maximum(r, g), b)
    low = numpy.minimum(numpy.minimum(r, g), b)
    delta = high - low
    safe = numpy.where(delta == 0, 1, delta)
    # the hue in 0..1529: 255 steps for each of the six sectors of the colour wheel
    hue = numpy.where(
        high == r,
        (255 * (g - b)) // safe,
        numpy.where(high == g, 510 + (255 * (b - r)) // safe, 1020 + (255 * (r - g)) // safe),
    )
    hue = numpy.where(delta == 0, 0, hue) % HUE_STEPS
    sat = numpy.where(high == 0, 0, (255 * delta + high // 2) // numpy.where(high == 0, 1, high))
    hue = (hue + (shift % 360) * HUE_STEPS // 360) % HUE_STEPS
    sat = numpy.minimum(255, sat * int(round(saturation * 1000)) // 1000)
    val = numpy.minimum(255, high * int(round(value * 1000)) // 1000)
    sector, part = hue // 255, hue % 255
    full = 255 * 255
    p = (val * (255 - sat) + 127) // 255
    q = (val * (full - sat * part) + full // 2) // full
    t = (val * (full - sat * (255 - part)) + full // 2) // full
    choices_r = [val, q, p, p, t, val]
    choices_g = [t, val, val, q, p, p]
    choices_b = [p, p, t, val, val, q]
    return numpy.stack(
        [
            numpy.choose(sector, choices_r),
            numpy.choose(sector, choices_g),
            numpy.choose(sector, choices_b),
        ],
        axis=-1,
    )


def render(source_image: Any, op: str, params: dict[str, Any]) -> Any:
    """The recoloured picture (a new RGBA ``PIL.Image``). Alpha is kept as it is, and so are the
    colours of fully transparent pixels."""
    import numpy
    from PIL import Image

    rgba = numpy.asarray(source_image.convert("RGBA")).astype(numpy.int64)
    rgb, alpha = rgba[..., :3], rgba[..., 3:]
    if op == "hue":
        shift = int(params.get("shift", 0)) % 360
        saturation = float(params.get("saturation", 1.0))
        value = float(params.get("value", 1.0))
        unchanged = shift == 0 and saturation == 1.0 and value == 1.0
        new = rgb if unchanged else _hue_shift(rgb, shift, saturation, value)
    elif op == "palette":
        new = rgb.copy()
        for old, to in params.get("map", []):
            hit = (rgb == numpy.asarray(old, dtype=numpy.int64)).all(axis=-1)
            new[hit] = numpy.asarray(to, dtype=numpy.int64)
    else:
        raise VariantError(f"unknown variant operation '{op}'")
    new = numpy.where(alpha == 0, rgb, new)
    out = numpy.concatenate([new, alpha], axis=-1).astype(numpy.uint8)
    return Image.fromarray(out, "RGBA")


def render_bytes(source_image: Any, op: str, params: dict[str, Any]) -> bytes:
    """``render`` as PNG bytes: byte-identical for the same input on every run."""
    out = io.BytesIO()
    render(source_image, op, params).save(out, format="PNG", optimize=False, compress_level=6)
    return out.getvalue()


def palette_of(source_image: Any, limit: int = 32) -> list[tuple[int, int, int]]:
    """The colours of the visible pixels, most used first (the palette table's rows)."""
    counts: dict[tuple[int, int, int], int] = {}
    rgba = source_image.convert("RGBA")
    for count, colour in rgba.getcolors(maxcolors=rgba.width * rgba.height) or []:
        if colour[3] == 0:
            continue
        key = (colour[0], colour[1], colour[2])
        counts[key] = counts.get(key, 0) + count
    ranked = sorted(counts, key=lambda c: (-counts[c], c))
    return ranked[:limit]


# --------------------------------------------------------------------------- the catalog


def cache_dir() -> Path:
    """Where rendered variants are kept (named by their content, so nothing is ever stale)."""
    return paths.cache_dir() / "variants"


def cached_file(sha256: str) -> Path:
    return cache_dir() / f"{sha256}.png"


def _source_file(asset: Any, pack_roots: dict[str, Path]) -> Path | None:
    parts = asset.path.split("/", 3)
    root = pack_roots.get(asset.pack_id)
    if root is None or len(parts) != 4 or parts[:2] != ["assets", "packs"]:
        return None
    file = Path(root) / parts[3]
    return file if file.is_file() else None


def build_asset(definition: dict[str, Any], source: Any, source_file: Path) -> tuple[Any, Path]:
    """(the variant's effective asset, its rendered file in the cache)."""
    from PIL import Image

    from rpggen.core import catalog as catalog_mod

    with Image.open(source_file) as opened:
        data = render_bytes(opened, definition["op"], definition["params"])
    digest = hashlib.sha256(data).hexdigest()
    file = cached_file(digest)
    if not file.is_file():
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(file)
    facets = copy.deepcopy(catalog_mod.effective(source))
    facets["derived_from"] = source.id
    facets["tags"] = sorted(
        t for t in facets.get("tags") or [] if not str(t).startswith("duplicate_of:")
    )
    asset = catalog_mod.Asset(
        id=definition["id"],
        pack_id=source.pack_id,
        path=path_of(definition["id"]),
        sha256=digest,
        kind="image",
        status="CONFIRMED",
        detected=facets,
        detected_by="variant",
        confidence=1.0,
    )
    return asset, file


def apply(
    catalog: Any,
    definitions: list[dict[str, Any]],
    pack_roots: dict[str, Path],
    issues: Any,
    previous: Any | None = None,
) -> dict[str, str]:
    """Add the effective asset of every variant to ``catalog`` (replacing an older one) and
    return ``{project-relative path: rendered file}`` for the installer. A variant whose source
    is gone, or whose definition cannot be rendered, gets ``ASSET-029`` and no asset; its
    definition stays, so it is back when the source is."""
    generated: dict[str, str] = {}
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    variant_ids = {str(d.get("id")) for d in definitions}
    catalog.assets = [a for a in catalog.assets if a.id not in variant_ids]
    for raw in definitions:
        try:
            definition = normalized(raw)
        except VariantError as exc:
            issues.add("ASSET-029", variant=str(raw.get("id", "?")), reason=str(exc))
            continue
        if definition["id"] in seen:
            continue
        seen.add(definition["id"])
        kept.append(definition)
        source = catalog.asset(definition["source"])
        usable = source is not None and source.kind == "image" and source.status != "MISSING"
        file = _source_file(source, pack_roots) if usable else None
        if source is None or file is None:
            issues.add(
                "ASSET-029",
                variant=definition["id"],
                reason=f"its source {definition['source']} is not in the packs any more",
            )
            continue
        try:
            asset, rendered = build_asset(definition, source, file)
        except (OSError, ValueError) as exc:
            issues.add("ASSET-029", variant=definition["id"], reason=str(exc))
            continue
        old = previous.asset(asset.id) if previous is not None else None
        if old is not None:  # what the user changed on the variant itself stays
            asset.overrides = copy.deepcopy(old.overrides)
            if old.status in ("UNUSED", "CONFIRMED"):
                asset.status = old.status
        catalog.assets.append(asset)
        generated[asset.path] = str(rendered)
    catalog.variants = kept
    return generated


def definition_of(catalog: Any, asset_id: str) -> dict[str, Any] | None:
    return next((d for d in catalog.variants if d.get("id") == asset_id), None)


def is_variant(asset: Any) -> bool:
    return asset.detected_by == "variant" or "derived_from" in asset.detected


def stats_apply(source: Any) -> bool:
    """True when a variant of ``source`` gets the stats multipliers (an enemy or a boss)."""
    from rpggen.core import catalog as catalog_mod

    return catalog_mod.effective(source).get("role") in ENEMY_ROLES
