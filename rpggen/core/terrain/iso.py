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
# a piece whose name says it rises across its face is no flat ground (T17.33: Kenney's racing
# packs' ``hillES``, Miniature Farm's ``planksHighSlope``): its two shades read as edges
SLOPE_WORDS = frozenset({"hill", "hills", "slope", "slopes", "ramp", "ramps"})


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
        from rpggen.core import classifier
        from rpggen.core.adapters import naming

        folders, stem = classifier.tokens(asset.path)
        if set(stem) & SLOPE_WORDS:
            return None
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
    by_id = {a.id: a for a in catalog.assets}
    used: set[str] = set()
    # two flat tones shared at the corners in many ways (T17.33: Medieval Town's plates) are a
    # set of two terrains before they are read by their sides as a shore of one in the other;
    # pieces whose names give their sides, and the cells of a sheet, are read by their sides
    made = corner_sets([p for p in pieces if p.named is None and p.key[0] != "sheet"], by_id, used)
    by_key: dict[tuple[Any, ...], list[Piece]] = {}
    for p in pieces:
        if FACET not in by_id[p.asset_id].detected:
            by_key.setdefault(p.key, []).append(p)
    for key in sorted(by_key, key=str):
        if key[0] != "sheet":
            apply_names(by_key[key])
        groups = [by_key[key]] if key[0] == "sheet" else _cluster(by_key[key])
        for group in groups:
            spec = _terrain(group, by_id, used)
            if spec is not None:
                made += 1
    # what is left: plain grounds of whole diamonds (T17.33)
    made += plain_sets(pieces, by_id, used)
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
    role_of = {
        p.asset_id: str(catalog_mod.effective(by_id[p.asset_id]).get("role", "")) for p in members
    }
    roles = [role_of[p.asset_id] for p in members]
    role = max(sorted(set(roles)), key=roles.count)
    # a piece of another role is not one of these, though its name and colours agree (Kenney's
    # streets are kerbed roads beside the roads): a painted road would lay them in its turns.
    # A plain middle stays whatever its role
    members = [p for p in members if role_of[p.asset_id] == role or p.sides == frozenset(SIDES)]
    if len(members) < MIN_PIECES or len({p.sides for p in members}) < MIN_PIECES:
        return None
    first = by_id[members[0].asset_id]
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
    chances = _middle_chances(members, mode)
    for p in members:
        peering = {key: -1 for key in PEERING.values()}
        for side in p.sides:
            peering[PEERING[side]] = 0
        if mode == "corners_and_sides":
            for corner in p.corners:
                peering[PEERING[corner]] = 0
        asset = by_id[p.asset_id]
        asset.detected[FACET] = {**spec, "peering": peering}
        if p.asset_id in chances:
            asset.detected[FACET]["probability"] = chances[p.asset_id]
    return spec


# the variants of a middle, together, at most this share of the ground (blocks.VARIANTS_SHARE)
MIDDLE_VARIANTS = 0.15
# a middle this far from the plainest one's colour (mean channel, 0..1) is another ground
MIDDLE_TONE = 0.06


def _middle_chances(members: list[Piece], mode: str) -> dict[str, float]:
    """The probability of the middles of a terrain other than its main one (T17.33). A pack
    often draws its ground's middle several times (Screaming Brain's *Floor Pack*: nine grassy
    floors, laid as often as each other, a patchwork): the plainest is the middle, those of
    its colour are variants laid now and then (together at most ``MIDDLE_VARIANTS`` of the
    ground), the others laid only where nothing else fits (0)."""

    def full(p: Piece) -> bool:
        whole_corners = mode != "corners_and_sides" or len(p.corners) == 4
        return p.sides == frozenset(SIDES) and whole_corners

    middles = [p for p in members if full(p)]
    if len(middles) < 2:
        return {}
    middles.sort(key=lambda p: (_plainness(p), p.asset_id))
    main = middles[0]
    alike = [p for p in middles[1:] if float(np.abs(p.middle - main.middle).mean()) <= MIDDLE_TONE]
    share = min(
        blocks.VARIANT_PROBABILITY, MIDDLE_VARIANTS / (1.0 - MIDDLE_VARIANTS) / max(1, len(alike))
    )
    out = {p.asset_id: 0.0 for p in middles[1:]}
    out.update({p.asset_id: round(share, 4) for p in alike})
    return out


