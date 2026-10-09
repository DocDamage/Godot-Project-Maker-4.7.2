"""T14.06: the side-view world preview and the generated side-view kit."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from rpggen.core import catalog as catalog_mod
from rpggen.core import map_preview, room_plan, side_kit

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _rooms(count: int = 6, seed: int = 12345, abilities: list[str] | None = None):
    options = {"rooms": count}
    if abilities is not None:
        options["abilities"] = abilities
    return room_plan.plan(options, seed)


def _colours(picture: Image.Image) -> set:
    found = picture.getcolors(maxcolors=picture.width * picture.height)
    return {colour for _count, colour in found or []}


# --------------------------------------------------------------------------- the preview


def test_the_preview_draws_one_cell_per_room() -> None:
    rooms = _rooms()
    rects = map_preview.world_rects(rooms, scale=3)
    assert sorted(rects) == [r["id"] for r in rooms["list"]]
    assert {(w, h) for _l, _t, w, h in rects.values()} == {(120, 69)}, "a pixel times 3 per tile"
    boxes = list(rects.values())
    for i, (left, top, w, h) in enumerate(boxes):
        for other_left, other_top, ow, oh in boxes[i + 1 :]:
            apart = (
                left + w <= other_left
                or other_left + ow <= left
                or top + h <= other_top
                or other_top + oh <= top
            )
            assert apart, "no two rooms overlap"
    picture = map_preview.render_world(rooms, scale=3)
    cols = {r["cell"][0] for r in rooms["list"]}
    rows = {r["cell"][1] for r in rooms["list"]}
    gap = map_preview.SIDE_GAP
    assert picture.size == (gap + len(cols) * (120 + gap), gap + len(rows) * (69 + gap))
    ground = map_preview.SIDE_COLORS["#"] + (255,)
    air = map_preview.SIDE_COLORS["."] + (255,)
    for room in rooms["list"]:
        left, top, _w, _h = rects[room["id"]]
        assert picture.getpixel((left + 2 * 3 + 1, top + 22 * 3 + 1)) == ground, room["id"]
        assert picture.getpixel((left + 5 * 3 + 1, top + 4 * 3 + 1)) == air, room["id"]
    assert picture.getpixel((1, 1)) == map_preview.SIDE_BACKGROUND + (255,)
    # where no room is, the grid is empty
    start = rooms["list"][0]
    left, top, _w, _h = rects[start["id"]]
    assert map_preview.room_at(rooms, left + 10, top + 10) == start["id"]
    assert map_preview.room_at(rooms, 1, 1) is None
    assert map_preview.room_at(rooms, -50, -50) is None


def test_the_rooms_lie_where_the_plan_put_them() -> None:
    rooms = _rooms()
    rects = map_preview.world_rects(rooms, scale=2)
    by_id = {r["id"]: r for r in rooms["list"]}
    for room in rooms["list"]:
        for exit_ in room["exits"]:
            other = by_id[exit_["to"]]
            a, b = rects[room["id"]], rects[other["id"]]
            if exit_["edge"] == "E":
                assert b[0] > a[0] and b[1] == a[1]
            elif exit_["edge"] == "N":
                assert b[1] < a[1] and b[0] == a[0]


def test_markers_exits_and_gate_letters_are_drawn() -> None:
    rooms = _rooms(9, 7, list(room_plan.ABILITIES))
    counts = map_preview.world_markers(rooms)
    assert counts["spawn"] == 1 and counts["station"] == 1 and counts["npc"] == 1
    assert counts["guardian"] == 1 and counts["pickup"] == 4
    assert counts["exit"] == 16, "eight pairs in a chain of nine rooms"
    assert list(counts) == list(map_preview.SIDE_MARKER_ORDER)
    scale = 4
    picture = map_preview.render_world(rooms, scale=scale)
    rects = map_preview.world_rects(rooms, scale)
    colours = {kind: colour + (255,) for kind, colour in map_preview.SIDE_MARKERS.items()}
    start = rooms["list"][0]
    left, top, w, _h = rects[start["id"]]
    x, y = start["spawn"]
    assert picture.getpixel((left + x * scale + 2, top + y * scale + 2)) == colours["spawn"]
    x, y = start["station"]
    assert picture.getpixel((left + x * scale + 2, top + y * scale + 2)) == colours["station"]
    exit_ = start["exits"][0]
    assert picture.getpixel((left + w - 2, top + exit_["cell"][1] * scale + 1)) == colours["exit"]
    # a gate's letter is drawn above the place it stands in: some pixels have the letter colour
    gated = next(r for r in rooms["list"] if r["gates"])
    left, top, w, h = rects[gated["id"]]
    crop = picture.crop((left, top, left + w, top + h))
    assert (255, 235, 150, 255) in _colours(crop)
    plain = map_preview.render_world(_rooms(5, 3, []), scale=scale)
    assert (255, 235, 150, 255) not in _colours(plain), "no gate, no letter"
    assert room_plan.GATE_LETTERS == {
        "double_jump": "J", "dash": "D", "wall_jump": "W", "high_jump": "H", "break_blocks": "B",
    }  # fmt: skip


def test_a_selected_room_gets_a_frame_and_a_clicked_room_is_shown_large() -> None:
    rooms = _rooms()
    chosen = rooms["list"][2]["id"]
    rects = map_preview.world_rects(rooms, scale=3)
    left, top, _w, _h = rects[chosen]
    plain = map_preview.render_world(rooms, scale=3)
    framed = map_preview.render_world(rooms, scale=3, selected=chosen)
    assert plain.getpixel((left - 1, top + 5)) == map_preview.SIDE_EDGE + (255,)
    assert framed.getpixel((left - 1, top + 5)) == (255, 255, 255, 255)
    large = map_preview.render_room(rooms["list"][0], scale=8)
    assert large.size == (320, 184)
    # the one-way platform of the start room, three tiles above the floor
    assert large.getpixel((19 * 8 + 4, 17 * 8 + 4)) == map_preview.SIDE_COLORS["="] + (255,)
    assert large.getpixel((26 * 8 + 4, 19 * 8 + 4))[:3] == map_preview.SIDE_COLORS["^"]


def test_an_empty_plan_gives_a_small_empty_picture() -> None:
    assert map_preview.world_rects({"list": [], "room_size": [40, 23]}) == {}
    assert map_preview.render_world({"list": [], "room_size": [40, 23]}).size == (8, 8)


# --------------------------------------------------------------------------- the side kit


def _catalog(pack: str, tmp_path: Path, monkeypatch) -> catalog_mod.Catalog:
    from rpggen.core import archive, inventory

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    opened = archive.open_pack(SYNTH / pack, set(), pack_id=pack)
    cat, _issues, _generated = catalog_mod.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    return cat


def test_a_top_down_pack_gets_the_whole_kit(tmp_path: Path, monkeypatch) -> None:
    cat = _catalog("basic16", tmp_path, monkeypatch)
    assert side_kit.kinds_in(cat) == set()
    assert side_kit.missing_kinds(cat) == ["one_way", "ladder", "hazard", "breakable"]
    before = len(cat.assets)
    staging = tmp_path / "staging"
    assert side_kit.add(cat, 16, staging) == ["one_way", "ladder", "hazard", "breakable"]
    assert len(cat.assets) == before + 1
    kit = cat.asset(side_kit.KIT_ASSET)
    assert kit is not None and kit.status == "CONFIRMED" and kit.pack_id == side_kit.KIT_PACK
    facets = catalog_mod.effective(kit)
    assert facets["usage"] == "tiles" and facets["role"] == "DECORATION"
    assert facets["tile_overrides"]["0,0"] == {"collision": {"profile": "ONE_WAY"}}
    assert facets["tile_overrides"]["2,0"]["custom"] == {"hazard": True}
    assert facets["tileset"] == "overworld", "it joins the pack's tile set"
    sources = [s["asset"] for t in cat.tilesets if t.name == "overworld" for s in t.sources]
    assert sources == ["basic16.tiles.terrain", side_kit.KIT_ASSET], "the pack's source ids stay"
    image = Image.open(staging / "generated/side_kit/side_kit.png")
    assert image.size == (64, 16) and image.mode == "RGBA"
    assert image.getpixel((2, 1))[3] == 255 and image.getpixel((2, 12))[3] == 0, "a thin plank"
    assert image.getpixel((56, 8))[3] == 255, "a solid block"
    # the kit itself never counts as the pack's own tiles, and adding twice changes nothing
    assert side_kit.missing_kinds(cat) == ["one_way", "ladder", "hazard", "breakable"]
    snapshot = cat.to_json()
    assert side_kit.add(cat, 16, staging) == ["one_way", "ladder", "hazard", "breakable"]
    assert cat.to_json() == snapshot
    catalog_mod.save(cat, tmp_path / "asset_catalog.json")  # it fits the schema


def test_the_kit_is_the_same_bytes_every_time_and_scales_with_the_tile(tmp_path: Path) -> None:
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    side_kit.make_image(16).save(a, format="PNG", optimize=False, compress_level=9)
    side_kit.make_image(16).save(b, format="PNG", optimize=False, compress_level=9)
    assert a.read_bytes() == b.read_bytes()
    assert side_kit.make_image(32).size == (128, 32)
    assert side_kit.make_image(48).size == (192, 48)


def test_a_pack_with_some_kinds_gets_the_kit_for_the_rest(tmp_path: Path, monkeypatch) -> None:
    cat = _catalog("platformer", tmp_path, monkeypatch)
    assert side_kit.kinds_in(cat) == {"one_way", "ladder", "hazard"}
    assert side_kit.missing_kinds(cat) == ["breakable"]
    assert side_kit.add(cat, 16, tmp_path / "staging") == ["breakable"]
    assert cat.asset(side_kit.KIT_ASSET) is not None


def test_a_pack_with_every_kind_gets_no_kit(tmp_path: Path, monkeypatch) -> None:
    from rpggen.core import archive, inventory, profiles

    side = SYNTH.parents[1] / "sample_pack_side"
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    profiles.install_profile(side / "sample_side.rpgprofile.json")
    opened = archive.open_pack(side, set(), pack_id="sample_pack_side")
    cat, _issues, _generated = catalog_mod.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    assert side_kit.kinds_in(cat) == {"one_way", "ladder", "hazard", "breakable"}
    assert side_kit.add(cat, 16, tmp_path / "staging") == []
    assert cat.asset(side_kit.KIT_ASSET) is None
    assert not (tmp_path / "staging").exists()
