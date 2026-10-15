"""Isometric terrains (T17.31): pieces of a pack that join along the sides of a diamond.

An isometric pack draws its roads, paths, rivers and shores as single tiles, each the piece
for one way of joining: Kenney's *Vector Roads* names them (``roadES``, ``waterCornerNE``,
T17.12 reads the capitals as ``joins``), Screaming Brain's *Pathways* and *Roads* lay eleven
pieces in a sheet without a name (T17.30 cuts them, ``#c<col>_<row>``). Names do not say
enough (``lotE`` names the side its kerb is on, ``waterE`` the side the land is on), so every
piece is read from its picture:

* its **middle** is the surface (``measure``: a patch at the middle of its diamond);
* a **side is open** when the surface goes on there: the point near the middle of that side
  (``SIDE_REACH`` of the way out, in the grid's own measure) has the middle's colour; a
  **corner is open** when the point near that corner has it and both sides beside it are
  open;
* pieces are grouped: the cells of one sheet are one group, single pictures of one pack by
  their role, by whether any corner is open (a road or a river joins at its sides only, a
  shore has inner corners) and by the colours of their middle and of what lies outside;
* a group is checked by **edge matching**: two pieces laid side by side meet along the side of
  a diamond, and the pixels along it must fit where both are open (or both closed) clearly
  better than where one is open and the other is not (``CONTRAST_LIMIT``).

A group that holds is a terrain set of the isometric tile set: ``sides`` (Godot's
``TERRAIN_MODE_MATCH_SIDES``) for a group whose corners are all closed, a piece whose surface
fills a corner (a car park, a plaza) left out of it; ``corners_and_sides`` for the others. A
piece's ``iso_terrain`` facet carries the set (``set``, ``mode``, ``surface``, ``over``,
``shape``, ``role``) and its ``peering`` in the grid's names (``top_side`` is the side ``n``,
the upper right; ``top_right_corner`` the corner between ``n`` and ``e``, the right corner of
the diamond); ``iso_atlas.add`` gathers the sets into the tile set's definition and the builder
turns the names into Godot's isometric neighbours.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen.core import catalog as catalog_mod
from rpggen.core.terrain import blocks

SIDE_REACH = 0.40  # how far toward the middle of a side it is looked at (the side is at 0.5)
CORNER_REACH = 0.34  # how far toward a corner, each way
EDGE_INSET = 0.46  # where the pixels along a side are read to match two pieces
COLOUR_NEAR = 0.11  # a point has the middle's colour within this (mean channel, 0..1)
OUTSIDE_NEAR = 0.15  # the pieces of two names have the same land round them within this
CONTRAST_LIMIT = 0.8
MIN_PIECES = 3
EDGE_POINTS = 9
ROLES = frozenset({"ROAD", "WATER", "GROUND"})
SIDES = ("n", "e", "s", "w")
_SIDE_AT = {"n": (0.0, -1.0), "e": (1.0, 0.0), "s": (0.0, 1.0), "w": (-1.0, 0.0)}
# corners by the grid: ne is the diamond's right corner, es its bottom, sw its left, nw its top
_CORNER_AT = {"ne": (1.0, -1.0), "es": (1.0, 1.0), "sw": (-1.0, 1.0), "nw": (-1.0, -1.0)}
_CORNER_SIDES = {"ne": ("n", "e"), "es": ("e", "s"), "sw": ("s", "w"), "nw": ("w", "n")}
PEERING = {
    "n": "top_side",
    "e": "right_side",
    "s": "bottom_side",
    "w": "left_side",
    "ne": "top_right_corner",
    "es": "bottom_right_corner",
    "sw": "bottom_left_corner",
    "nw": "top_left_corner",
}
FACET = "iso_terrain"


@dataclass
class Piece:
    asset_id: str
    key: tuple[Any, ...]
    sides: frozenset[str]
    corners: frozenset[str]
    middle: np.ndarray
    outside: np.ndarray | None
    rgba: np.ndarray
    origin: tuple[float, float]
    foot: tuple[int, int]
    words: set[str]
    # the sides its name gives (``joins``, turned to the grid by the reader of T17.12), the
    # name without them and without ``Corner``, and whether the name says ``Corner``
    named: frozenset[str] | None = None
    stem: str = ""
    corner_word: bool = False


def apply_names(pieces: list[Piece]) -> None:
    """The sides of the pieces whose names give them (T17.12's ``joins``), read the way the
    pictures say: a name gives the sides a road goes on (``roadES``) or the sides the land is
    on (``waterE``, ``lotE``, its kerb); of the pieces of one name the reading that fits their
    pictures best is taken. A ``Corner`` piece (``waterCornerES``) is the surface on every side
    with the land in the corner between the sides it names. A name is surer than a picture
    whose face is drawn at two heights (Kenney's water lies lower than the land round it)."""
    by_stem: dict[str, list[Piece]] = {}
    for p in pieces:
        if p.named is not None:
            by_stem.setdefault(p.stem, []).append(p)
    every = frozenset(SIDES)
    for group in by_stem.values():
        as_open = sum(len(p.sides ^ p.named) for p in group if p.named is not None)
        as_closed = sum(len(p.sides ^ (every - p.named)) for p in group if p.named is not None)
        open_is_named = as_open <= as_closed
        # the surface is the middle most of them have (an outer corner's middle is the land)
        middle = max(
            (p.middle for p in group),
            key=lambda m: sum(1 for q in group if _near(q.middle, m)),
        )
        for p in group:
            p.middle = middle
        for p in group:
            if p.named is None:
                continue
            if p.corner_word and len(p.named) == 2:
                land = next(
                    (c for c, pair in _CORNER_SIDES.items() if set(pair) == set(p.named)), None
                )
                p.sides = every
                p.corners = frozenset(c for c in _CORNER_SIDES if c != land)
            else:
                p.sides = p.named if open_is_named else every - p.named
                if open_is_named:
                    p.corners = frozenset()  # a road: the corners are its verge
                else:
                    p.corners = frozenset(
                        c for c, (a, b) in _CORNER_SIDES.items() if a in p.sides and b in p.sides
                    )
            p.outside = outside_of(p.rgba, p.origin, p.foot, p.sides, p.corners)


def _point(
    rgba: np.ndarray, origin: tuple[float, float], foot: tuple[int, int], east: float, south: float
) -> np.ndarray | None:
    """The colour (0..1, RGB) of the 3x3 px round a point of a diamond given in the grid's own
    measure from its middle; None where it is not painted."""
    x = int(round(origin[0] + (east - south) * foot[0] / 2.0))
    y = int(round(origin[1] + (east + south) * foot[1] / 2.0))
    h, w = rgba.shape[:2]
    patch = rgba[max(0, y - 1) : min(h, y + 2), max(0, x - 1) : min(w, x + 2)]
    if patch.size == 0:
        return None
    painted = patch[..., 3] >= 128
    if painted.mean() < 0.5:
        return None
    return np.asarray(patch[..., :3][painted].mean(axis=0) / 255.0, dtype=np.float64)


def _painted_points(rgba: np.ndarray, origin: tuple[float, float], foot: tuple[int, int]) -> int:
    points = [(0.0, 0.0), *_SIDE_AT.values(), *_CORNER_AT.values()]
    return sum(
        _point(rgba, origin, foot, de * SIDE_REACH, ds * SIDE_REACH) is not None
        for de, ds in points
    )


def face_origin(
    rgba: np.ndarray, origin: tuple[float, float], foot: tuple[int, int]
) -> tuple[float, float]:
    """The middle of the face a piece paints: the catalog's (where it stands on the map's
    diamond), unless the face lies lower in the picture (Kenney's water is a few px below the
    land round it) and the diamond whose top is the first painted row of the middle column has
    more of the points read painted."""
    column = rgba[:, int(origin[0]), 3] if 0 <= int(origin[0]) < rgba.shape[1] else None
    if column is None or not (column >= 128).any():
        return origin
    top = float(np.argmax(column >= 128))
    lower = (origin[0], top + foot[1] / 2.0)
    if lower[1] <= origin[1]:
        return origin
    return (
        lower
        if _painted_points(rgba, lower, foot) > _painted_points(rgba, origin, foot)
        else origin
    )


def _near(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    return a is not None and b is not None and float(np.abs(a - b).mean()) <= COLOUR_NEAR


def read_piece(
    asset_id: str, rgba: np.ndarray, origin: tuple[float, float], foot: tuple[int, int]
) -> tuple[frozenset[str], frozenset[str], np.ndarray, np.ndarray | None] | None:
    """``(open sides, open corners, middle colour, outside colour)`` of a flat piece, or None
    when its middle is not painted."""
    origin = face_origin(rgba, origin, foot)
    middle = _point(rgba, origin, foot, 0.0, 0.0)
    if middle is None:
        return None
    sides = set()
    for side, (de, ds) in _SIDE_AT.items():
        found = _point(rgba, origin, foot, de * SIDE_REACH, ds * SIDE_REACH)
        if _near(found, middle):
            sides.add(side)
    corners = set()
    for corner, (de, ds) in _CORNER_AT.items():
        a, b = _CORNER_SIDES[corner]
        if (
            a in sides
            and b in sides
            and _near(_point(rgba, origin, foot, de * CORNER_REACH, ds * CORNER_REACH), middle)
        ):
            corners.add(corner)
    found_sides, found_corners = frozenset(sides), frozenset(corners)
    return found_sides, found_corners, middle, outside_of(rgba, origin, foot, sides, corners)


def outside_of(
    rgba: np.ndarray,
    origin: tuple[float, float],
    foot: tuple[int, int],
    sides: set[str] | frozenset[str],
    corners: set[str] | frozenset[str],
) -> np.ndarray | None:
    """The colour of what lies outside a piece's surface: at its closed sides and corners (the
    land round a pond, the verge of a road); None when that is nothing (a path over nothing)
    or the piece is closed nowhere."""
    # the closed corners first: the side of a road is its kerb, a bridge's its rail, and what
    # they cross shows in the corners (grass, water)
    at_corners = [
        _point(rgba, origin, foot, de * CORNER_REACH, ds * CORNER_REACH)
        for corner, (de, ds) in _CORNER_AT.items()
        if corner not in corners
    ]
    painted = [f for f in at_corners if f is not None]
    if not painted:
        at_sides = [
            _point(rgba, origin, foot, de * SIDE_REACH, ds * SIDE_REACH)
            for side, (de, ds) in _SIDE_AT.items()
            if side not in sides
        ]
        painted = [f for f in at_sides if f is not None]
    return np.mean(painted, axis=0) if painted else None


def _edge(piece: Piece, side: str) -> np.ndarray | None:
    """The colours along a side of a piece, from its first corner to its second in the order
    the neighbour across that side has them (a side ``e`` and the side ``w`` of the piece east
    of it are read at the same ``south``)."""
    out = []
    for i in range(EDGE_POINTS):
        t = -0.4 + 0.8 * i / (EDGE_POINTS - 1)
        if side in ("e", "w"):
            east, south = (EDGE_INSET if side == "e" else -EDGE_INSET), t
        else:
            east, south = t, (EDGE_INSET if side == "s" else -EDGE_INSET)
        found = _point(piece.rgba, piece.origin, piece.foot, east, south)
        out.append(found if found is not None else np.full(3, -1.0))
    return np.array(out)


def _holds(pieces: list[Piece]) -> bool:
    """Edge matching of a group: the seams of two pieces that should meet (both open there, or
    both closed) differ clearly less than those that should not."""
    fitting: list[float] = []
    other: list[float] = []
    for a in pieces:
        for b in pieces:
            for side, across in (("e", "w"), ("s", "n")):
                ea, eb = _edge(a, side), _edge(b, across)
                if ea is None or eb is None:
                    continue
                diff = float(np.abs(ea - eb).mean())
                if (side in a.sides) == (across in b.sides):
                    fitting.append(diff)
                else:
                    other.append(diff)
    if not fitting:
        return False
    if not other:
        return True
    return float(np.mean(fitting)) <= CONTRAST_LIMIT * float(np.mean(other))


def _group_key(asset: catalog_mod.Asset, facets: dict[str, Any]) -> tuple[Any, ...]:
    if "#c" in asset.id:  # the cells of one sheet are one group
        return ("sheet", asset.id.split("#", 1)[0])
    return ("pack", asset.pack_id)


def _cluster(pieces: list[Piece]) -> list[list[Piece]]:
    """Single pictures of one pack and role split by what they are: joined at the sides only or
    not, the colour of their middle and of what is outside them."""
    groups: list[list[Piece]] = []

    def mean_outside(g: list[Piece]) -> np.ndarray | None:
        found = [q.outside for q in g if q.outside is not None]
        return np.mean(found, axis=0) if found else None

    def pathlike_of(p: Piece) -> bool:
        return not p.corners and p.sides != frozenset(SIDES)

    by_kind: list[list[Piece]] = []
    for p in pieces:
        for g in by_kind:
            if pathlike_of(p) == pathlike_of(g[0]) and _near(p.middle, g[0].middle):
                g.append(p)
                break
        else:
            by_kind.append([p])
    # then by what lies outside them: a shore of grass and a shore of sand are two terrains,
    # and a bridge is no piece of a road on land; a piece closed nowhere goes with the most
    for kind in by_kind:
        # the pieces of one name go together (a picture without one is its own)
        stems: dict[str, list[Piece]] = {}
        for p in kind:
            stems.setdefault(p.stem or p.asset_id, []).append(p)
        split: list[list[Piece]] = []
        loose: list[Piece] = []
        for name in sorted(stems, key=lambda s: (-len(stems[s]), s)):
            members = stems[name]
            theirs = mean_outside(members)
            if theirs is None:
                loose.extend(members)
                continue
            for g in split:
                ours = mean_outside(g)
                # a shore of grass is not one of sand; a bridge (rails and water) is no road
                if ours is None or float(np.abs(theirs - ours).max()) > OUTSIDE_NEAR:
                    continue
                g.extend(members)
                break
            else:
                split.append(list(members))
        if not split:
            split = [[]]
        split[0].extend(loose)
        groups.extend(g for g in split if g)
    # a plain middle (every side and corner open) joins the largest group of its colour
    plain = [g for g in groups if len(g) == 1 and g[0].sides == frozenset(SIDES) and g[0].corners]
    for g in plain:
        best = max(
            (h for h in groups if h is not g and len(h) > 1 and _near(h[0].middle, g[0].middle)),
            key=len,
            default=None,
        )
        if best is not None:
            best.extend(g)
            g.clear()
    return [g for g in groups if g]


def _usable(asset: catalog_mod.Asset, facets: dict[str, Any]) -> bool:
    return (
        asset.kind == "image"
        and facets.get("usage") == "iso_tile"
        and asset.status not in ("UNUSED", "MISSING")
        and not facets.get("rise")
        and not any(facets.get(k) for k in ("edge", "post", "roof"))
        and facets.get("role") in ROLES
        and isinstance(facets.get("origin"), list)
        and isinstance(facets.get("footprint"), list)
    )


def read(
    catalog: catalog_mod.Catalog,
    roots: dict[str, Path],
    generated: dict[str, str],
    in_parallel: Callable[[Callable[[Any], Any], list[Any]], list[Any]],
) -> int:
    """Gives the pieces of the isometric packs that make a terrain their ``iso_terrain``
    facet; returns how many terrains were read. ``generated`` maps the project paths of the
    pictures rpggen cut to their files; ``in_parallel`` runs a job over items as the image
    analysis does (and polls the cancel)."""
    candidates: list[tuple[catalog_mod.Asset, dict[str, Any], Path]] = []
    for asset in sorted(catalog.assets, key=lambda a: catalog_mod._sort_key(a.id)):
        facets = catalog_mod.effective(asset)
        if not _usable(asset, facets):
            continue
        file = Path(generated[asset.path]) if asset.path in generated else None
        if file is None and asset.pack_id in roots:
            file = roots[asset.pack_id] / asset.path.split("/", 3)[-1]
        if file is None or not file.is_file():
            continue
        candidates.append((asset, facets, file))

    def job(item: tuple[catalog_mod.Asset, dict[str, Any], Path]) -> Piece | None:
        asset, facets, file = item
        try:
            with Image.open(file) as opened:
                rgba = np.asarray(opened.convert("RGBA"))
        except (OSError, ValueError):
            return None
        origin = (float(facets["origin"][0]), float(facets["origin"][1]))
        foot = (int(facets["footprint"][0]), int(facets["footprint"][1]))
        origin = face_origin(rgba, origin, foot)
        found = read_piece(asset.id, rgba, origin, foot)
        if found is None:
            return None
        sides, corners, middle, outside = found
        from rpggen.core import classifier
        from rpggen.core.adapters import naming

        folders, stem = classifier.tokens(asset.path)
        piece = Piece(
            asset.id,
            _group_key(asset, facets),
            sides,
            corners,
            middle,
            outside,
            rgba,
            origin,
            foot,
            set(folders) | set(stem),
        )
        joins = facets.get("joins")
        split = naming.split_joins(posixpath.splitext(posixpath.basename(asset.path))[0])
        if isinstance(joins, list) and joins and split is not None:
            base = split[0].casefold()
            piece.corner_word = base.endswith("corner")
            piece.stem = base.removesuffix("corner")
            piece.named = frozenset(str(s) for s in joins)
        return piece

    pieces = [p for p in in_parallel(job, candidates) if p is not None]
    by_key: dict[tuple[Any, ...], list[Piece]] = {}
    for p in pieces:
        by_key.setdefault(p.key, []).append(p)
    by_id = {a.id: a for a in catalog.assets}
    made = 0
    used: set[str] = set()
    for key in sorted(by_key, key=str):
        if key[0] != "sheet":
            apply_names(by_key[key])
        groups = [by_key[key]] if key[0] == "sheet" else _cluster(by_key[key])
        for group in groups:
            spec = _terrain(group, by_id, used)
            if spec is not None:
                made += 1
    return made


def _terrain(
    group: list[Piece], by_id: dict[str, catalog_mod.Asset], used: set[str]
) -> dict[str, Any] | None:
    pathlike = all(not p.corners for p in group if p.sides != frozenset(SIDES)) and not any(
        p.corners and p.sides == frozenset(SIDES) and len(p.corners) < 4 for p in group
    )
    members = [p for p in group if not (pathlike and p.corners)]
    if len(members) < MIN_PIECES or len({p.sides for p in members}) < MIN_PIECES:
        return None
    # the edges of pieces whose names give their sides are not matched: a name is surer than a
    # picture whose face is drawn at two heights (Kenney's water lies below its land)
    named = all(p.named is not None or p.sides == frozenset(SIDES) for p in members)
    if not named and not _holds(members):
        return None
    first = by_id[members[0].asset_id]
    roles = [str(catalog_mod.effective(by_id[p.asset_id]).get("role", "")) for p in members]
    role = max(sorted(set(roles)), key=roles.count)
    words = set().union(*(p.words for p in members))
    middle = np.mean([p.middle for p in members], axis=0)
    surface = blocks.surface_of(middle, words)
    if role == "ROAD" and surface not in ("path", "road"):
        surface = "road" if words & {"road", "roads", "asphalt", "street"} else "path"
    if words & {"road", "roads", "asphalt", "street"} and surface == "path":
        surface = "road"
    # named after the picture (``roadES``) or, for the cells of a sheet, after the sheet
    if "#" in first.id:
        stem = first.id.split("#", 1)[0].rsplit(".", 1)[-1]
    else:
        stem = posixpath.basename(first.path).rsplit(".", 1)[0]
    name = f"iso_{stem}_{surface}"
    if name in used:
        name = f"iso_{first.id.replace('.', '_').replace('#', '_')}_{surface}"
    used.add(name)
    mode = "sides" if pathlike else "corners_and_sides"
    over = "nothing" if any(p.outside is None and len(p.sides) < 4 for p in members) else "ground"
    spec = {
        "set": name,
        "mode": mode,
        "surface": surface,
        "over": over,
        "shape": "path" if pathlike else "any",
        "role": role,
    }
    for p in members:
        peering = {key: -1 for key in PEERING.values()}
        for side in p.sides:
            peering[PEERING[side]] = 0
        if mode == "corners_and_sides":
            for corner in p.corners:
                peering[PEERING[corner]] = 0
        asset = by_id[p.asset_id]
        asset.detected[FACET] = {**spec, "peering": peering}
    return spec


def terrain_sets(
    members: list[catalog_mod.Asset], known: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The terrain sets of the isometric tile set: the ones it has (in their order: painted maps
    name them by their place), then the sets of ``members``' ``iso_terrain`` facets in the order
    of the members."""
    out = [dict(t) for t in known]
    names = {t["name"] for t in out}
    for asset in members:
        found = catalog_mod.effective(asset).get(FACET)
        if not isinstance(found, dict) or found.get("set") in names:
            continue
        names.add(found["set"])
        index = len(out)
        spec = {
            "name": found["set"],
            "mode": found.get("mode", "sides"),
            "terrains": [
                {
                    "name": found.get("surface", "path"),
                    "color": blocks.a2._COLORS[index % len(blocks.a2._COLORS)],
                }
            ],
        }
        for key in ("surface", "over", "shape", "role"):
            if key in found:
                spec[key] = found[key]
        spec["sheet"] = asset.id
        out.append(spec)
    return out
