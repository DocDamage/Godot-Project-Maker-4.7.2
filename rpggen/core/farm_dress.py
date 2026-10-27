"""What a farming pack lacks of the dress of a game, made from its own pictures (T17.33).

LimeZu's *Modern Farm* has a farm, a village and its people, but no window frames, no faces for
the dialogue and no walls for a map's border: a user had to take rpggen's magenta stand-ins for
them. They are made here from what the pack does have, once the catalog is put together:

* **Portraits**: the face of each of the pack's people (the player and the villagers), cut from
  the first frame it stands in (the upper part of what it paints, the head) and enlarged by a
  whole number, a ``PORTRAIT`` each (``portrait_of:<asset>``).
* **Walls**: the pack's fences, a ``WALL`` sheet for the border of its maps.
* **The interface**: a nine-slice frame drawn in the pack's own colours (the darkest colour its
  people are outlined in, and the wood of its things), a ``UI`` asset the theme is made from.

Only a farming pack without such a thing gets one, and only what is made of its own pixels: a
pack with portraits, walls or a frame keeps its own.
"""

from __future__ import annotations

import hashlib
import posixpath
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

PORTRAIT_DIR = "generated/farm_dress"
PORTRAIT_SIZE = 48  # the smallest side a portrait is enlarged to (a whole multiple)
PORTRAIT_TAG = "portrait_of:"
DRESS_TAG = "farm_dress"
CONFIDENCE = 0.8
PEOPLE = ("PLAYER", "NPC")
UNUSED = ("UNUSED", "MISSING")


def _file_of(asset: Any, roots: dict[str, Path], pack_roots: dict[str, str],
             generated: dict[str, str]) -> Path | None:  # fmt: skip
    if asset.path in generated:
        return Path(generated[asset.path])
    root = pack_roots.get(asset.pack_id, "")
    local = roots.get(asset.pack_id)
    if local is None or not asset.path.startswith(root + "/"):
        return None
    return local / asset.path[len(root) + 1 :]


def _first_frame(
    facets: dict[str, Any], file: Path, generated: dict[str, str]
) -> np.ndarray | None:
    anims = facets.get("animations") or {}
    anim = (anims.get("idle_down") or next(iter(anims.values()), None)) if anims else None
    frame = facets.get("frame") or facets.get("size")
    if not frame:
        return None
    fw, fh = int(frame[0]), int(frame[1])
    source = anim.get("source") if isinstance(anim, dict) else None
    if isinstance(source, str) and source in generated:
        file = Path(generated[source])  # an animation drawn into a strip of its own
    try:
        with Image.open(file) as im:
            rgba = np.asarray(im.convert("RGBA"))
    except (OSError, ValueError):
        return None
    col, row = 0, 0
    if isinstance(anim, dict) and anim.get("frames"):
        col, row = (int(v) for v in anim["frames"][0])
    grid = facets.get("grid") or {}
    margin = grid.get("margin") or [0, 0]
    sep = grid.get("separation") or [0, 0]
    x0 = int(margin[0]) + col * (fw + int(sep[0]))
    y0 = int(margin[1]) + row * (fh + int(sep[1]))
    part = rgba[y0 : y0 + fh, x0 : x0 + fw]
    return part if part.shape[0] == fh and part.shape[1] == fw else None