def _plainness(piece: Piece) -> float:
    """How much the neighbouring pixels of a piece's face differ round its middle."""
    x, y = int(piece.origin[0]), int(piece.origin[1])
    half_w, half_h = max(2, piece.foot[0] // 4), max(2, piece.foot[1] // 4)
    patch = piece.rgba[max(0, y - half_h) : y + half_h, max(0, x - half_w) : x + half_w, :3]
    if patch.size == 0:
        return 0.0
    a = patch.astype(np.float32)
    return float(np.abs(np.diff(a, axis=0)).mean() + np.abs(np.diff(a, axis=1)).mean())


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
        names_ = found.get("terrains") or [found.get("surface", "path")]
        spec = {
            "name": found["set"],
            "mode": found.get("mode", "sides"),
            "terrains": [
                {
                    "name": str(terrain_name),
                    "color": blocks.a2._COLORS[(index + k) % len(blocks.a2._COLORS)],
                }
                for k, terrain_name in enumerate(names_)
            ],
        }
        for key in ("surface", "over", "shape", "role"):
            if key in found:
                spec[key] = found[key]
        spec["sheet"] = asset.id
        out.append(spec)
    return out


# --------------------------------------------------------------------------- corners and plains

# the corners of a diamond's face, from its middle (x, y in halves of the footprint), and the
# grid's name of each (``PEERING``): the top corner is nw, the right ne, the bottom es, the left sw
_FACE_CORNERS = {"nw": (0.0, -1.0), "ne": (1.0, 0.0), "es": (0.0, 1.0), "sw": (-1.0, 0.0)}
FACE_REACH = 0.72  # how far toward a corner of the face a corner's tone is read
TONE_TOL = 0.07  # a corner's colour belongs to a tone within this (mean channel, 0..1)
TONE_GAP = 0.05  # the two tones of a corner set are this far apart at least
MIN_CORNER_PIECES = 6
MIN_MIXED_WAYS = 6  # of the 14 ways between the two whole pieces, a set draws this many
MIXED_SHARE = 0.3  # ... and this share of its pieces are of them
CRISP = 0.33  # a corner of a set lies within this share of the gap between the tones of its own
CRISP_SHARE = 0.9  # ... and so do this share of the corners of a set


def _face_tone(piece: Piece, corner: str) -> np.ndarray | None:
    """The colour near one corner of a piece's face (a patch of 3 x 3 px), or None."""
    dx, dy = _FACE_CORNERS[corner]
    x = piece.origin[0] + dx * FACE_REACH * piece.foot[0] / 2.0
    y = piece.origin[1] + dy * FACE_REACH * piece.foot[1] / 2.0
    xi, yi = int(round(x)), int(round(y))
    patch = piece.rgba[max(0, yi - 1) : yi + 2, max(0, xi - 1) : xi + 2]
    if patch.size == 0 or float(patch[..., 3].mean()) < 200:
        return None
    return np.asarray(patch[..., :3].reshape(-1, 3).mean(axis=0) / 255.0, dtype=np.float32)


MAX_TONE_SAMPLES = 1200  # the corners a family's densest colours are counted over, at most
MAX_TONE_SEEDS = 4  # the densest colours tried as a set's first tone, at most


def _two_tones(rows: list[list[np.ndarray]]) -> tuple[np.ndarray, np.ndarray] | None:
    """Two colours the corners of ``rows`` fall into, the darker first; None when they are not
    two tones. The first is the colour most corners are near (within half ``TONE_GAP``) that
    meets another in a piece, the second the one most corners are near of those ``TONE_GAP``
    from it in pieces that have the first too: the two tones of a set meet in its pieces, and
    a plate of wood among the town's stone, though drawn as often and flatter, meets nothing.
    Each is then the mean of the corners nearer it than the other, within half the gap."""
    samples = np.asarray([c for row in rows for c in row], dtype=np.float32)
    row_of = np.asarray([k for k, row in enumerate(rows) for _ in row])
    if len(samples) < 8:
        return None
    step = max(1, len(samples) // MAX_TONE_SAMPLES)
    counted, counted_row = samples[::step], row_of[::step]
    near = np.abs(counted[:, None, :] - counted[None, :, :]).mean(axis=2) <= TONE_GAP / 2
    density = near.sum(axis=1)
    tried = np.zeros(len(counted), dtype=bool)
    seeds = 0
    for first in np.argsort(-density, kind="stable"):
        if tried[first]:
            continue
        if seeds == MAX_TONE_SEEDS:
            return None
        seeds += 1
        tried |= near[first]
        seed = counted[near[first]].mean(axis=0)
        off = np.abs(samples - seed).mean(axis=1)
        with_first = np.unique(row_of[off <= TONE_GAP / 2])
        away = (np.abs(counted - seed).mean(axis=1) >= TONE_GAP) & np.isin(counted_row, with_first)
        if away.any():
            break
    else:
        return None
    second = int(np.argmax(np.where(away, density, -1)))
    a, b = seed, counted[near[second]].mean(axis=0)
    for _ in range(8):
        to_a = np.abs(samples - a).mean(axis=1)
        to_b = np.abs(samples - b).mean(axis=1)
        reach = float(np.abs(a - b).mean()) / 2
        of_a = (to_a <= to_b) & (to_a <= reach)
        of_b = (to_b < to_a) & (to_b <= reach)
        if not of_a.any() or not of_b.any():
            return None
        a, b = samples[of_a].mean(axis=0), samples[of_b].mean(axis=0)
    if float(np.abs(a - b).mean()) < TONE_GAP:
        return None
    return (a, b) if float(a.mean()) <= float(b.mean()) else (b, a)


def _corner_family(piece: Piece) -> tuple[Any, ...]:
    """Pieces of one pack, one footprint and one first word of their names (``plate_road``,
    ``plate_curve``: plates) may be one set of corners."""
    pack = piece.asset_id.split(".", 1)[0]
    name = piece.asset_id.split("#", 1)[0].rsplit(".", 1)[-1]
    return (pack, piece.foot, name.split("_", 1)[0])


def corner_sets(pieces: list[Piece], by_id: dict[str, catalog_mod.Asset], used: set[str]) -> int:
    """Sets of two terrains joined at the corners of the diamond (T17.33: Kenney's *Medieval
    Town* draws its town square as plates, each its road and its pavement in a corner, half,
    three corners or whole, in four turns, and nothing says which). Pieces no terrain took, of
    one family (``_corner_family``), whose four corners fall into two tones: each piece is one
    of the 16 ways the four corners of a diamond can be the one or the other; a family is a set
    when it has both whole pieces and three ways at least between them. A piece whose corners
    are of neither tone (a plate of wood) is left out. Returns how many sets."""
    families: dict[tuple[Any, ...], list[Piece]] = {}
    for p in pieces:
        if FACET not in by_id[p.asset_id].detected:
            families.setdefault(_corner_family(p), []).append(p)
    made = 0
    for key in sorted(families, key=str):
        members = families[key]
        if len(members) < MIN_CORNER_PIECES:
            continue
        tones_of: dict[str, list[np.ndarray]] = {}
        for p in members:
            found = [_face_tone(p, c) for c in _FACE_CORNERS]
            if all(f is not None for f in found):
                tones_of[p.asset_id] = [f for f in found if f is not None]
        tones = None
        for _ in range(2):  # a piece of neither tone is left out, and the tones read again
            tones = _two_tones(list(tones_of.values()))
            if tones is None:
                break
            dark, light = tones
            tones_of = {k: row for k, row in tones_of.items() if _of_tones(row, dark, light)}
        if tones is None or len(tones_of) < MIN_CORNER_PIECES:
            continue
        dark, light = tones
        # the corners of a set are flat colours, each far nearer its tone than the tones are to
        # each other; the corners of textured floors are noise round two means
        gap = float(np.abs(dark - light).mean())
        crisp = [
            min(float(np.abs(c - dark).mean()), float(np.abs(c - light).mean())) <= CRISP * gap
            for row in tones_of.values()
            for c in row
        ]
        if sum(crisp) < CRISP_SHARE * len(crisp):
            continue
        bits: dict[str, dict[str, int]] = {}
        for asset_id, row in tones_of.items():
            bits[asset_id] = {
                corner: 0
                if float(np.abs(c - dark).mean()) <= float(np.abs(c - light).mean())
                else 1
                for corner, c in zip(_FACE_CORNERS, row, strict=True)
            }
        ways = {tuple(sorted(b.items())) for b in bits.values()}
        whole = {tuple(sorted((c, t) for c in _FACE_CORNERS)) for t in (0, 1)}
        mixed = [b for b in bits.values() if tuple(sorted(b.items())) not in whole]
        if (
            not whole <= ways
            or len(ways - whole) < MIN_MIXED_WAYS
            or len(mixed) < MIXED_SHARE * len(bits)
        ):
            # floors of many textures whose corners happen to fall into two tones are no set:
            # a set draws its ways between the two (a plate's corner, half, three corners)
            continue
        words: set[str] = set().union(*(p.words for p in members if p.asset_id in bits))
        names = [blocks.surface_of(dark, words), blocks.surface_of(light, words)]
        if names[0] == names[1]:
            names = [names[0], f"{names[1]}_light"]
        if words & {"road", "street"} and "road" not in names:
            names[0] = "road"
        if words & {"pavement", "sidewalk"} and "pavement" not in names:
            names[1] = "pavement"
        name = f"iso_{key[2]}_corners"
        while name in used:
            name += "_2"
        used.add(name)
        first = by_id[next(iter(bits))]
        role = str(catalog_mod.effective(first).get("role", "GROUND"))
        spec = {"set": name, "mode": "corners", "surface": names[0], "terrains": names,
                "over": "ground", "shape": "corners", "role": role}  # fmt: skip
        # the whole pieces of a tone after the first are variants of it, laid now and then
        seen: set[tuple[Any, ...]] = set()
        for asset_id in sorted(bits):
            corner_bits = bits[asset_id]
            peering = {key_: -1 for key_ in PEERING.values()}
            for corner, tone in corner_bits.items():
                peering[PEERING[corner]] = tone
            counts = [list(corner_bits.values()).count(t) for t in (0, 1)]
            centre = 0 if counts[0] >= counts[1] else 1
            facet = {**spec, "peering": peering, "terrain": centre}
            way = tuple(sorted(corner_bits.items()))
            if way in seen:
                facet["probability"] = round(MIDDLE_VARIANTS / 4.0, 4)
            seen.add(way)
            by_id[asset_id].detected[FACET] = facet
        made += 1
    return made


def plain_sets(pieces: list[Piece], by_id: dict[str, catalog_mod.Asset], used: set[str]) -> int:
    """A ground of whole diamonds that no terrain took is a terrain of its own (T17.33: *Lords
    Of Pain*'s stone, Kenney's *Nature* grass), so the Terrain tool paints it: the pieces of one
    pack and footprint whose faces are whole and of one colour are one plain set (matched by
    its sides), the plainest its middle, the others variants (``_middle_chances``; a patch laid
    on a ground, ``_laid_on``, is one whatever its colour). Returns how many."""
    loose = [
        p for p in pieces
        if FACET not in by_id[p.asset_id].detected and _role(by_id[p.asset_id]) == "GROUND"
        and (_whole(p) or _laid_on(by_id[p.asset_id]))
    ]  # fmt: skip
    groups: list[list[Piece]] = []
    for p in sorted(loose, key=lambda q: q.asset_id):
        pack = p.asset_id.split(".", 1)[0]
        variant = _variant_of(by_id[p.asset_id])
        for g in groups:
            same_pack = g[0].asset_id.split(".", 1)[0] == pack and g[0].foot == p.foot
            if same_pack and (variant in {q.asset_id for q in g} or _near(p.middle, g[0].middle)):
                g.append(p)
                break
        else:
            groups.append([p])
    made = 0
    for g in groups:
        words: set[str] = set().union(*(p.words for p in g))
        middle = np.mean([p.middle for p in g], axis=0)
        surface = blocks.surface_of(middle, words)
        first = by_id[g[0].asset_id]
        stem = (first.id.split("#", 1)[0].rsplit(".", 1)[-1] if "#" in first.id
                else posixpath.basename(first.path).rsplit(".", 1)[0])  # fmt: skip
        name = f"iso_{stem}_{surface}_plain"
        while name in used:
            name += "_2"
        used.add(name)
        spec = {"set": name, "mode": "sides", "surface": surface, "over": "ground",
                "shape": "plain", "role": "GROUND"}  # fmt: skip
        # the ground the variants were made from is the middle, never one of them; a variant of
        # a picture not in the set (Kenney's *Nature*: the turns of a grass whose first turn is
        # an edge of another terrain) is a ground of its own here
        ids = {p.asset_id for p in g}
        made_from = [p for p in g if _variant_of(by_id[p.asset_id]) not in ids]
        chances = _middle_chances(made_from, "sides") if len(made_from) > 1 else {}
        # the variants and the middles of the main one's colour share ``MIDDLE_VARIANTS``
        laid = [k for k, chance in chances.items() if chance > 0]
        laid += [p.asset_id for p in g if _variant_of(by_id[p.asset_id]) in ids]
        if laid:
            each = MIDDLE_VARIANTS / (1.0 - MIDDLE_VARIANTS) / len(laid)
            chances.update({k: round(min(blocks.VARIANT_PROBABILITY, each), 4) for k in laid})
        for p in g:
            peering = {key: -1 for key in PEERING.values()}
            for side in SIDES:
                peering[PEERING[side]] = 0
            facet: dict[str, Any] = {**spec, "peering": peering}
            if p.asset_id in chances:
                facet["probability"] = chances[p.asset_id]
            by_id[p.asset_id].detected[FACET] = facet
        made += 1
    return made


def _whole(piece: Piece) -> bool:
    return piece.sides == frozenset(SIDES) and len(piece.corners) == 4


def _of_tones(row: list[np.ndarray], dark: np.ndarray, light: np.ndarray) -> bool:
    """True when every corner colour of ``row`` is of one of the two tones."""
    return all(
        min(float(np.abs(c - dark).mean()), float(np.abs(c - light).mean())) <= TONE_TOL
        for c in row
    )


def _role(asset: catalog_mod.Asset) -> str:
    return str(catalog_mod.effective(asset).get("role", ""))


def _laid_on(asset: catalog_mod.Asset) -> bool:
    """True for a variant made by laying a patch on a ground (*Lords Of Pain*), not a turn of
    another picture (Miniature Farm's ``planksCornerLeft_E``, another shape than ``_N``)."""
    tags = [str(t) for t in catalog_mod.effective(asset).get("tags") or []]
    return bool(_variant_of(asset)) and not any(t.startswith(catalog_mod.TURN_TAG) for t in tags)


def _variant_of(asset: catalog_mod.Asset) -> str:
    for tag in catalog_mod.effective(asset).get("tags") or []:
        if str(tag).startswith("variant_of:"):
            return str(tag).split(":", 1)[1]
    return ""