def face_of(frame: np.ndarray) -> np.ndarray | None:
    """The head of a figure standing in a frame: the upper part of what it paints, as wide as
    the figure and about as high as wide."""
    mask = frame[:, :, 3] >= 64
    ys, xs = np.nonzero(mask)
    if ys.size < 16:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    w = x1 - x0 + 1
    h = min(y1 - y0 + 1, max(4, int(round(w * 1.0))), max(4, (y1 - y0 + 1) * 11 // 20))
    head = frame[y0 : y0 + h, x0 : x1 + 1]
    return head if head.size else None


def _enlarged(picture: np.ndarray) -> Image.Image:
    im = Image.fromarray(picture)
    k = max(1, -(-PORTRAIT_SIZE // max(1, min(im.width, im.height))))
    return im.resize((im.width * k, im.height * k), Image.Resampling.NEAREST)


def _save(picture: Image.Image, work: Path) -> tuple[str, Path, str]:
    pixels = np.asarray(picture)
    digest = hashlib.sha256(pixels.tobytes() + repr(pixels.shape).encode()).hexdigest()
    out = work / f"{digest[:24]}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.is_file():
        picture.save(out, format="PNG", optimize=False)
    return f"{PORTRAIT_DIR}/{out.name}", out, digest


def dress(
    catalog: Any,
    farm_ids: set[str],
    roots: dict[str, Path],
    generated: dict[str, str],
    work_dir: Path | None,
) -> dict[str, str]:
    """Portraits, walls and a frame for the farming packs that lack them (see the module's
    text). Returns the generated files (project path -> file)."""
    from rpggen import paths
    from rpggen.core.catalog import Asset, CatalogPack, effective
    from rpggen.core.terrain import GENERATED_PACK, rpgmaker_a2

    out: dict[str, str] = {}
    if not farm_ids:
        return out
    work = (work_dir or paths.cache_dir()) / "farm_dress"
    pack_roots = {p.pack_id: p.root for p in catalog.packs}
    have = {
        effective(a).get("role")
        for a in catalog.assets
        if a.status not in UNUSED and a.pack_id != GENERATED_PACK
    }
    added: list[Any] = []
    people = [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.pack_id in farm_ids
        and effective(a).get("role") in PEOPLE
        and effective(a).get("usage") == "sprite"
        and a.status not in UNUSED
    ]
    if "PORTRAIT" not in have:
        for person in people:
            facets = effective(person)
            file = _file_of(person, roots, pack_roots, {**generated, **out})
            if file is None:
                continue
            frame = _first_frame(facets, file, {**generated, **out})
            head = face_of(frame) if frame is not None else None
            if head is None:
                continue
            face = _enlarged(head)
            rel, local, digest = _save(face, work)
            out[rel] = str(local)
            name = person.id.rsplit(".", 1)[-1]
            added.append(Asset(f"{GENERATED_PACK}.portrait_{name}", GENERATED_PACK, rel, digest,
                               "image", "AUTO_DETECTED",
                               {"usage": "portrait", "role": "PORTRAIT",
                                "size": [face.width, face.height],
                                "tags": [DRESS_TAG, PORTRAIT_TAG + person.id]},
                               {}, "farm_dress", CONFIDENCE))  # fmt: skip
    if "WALL" not in have:
        for asset in catalog.assets:
            facets = asset.detected
            if asset.pack_id not in farm_ids or asset.status in UNUSED:
                continue
            tags = set(facets.get("tags") or [])
            stem = posixpath.basename(asset.path).casefold()
            if facets.get("usage") == "tiles" and ("fence" in tags or "fence" in stem):
                facets["role"] = "WALL"
                facets["tags"] = sorted(tags | {DRESS_TAG})
                asset.confidence = max(float(asset.confidence or 0.0), CONFIDENCE)
                break
    if "UI" not in have and people:
        frame_ui = _frame_in_colours(people, roots, pack_roots, {**generated, **out})
        if frame_ui is not None:
            rel, local, digest = _save(frame_ui, work)
            out[rel] = str(local)
            added.append(Asset(f"{GENERATED_PACK}.farm_frame", GENERATED_PACK, rel, digest,
                               "image", "AUTO_DETECTED",
                               {"usage": "ui", "role": "UI", "nine_slice": [6, 6, 6, 6],
                                "size": [frame_ui.width, frame_ui.height],
                                "tags": [DRESS_TAG]},
                               {}, "farm_dress", CONFIDENCE))  # fmt: skip

    if added:
        catalog.assets.extend(added)
        if not any(p.pack_id == GENERATED_PACK for p in catalog.packs):
            catalog.packs.append(
                CatalogPack(GENERATED_PACK, "0" * 64, rpgmaker_a2.TERRAIN_DIR, [], [], None, [])
            )
    return out


HOUSE_WORDS = {"barn": "barn", "coop": "coop", "henhouse": "coop", "hencoop": "coop"}
NOT_A_HOUSE = frozenset({"door", "railing", "inside", "interior", "sign", "roof", "wall", "fence",
                         "window", "silo", "trough", "floor"})  # fmt: skip
FOOTPRINT_FRACTION = 0.3
MIN_HOUSE = 32  # px each way: a smaller picture of a barn is an icon


FARMHOUSE_WORDS = frozenset({"house", "houses", "home", "cottage", "farmhouse", "cabin"})
NOT_A_FARMHOUSE = frozenset({"dog", "doghouse", "bird", "birdhouse", "npcs", "npc", "kit"})
ONE_THING = 0.85  # of what a picture paints, its largest piece: one thing, not a sheet


def _one_thing(asset: Any, roots: dict[str, Path], pack_roots: dict[str, str]) -> bool:
    """True when a picture is one thing: its largest piece of touching painted pixels is most of
    what it paints."""
    file = _file_of(asset, roots, pack_roots, {})
    if file is None:
        return False
    try:
        with Image.open(file) as im:
            alpha = np.asarray(im.convert("RGBA"))[:, :, 3] >= 64
    except (OSError, ValueError):
        return False
    if not alpha.any():
        return False
    from rpggen.core.figures import _islands_in

    # looked at in blocks of 4 px: the pieces of a sheet lie further apart than that
    h, w = alpha.shape
    alpha = alpha[: h // 4 * 4, : w // 4 * 4].reshape(h // 4, 4, w // 4, 4).any(axis=(1, 3))

    sizes = [size for size, _share in _islands_in(alpha, np.zeros_like(alpha))]
    return max(sizes) >= ONE_THING * int(alpha.sum())


TREE_WORDS = frozenset({"tree", "trees", "pine", "oak", "birch", "maple", "mahogany"})
NOT_A_TREE = frozenset(
    {"effects", "effect", "fx", "animation", "trunk", "trunks", "root", "roots",
     "shandow", "leafs", "leaves", "water", "stump", "copiar", "old"}
)  # fmt: skip


def _pieces(alpha: np.ndarray, step: int = 2) -> list[tuple[int, int, int, int]]:
    """The boxes (x0, y0, x1, y1, end exclusive) of the pieces of touching painted pixels of a
    mask, looked at in blocks of ``step`` px."""
    h, w = alpha.shape
    small = alpha[: h // step * step, : w // step * step]
    small = small.reshape(h // step, step, w // step, step).any(axis=(1, 3))
    sh, sw = small.shape
    seen = np.zeros_like(small)
    out: list[tuple[int, int, int, int]] = []
    for sy, sx in zip(*np.nonzero(small), strict=True):
        if seen[sy, sx]:
            continue
        stack = [(int(sy), int(sx))]
        seen[sy, sx] = True
        x0, y0, x1, y1 = int(sx), int(sy), int(sx), int(sy)
        while stack:
            y, x = stack.pop()
            x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < sh and 0 <= nx < sw and small[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((x0 * step, y0 * step, (x1 + 1) * step, (y1 + 1) * step))
    return out


def trees(catalog: Any, farm_ids: set[str], roots: dict[str, Path]) -> None:
    """A farming pack's trees drawn a season beside the other (T17.33: *Farm RPG*'s
    ``Tree/Common/Shadow/Pine Tree.png``, four pines of the four seasons in a row): the first
    of each picture, its spring tree, is a ``DECORATION`` tagged ``tree`` the farm plants
    instead of drawing one. A picture of one tree is one already."""
    import re

    from rpggen.core.catalog import SheetObject

    pack_roots = {p.pack_id: p.root for p in catalog.packs}
    have = {o.id for o in catalog.objects}
    for asset in sorted(catalog.assets, key=lambda a: a.id):
        if asset.pack_id not in farm_ids or "#" in asset.id or asset.kind != "image":
            continue
        said = {w for w in re.split(r"[^a-z]+", asset.path.casefold()) if w}
        if not said & TREE_WORDS or said & NOT_A_TREE or asset.detected.get("animations"):
            continue
        file = _file_of(asset, roots, pack_roots, {})
        if file is None:
            continue
        try:
            with Image.open(file) as im:
                alpha = np.asarray(im.convert("RGBA"))[:, :, 3] >= 64
        except (OSError, ValueError):
            continue
        # the trees of a picture (side by side or one under the other): the first large piece
        # of touching painted pixels in reading order is the first season's
        pieces = [b for b in _pieces(alpha) if b[2] - b[0] >= 16 and b[3] - b[1] >= 16]
        if not pieces:
            continue
        x0, y0, x1, y1 = min(pieces, key=lambda b: (b[1] // 32, b[0]))
        region = [x0, y0, x1 - x0, y1 - y0]
        object_id = f"{asset.id}#tree"
        if object_id in have:
            continue
        fh = max(1, region[3] // 6)
        catalog.objects.append(
            SheetObject(
                object_id,
                asset.id,
                posixpath.splitext(posixpath.basename(asset.path))[0],
                "DECORATION",
                region,
                [region[2] // 2, region[3] - 1],
                [region[2] // 3, region[3] - fh, max(1, region[2] // 3), fh],
                {
                    "profile": "CUSTOM",
                    "polygon": [
                        [region[2] // 3, region[3] - fh],
                        [2 * region[2] // 3, region[3] - fh],
                        [2 * region[2] // 3, region[3]],
                        [region[2] // 3, region[3]],
                    ],
                },
                ["tree", DRESS_TAG],
            )  # fmt: skip
        )


def animal_houses(catalog: Any, farm_ids: set[str], roots: dict[str, Path] | None = None) -> None:
    """A farming pack's own barn and coop (T17.33: *Modern Farm*'s ``Barn_Small_16x16.png`` and
    ``Chicken_Coop_16x16.png``): a single picture named so, large enough, becomes a building
    tagged ``barn`` or ``coop`` where no building of the packs is (the many barns of its sheet
    were set aside, and the single pictures as copies of its cells), so the farm stands its own
    barn and coop instead of drawing them."""
    import re

    from rpggen.core.catalog import SheetObject

    tagged = {
        t
        for o in catalog.objects
        if o.role == "BUILDING" and o.status != "UNUSED"
        for t in o.tags
        if t in ("barn", "coop")
    }
    pack_roots = {p.pack_id: p.root for p in catalog.packs}
    for asset in sorted(catalog.assets, key=lambda a: a.id):
        if asset.pack_id not in farm_ids or asset.kind != "image":
            continue
        if "#" in asset.id:
            # a house cut from a sheet of things that its picture says is one (T17.33)
            if "house" in (asset.detected.get("tags") or []) and asset.status != "UNUSED":
                _add_house(catalog, asset, SheetObject)
            continue
        stem = posixpath.splitext(posixpath.basename(asset.path))[0]
        folder = posixpath.basename(posixpath.dirname(asset.path))
        words = {w for w in re.split(r"[^a-z]+", stem.casefold()) if w}
        folder_words = {w for w in re.split(r"[^a-z]+", folder.casefold()) if w}
        kinds = {HOUSE_WORDS[w] for w in words if w in HOUSE_WORDS}
        if not kinds and (words | folder_words) & FARMHOUSE_WORDS:
            # T17.33: a whole house of the pack (*Farm RPG*'s ``Houses/1.png``): the farmhouse
            kinds = {"house"}
        if len(kinds) != 1 or (words | folder_words) & NOT_A_HOUSE:
            continue
        kind = kinds.pop()
        if (kind in tagged and kind != "house") or asset.path.casefold().endswith(".gif"):
            continue
        if kind == "house" and (words | folder_words) & NOT_A_FARMHOUSE:
            continue
        if kind == "house" and asset.detected.get("usage") == "tiles":
            continue  # a tile set of walls and roofs to build houses of (``Tileset House.png``)
        if kind == "house" and (roots is None or not _one_thing(asset, roots, pack_roots)):
            continue  # a kit of walls and roofs (``Tiny House.png``), or several houses
        if any(
            str(t).startswith("unused_because:other_size") for t in asset.detected.get("tags") or []
        ):
            continue  # the pack drawn in another size: its own size's barn is the one
        if {"unused_because:shadow", "pack_manifest"} & set(asset.detected.get("tags") or []):
            # a house's shadow is no house, and a picture its pack's manifest says what it is
            # (Gridwright's ``cottage_left``, a BUILDING already) is that (2026-10-26)
            continue
        size = asset.detected.get("size") or [0, 0]
        w, h = int(size[0]), int(size[1])
        if w < MIN_HOUSE or h < MIN_HOUSE:
            continue
        fh = max(1, round(h * FOOTPRINT_FRACTION))
        fy = h - fh
        # the picture stays what it was read as (a copy of a sheet's cell set aside, a
        # decoration): its object is the farm's building, not the village's starter
        catalog.objects.append(
            SheetObject(
                f"{asset.id}#{kind}",
                asset.id,
                stem,
                "BUILDING",
                [0, 0, w, h],
                [w // 2, h - 1],
                [0, fy, w, fh],
                {"profile": "CUSTOM", "polygon": [[0, fy], [w, fy], [w, h], [0, h]]},
                [kind, DRESS_TAG],
            )  # fmt: skip
        )
        tagged.add(kind)


def _add_house(catalog: Any, asset: Any, sheet_object: Any) -> None:
    """The building object of a whole picture of a house (``{asset}#house``)."""
    size = asset.detected.get("size") or [0, 0]
    w, h = int(size[0]), int(size[1])
    if w < MIN_HOUSE or h < MIN_HOUSE:
        return
    fh = max(1, round(h * FOOTPRINT_FRACTION))
    fy = h - fh
    stem = asset.id.rsplit("#", 1)[-1]
    catalog.objects.append(
        sheet_object(
            f"{asset.id}#house",
            asset.id,
            stem,
            "BUILDING",
            [0, 0, w, h],
            [w // 2, h - 1],
            [0, fy, w, fh],
            {"profile": "CUSTOM", "polygon": [[0, fy], [w, fy], [w, h], [0, h]]},
            ["house", DRESS_TAG],
        )  # fmt: skip
    )


def _frame_in_colours(
    people: list[Any], roots: dict[str, Path], pack_roots: dict[str, str], generated: dict[str, str]
) -> Image.Image | None:
    """A 24 px nine-slice frame: a border of the darkest colour the people are drawn with, a
    lighter edge inside it and a body of their middle tone, darkened to read text on."""
    from rpggen.core.catalog import effective

    colours: list[np.ndarray] = []
    for person in people[:4]:
        file = _file_of(person, roots, pack_roots, generated)
        frame = _first_frame(effective(person), file, generated) if file is not None else None
        if frame is not None:
            colours.append(frame[frame[:, :, 3] >= 128][:, :3])
    if not colours:
        return None
    px = np.concatenate(colours).astype(np.float32)
    value = px.max(axis=1)
    dark = px[value <= np.percentile(value, 15)].mean(axis=0)
    mid = px[(value > np.percentile(value, 40)) & (value <= np.percentile(value, 70))]
    body = (mid.mean(axis=0) if len(mid) else px.mean(axis=0)) * 0.45
    light = np.minimum(255.0, body * 1.6 + 30)
    size = 24
    a = np.zeros((size, size, 4), np.uint8)
    a[:, :, :3] = body.astype(np.uint8)
    a[:, :, 3] = 235
    a[2:-2, 2:-2][:2, :, :3] = light.astype(np.uint8)
    a[2:-2, 2:-2][-2:, :, :3] = light.astype(np.uint8)
    a[2:-2, 2:4, :3] = light.astype(np.uint8)
    a[2:-2, -4:-2, :3] = light.astype(np.uint8)
    for edge in (a[:2], a[-2:], a[:, :2], a[:, -2:]):
        edge[:, :, :3] = dark.astype(np.uint8)
        edge[:, :, 3] = 255
    return Image.fromarray(a, "RGBA")
