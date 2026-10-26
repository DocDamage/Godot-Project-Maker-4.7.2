"""Packs of other shapes (T17.30), on the synthetic packs drawn in their shapes: isometric sheets
named by their cell, characters in a folder of facings (8 and 16), an object sheet beside a
sheet of loose tiles, a mixed tile sheet, and a licence stated by hand."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen.core import archive, catalog, inventory, licenses, profiles, staging
from rpggen.core.adapters import base, facings, iso_sheets, naming, sheet_parts
from rpggen.core.archive import Cancelled

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture(scope="module")
def packs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    spec = importlib.util.spec_from_file_location(
        "make_synthetic_packs", REPO / "tools" / "make_synthetic_packs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path_factory.mktemp("shapes")
    for name in ("iso_named", "facings", "object_sheet", "mixed_sheet"):
        mod.PACKS[name](out)
    return out


def _catalog(source: Path, previous: catalog.Catalog | None = None) -> tuple[catalog.Catalog, list]:
    opened = archive.open_pack(source, set())
    cat, issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], previous, [], use_cache=False
    )
    return cat, list(issues)


def _asset(cat: catalog.Catalog, suffix: str) -> catalog.Asset:
    found = [a for a in cat.assets if a.id.endswith(suffix)]
    assert len(found) == 1, (suffix, [a.id for a in cat.assets][:40])
    return found[0]


# ------------------------------------------------------------------------------ names


def test_names_state_a_cell_a_facing_and_a_direction() -> None:
    assert naming.named_cell("Floor_Dry_01-256x128") == (256, 128)
    assert naming.named_cell("Overworld - Water - Flat 128x64") == (128, 64)
    assert naming.named_cell("Flat_Brick_01-SE-128x192") == (128, 192)
    assert naming.named_cell("Floor_Dry_01") is None
    assert naming.named_facing("Flat_Brick_01-SE-128x192") == "SE"
    assert naming.named_facing("Stone") == ""
    assert naming.direction_angle("north-east") == 45.0
    assert naming.direction_angle("NEE") == 22.5
    assert naming.direction_angle("S") == 270.0
    assert naming.direction_angle("sideways") is None


# ------------------------------------------------------------------------------ isometric


def test_isometric_sheets_are_read_by_the_cell_their_names_state(packs: Path) -> None:
    cat, issues = _catalog(packs / "iso_named")
    assert not [i for i in issues if i.code == "TILE-010"]
    pack = cat.packs[0]
    assert "isometric:32x16:named" in pack.warnings
    floor = _asset(cat, "floor_grass_01_32x16#c0_0")
    eff = catalog.effective(floor)
    assert eff["usage"] == "iso_tile" and eff["role"] == "GROUND"
    assert eff["footprint"] == [32, 16] and eff["canvas"] == [32, 16] and eff["rise"] == 0
    assert floor.path.startswith(iso_sheets.RENDER_DIR + "/")
    # the empty cell is no tile, the sheet is set aside, the Large copy is the other size
    assert not [a for a in cat.assets if a.id.endswith("floor_grass_01_32x16#c2_0")]
    assert catalog.effective(_asset(cat, "floor_grass_01_32x16"))["role"] == "NONE"
    large = catalog.effective(_asset(cat, "floor_grass_01_64x32#c0_0"))
    assert large["role"] == "NONE" and "unused_because:other_size" in large["tags"]
    assert cat.pack_sizes == {pack.pack_id: 32}


def test_wall_faces_become_four_pieces_along_the_sides_of_a_diamond(packs: Path) -> None:
    cat, _issues = _catalog(packs / "iso_named")
    pieces = {
        side: catalog.effective(_asset(cat, f"flat_stone_01_se_16x24#c0_0_{side}"))
        for side in "nesw"
    }
    for turn, side in enumerate("nesw"):
        assert pieces[side]["edge"] == side and pieces[side]["turn"] == turn
        assert pieces[side]["role"] == "WALL" and pieces[side]["usage"] == "iso_tile"
    # the far sides show the whole height of the wall above their diamond
    assert pieces["n"]["rise"] > pieces["s"]["rise"]
    sets = catalog.turn_sets([a for a in cat.assets if "flat_stone_01_se_16x24#" in a.id])
    first = _asset(cat, "flat_stone_01_se_16x24#c0_0_n").id
    assert set(sets.values()) == {first} and len(sets) == 4
    door = catalog.effective(_asset(cat, "flat_stone_doorway_01_se_16x24#c0_0_s"))
    window = catalog.effective(_asset(cat, "flat_stone_01_windowa_se_16x24#c0_0_e"))
    assert "door" in door["tags"] and "window" in window["tags"]
    thick = catalog.effective(_asset(cat, "thick_stone_01_se_20x26"))
    assert thick["role"] == "NONE" and "unused_because:iso_sheet" in thick["tags"]


def test_a_thick_wall_is_read_as_its_faces_without_the_end_of_the_wall(packs: Path) -> None:
    cat, _issues = _catalog(packs / "iso_named")
    for turn, side in enumerate("nesw"):
        piece = catalog.effective(_asset(cat, f"thick_stone_01_se_20x26#c0_0_{side}"))
        assert (piece["usage"], piece["role"], piece["edge"], piece["turn"]) == (
            "iso_tile", "WALL", side, turn,
        )  # fmt: skip
        assert "thick" in piece["tags"] and piece["canvas"] == [32, 34]
    # a thick face says nothing of the diamond: the pack's stays the one its names give
    assert "isometric:32x16:named" in cat.packs[0].warnings
    mask = np.zeros((26, 20), dtype=bool)
    for x in range(20):  # the end of the wall at the left, its foot running back up
        foot = 25 - (4 - x) // 2 if x < 4 else 25 - (x - 4) // 2
        mask[foot - 12 : foot + 1, x] = True
    assert not iso_sheets._straight_ends(mask)
    flat = np.zeros((24, 16), dtype=bool)
    for x in range(16):
        flat[23 - x // 2 - 10 : 24 - x // 2, x] = True
    assert iso_sheets._straight_ends(flat)


def test_posts_stand_on_the_four_corners_of_their_diamond(packs: Path) -> None:
    cat, _issues = _catalog(packs / "iso_named")
    ids = []
    for turn, corner in enumerate(("nw", "ne", "es", "sw")):
        post = _asset(cat, f"corner_stone_01_se_20x26#c0_0_{corner}")
        eff = catalog.effective(post)
        assert (eff["usage"], eff["role"], eff["post"], eff["turn"]) == (
            "iso_tile", "DECORATION", corner, turn,
        )  # fmt: skip
        assert "post" in eff["tags"] and post.status == "AUTO_DETECTED"
        ids.append(post.id)
    sets = catalog.turn_sets([a for a in cat.assets if a.id in ids])
    assert set(sets.values()) == {ids[0]}


def test_a_town_sheet_whose_corner_is_painted_is_keyed_by_its_border(packs: Path) -> None:
    cat, _issues = _catalog(packs / "iso_named")
    for side in "nesw":
        wall = catalog.effective(_asset(cat, f"isometric_buildings_1_16x24#c0_0_{side}"))
        assert (wall["role"], wall["edge"]) == ("WALL", side)
    picture = np.asarray(
        Image.open(
            packs / "iso_named/Isometric Named - Small/Town/Isometric Buildings 1 - 16x24.png"
        ).convert("RGBA")
    )
    assert int(picture[0, 0, 3]) == 255 and tuple(picture[0, 0, :3]) != (0, 128, 128)
    assert iso_sheets._key_of(picture, None) == (0, 128, 128)
    # a texture with no colour that common has none
    rng = np.random.default_rng(5)
    texture = np.dstack(
        [rng.integers(0, 255, size=(32, 32, 3), dtype=np.uint8), np.full((32, 32), 255, np.uint8)]
    )
    assert iso_sheets._key_of(texture, None) is None


def test_roofs_over_one_diamond_are_cut_from_a_sheet_wider_than_its_cells(packs: Path) -> None:
    cat, _issues = _catalog(packs / "iso_named")
    for col in range(2):
        roof = catalog.effective(_asset(cat, f"town_roofing_38x28#c{col}_0"))
        assert (roof["usage"], roof["role"], roof["footprint"]) == (
            "iso_tile",
            "DECORATION",
            [32, 16],
        )
        assert "roof" in roof["tags"] and "roof" not in roof, "a whole roof of one cell: no shape"
        # the middle of the diamond its eaves cover: as wide as the roof, on its lowest corner
        assert roof["origin"] == [18, 16]
    assert not [a for a in cat.assets if a.id.endswith("town_roofing_38x28#c2_0")]


def test_a_ground_picture_that_tiles_is_cut_on_its_diamond() -> None:
    rng = np.random.default_rng(3)
    noise = rng.integers(40, 60, size=(64, 64, 3), dtype=np.uint8)
    picture = np.dstack([noise, np.full((64, 64), 255, dtype=np.uint8)])
    cut = iso_sheets.diamond_of(picture, iso_sheets.Diamond(64, 32))
    assert cut is not None and cut.shape == (32, 64, 4)
    assert cut[0, 0, 3] == 0 and cut[16, 32, 3] == 255  # the corner is outside, the middle in
    # a picture of two halves does not tile: its seams are hard
    halves = picture.copy()
    halves[:, :32, :3] = 0
    halves[:, 32:, :3] = 250
    assert iso_sheets.diamond_of(halves, iso_sheets.Diamond(64, 32)) is None


# ------------------------------------------------------------------------------ facings


def test_a_folder_of_eight_facings_is_one_character_that_walks_in_them(packs: Path) -> None:
    cat, _issues = _catalog(packs / "facings")
    hero = catalog.effective(_asset(cat, "villagers.n1_villager.rotations.south"))
    names = set(hero["animations"])
    for direction in naming.DIRECTIONS:
        assert f"idle_{direction}" in names and f"walk_{direction}" in names
    assert hero["directions"] == 8 and facings.WALK_FROM_STILL in hero["tags"]
    assert hero["frame"][0] < 24  # cut to what the figure paints
    gif = catalog.effective(_asset(cat, "villagers.n1_villager_showcase"))
    assert gif["role"] == "NONE"


def test_sixteen_facings_give_the_eight_the_game_turns_by(packs: Path) -> None:
    cat, issues = _catalog(packs / "facings")
    knight = _asset(cat, "knight_armed_idle.s.knight_armed_idle_s_270_0_0")
    eff = catalog.effective(knight)
    assert eff["role"] == "PLAYER" and knight.status == "AUTO_DETECTED"
    assert len([n for n in eff["animations"] if n.startswith("walk_")]) == 8
    assert {n.split("_")[0] for n in eff["animations"]} == {"idle", "walk", "attack"}
    assert "facings:16" in eff["tags"]
    assert any(i.code == "ADAPT-008" for i in issues)
    # the armed walk was taken: the variant that attacks
    walk = eff["animations"]["walk_down"]
    assert len(walk["frames"]) == 4
    # the prop in sixteen facings is one decoration
    crate = catalog.effective(_asset(cat, "prop.crate.s.crate_s_270_0_0"))
    assert crate["role"] == "DECORATION" and "walk_down" not in crate["animations"]
    # no picture of a facing folder is an asset of its own
    assert not [a for a in cat.assets if "knight_default_walk" in a.id]


def test_action_folders_name_their_owner() -> None:
    assert facings.is_action_name("rotations", "1._Villager")
    assert facings.is_action_name("knight_special_select", "knight")
    assert facings.is_action_name("knight_default_walk", "knight")
    assert not facings.is_action_name("barrel", "prop")


# ------------------------------------------------------------------------------ sheets


def test_an_object_sheet_is_cut_into_its_things_with_roles_from_its_name(packs: Path) -> None:
    cat, _issues = _catalog(packs / "object_sheet")
    animals = [a for a in cat.assets if "n1_farm_animals#o" in a.id]
    assert len(animals) == 6  # the banner is no animal
    for a in animals:
        eff = catalog.effective(a)
        assert eff["role"] == "ANIMAL" and a.status == "AUTO_DETECTED"
        assert set(eff["animations"]) == {"idle_down", "walk_down"}
    assert catalog.effective(_asset(cat, "n2_barns_and_silos#o40_140"))["role"] == "BUILDING"
    assert catalog.effective(_asset(cat, "n2_barns_and_silos#o200_440"))["role"] == "DECORATION"
    sheet = catalog.effective(_asset(cat, "n1_farm_animals"))
    assert sheet["role"] == "NONE" and "unused_because:object_sheet" in sheet["tags"]
    tiles = catalog.effective(_asset(cat, "n3_grass_tiles#tiles"))
    assert tiles["usage"] == "tiles" and tiles["grid"]["cell"] == [48, 48]


def test_the_ids_of_cut_things_are_the_same_on_every_run(packs: Path) -> None:
    first, _ = _catalog(packs / "object_sheet")
    second, _ = _catalog(packs / "object_sheet")
    assert [a.id for a in first.assets] == [a.id for a in second.assets]
    assert [a.path for a in first.assets] == [a.path for a in second.assets]


def test_a_mixed_tile_sheet_is_sorted_cell_by_cell(packs: Path) -> None:
    cat, _issues = _catalog(packs / "mixed_sheet")
    grass = catalog.effective(_asset(cat, "farm.n1#g0_96"))
    assert grass["usage"] == "tiles" and grass["role"] == "GROUND"
    assert grass["grid"]["cell"] == [48, 48] and grass["size"] == [192, 48]
    house = catalog.effective(_asset(cat, "farm.n1#o192_10"))
    assert house["usage"] == "object" and house["size"][0] > 48  # one thing over its cells
    fence = catalog.effective(_asset(cat, "farm.n1#o336_24"))
    assert fence["size"][0] > 96  # three cells joined
    sheet = catalog.effective(_asset(cat, "farm.n1"))
    assert sheet["role"] == "NONE" and "unused_because:sorted_sheet" in sheet["tags"]
    assert [t.tile_size for t in cat.tilesets] == [[48, 48]]


def test_a_grid_cell_is_the_one_the_art_keeps_to() -> None:
    a = np.zeros((576, 576, 4), dtype=np.uint8)
    for r in range(12):
        for c in range(12):
            a[r * 48 + 4 : r * 48 + 44, c * 48 + 4 : c * 48 + 44] = 200
    assert sheet_parts.grid_cell(a) == 48


def test_islands_keep_close_parts_together() -> None:
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 10:20] = True
    mask[10:20, 23:30] = True  # 3 px apart: one thing
    mask[60:70, 60:70] = True
    found = sheet_parts.islands(mask)
    assert [(x, y, w, h) for x, y, w, h, _own in found] == [(10, 10, 20, 10), (60, 60, 10, 10)]


# ------------------------------------------------------------------------------ cancel


def test_cutting_polls_the_cancel() -> None:
    ctx = base.AdapterContext(is_cancelled=lambda: True)
    with pytest.raises(Cancelled):
        iso_sheets.in_parallel(lambda n: n, [1, 2, 3], ctx)
    assert iso_sheets.in_parallel(lambda n: n * 2, [1, 2, 3], base.AdapterContext()) == [2, 4, 6]


def test_a_cancelled_analysis_stops_in_a_sheet_reader(packs: Path) -> None:
    opened = archive.open_pack(packs / "object_sheet", set())
    inv = inventory.build_inventory(opened)
    ctx = base.AdapterContext(pack_id=inv.pack_id, is_cancelled=lambda: True)
    with pytest.raises(Cancelled):
        sheet_parts.SheetPartsAdapter().extract(inv, opened.root, ctx)


# ------------------------------------------------------------------------------ licence


def _stated(cat: catalog.Catalog) -> catalog.Catalog:
    pack = cat.packs[0]
    stated = dataclasses.replace(
        pack,
        license_files=[],
        license_overrides={"license_id": licenses.COMMERCIAL, "credit": "Art by Synthetic"},
    )
    return dataclasses.replace(cat, packs=[stated])


def test_a_licence_stated_by_hand_is_written_into_the_readme(packs: Path) -> None:
    cat, _issues = _catalog(packs / "mixed_sheet")
    plain = staging.credits_note(cat)
    stated = _stated(cat)
    assert stated.packs[0].licence_stated()
    note = staging.credits_note(stated)
    assert "Art by Synthetic" in note and "the licence its user stated" in note
    assert "your own statement" in note and plain != note
    assert stated.packs[0].effective_license().credit == "Art by Synthetic"


def test_a_stated_licence_is_kept_through_a_new_analysis_and_said_once(packs: Path) -> None:
    cat, _ = _catalog(packs / "mixed_sheet")
    pack_dir = packs / "mixed_sheet"
    licence = pack_dir / "LICENSE.txt"
    text = licence.read_text(encoding="utf-8")
    licence.unlink()
    try:
        again, issues = _catalog(pack_dir, _stated(cat))
    finally:
        licence.write_text(text, encoding="utf-8")
    assert again.packs[0].license_overrides["credit"] == "Art by Synthetic"
    codes = [i.code for i in issues]
    assert "ASSET-036" in codes and "ASSET-021" not in codes


def test_the_profile_carries_a_stated_licence(packs: Path, tmp_path: Path) -> None:
    cat, _ = _catalog(packs / "mixed_sheet")
    stated = _stated(cat)
    opened = archive.open_pack(packs / "mixed_sheet", set())
    inv = inventory.build_inventory(opened)
    profile = profiles.export_profile(stated, stated.packs[0].pack_id, inv, {"title": "Mixed"})
    assert profile["pack_license"] == {"credit": "Art by Synthetic", "license_id": "commercial"}
    # a pack with its licence file exports none
    plain = profiles.export_profile(cat, cat.packs[0].pack_id, inv, {"title": "Mixed"})
    assert "pack_license" not in plain


def _marked(cat: catalog.Catalog, on: bool) -> catalog.Catalog:
    pack = cat.packs[0]
    overrides = {**pack.license_overrides, "ai_generated": True} if on else {}
    return dataclasses.replace(cat, packs=[dataclasses.replace(pack, license_overrides=overrides)])


def test_a_farm_of_a_pack_marked_as_ai_generated_says_so_in_its_readme(packs: Path) -> None:
    """T17.30: a farm whose catalog uses a pack marked as AI-generated art has the README
    section that names it; the same farm with the mark taken off has none."""
    from rpggen.core import config

    cat, _ = _catalog(packs / "mixed_sheet")
    cfg = config.default_for(
        "Marked", [config.pack_ref_from_source(packs / "mixed_sheet", "mixed_sheet")],
        archetype="farm",
    )  # fmt: skip
    template = (REPO / "godot_templates" / "project_files" / staging.README_TEMPLATE).read_text(
        encoding="utf-8"
    )
    marked = staging.render_readme(template, cfg, "1.5.0", "", _marked(cat, True))
    assert "### AI-generated content" in marked and "**mixed_sheet**" in marked
    assert "store page" in marked and "Steam's AI disclosure" in marked
    assert staging.AI_NOTE_CLEAN_UP.split("\n")[0] in marked  # clean it up in Aseprite
    assert staging.AI_NOTE_STILL_DECLARED in marked  # ... and still declare it
    plain = staging.render_readme(template, cfg, "1.5.0", "", _marked(cat, False))
    assert "AI-generated" not in plain
    # a pack marked so but of which the project uses nothing is not named
    unused = _marked(cat, True)
    for asset in unused.assets:
        asset.status = "UNUSED"
    assert staging.ai_note(unused) == ""


def test_the_profile_carries_the_mark_of_ai_generated_art(packs: Path) -> None:
    cat, _ = _catalog(packs / "mixed_sheet")
    opened = archive.open_pack(packs / "mixed_sheet", set())
    inv = inventory.build_inventory(opened)
    marked = _marked(cat, True)
    profile = profiles.export_profile(marked, cat.packs[0].pack_id, inv, {"title": "Mixed"})
    assert profile["pack_license"] == {"ai_generated": True}


def test_a_stated_licence_keeps_the_detected_licence_json() -> None:
    found = licenses.PackLicense("CC0-1.0", "A", "", False, "Credit line")
    assert "credit" not in found.to_json()
    assert licenses.effective({}, {"credit": "x"}).credit == "x"


def test_a_sheet_on_a_grid_of_tiles_is_left_for_the_others(tmp_path: Path) -> None:
    """A pack that says nothing of tiles and whose large picture is one thing is no object
    sheet: fewer islands than a sheet of things has."""
    pack = tmp_path / "one_thing"
    pack.mkdir()
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    img.paste((200, 100, 50, 255), (100, 100, 500, 500))
    img.save(pack / "castle.png")
    cat, _ = _catalog(pack)
    assert all(a.detected_by != sheet_parts.NAME for a in cat.assets)


# ------------------------------------------------------------------------------ cell sheets


def _fishing_pack(root: Path) -> Path:
    """A pack in the shape of Mana Seed's *Fishing Gear*: a sheet of icons and one of objects
    whose names give their cells, a text file naming the icons, and a school of fish that
    swims about its cell."""
    pack = root / "fishing_gear"
    (pack / "school of fish anim").mkdir(parents=True)
    icons = Image.new("RGBA", (48, 32), (0, 0, 0, 0))
    for n, colour in enumerate([(220, 90, 40), (240, 200, 60), (60, 120, 220), (90, 60, 30)]):
        x, y = (n % 3) * 16, (n // 3) * 16
        icons.paste((*colour, 255), (x + 2, y + 3, x + 14, y + 13))
    icons.save(pack / "fishing icons 16x16.png")  # the last cell is empty
    (pack / "Fishing icon reference.txt").write_text(
        "Row 1\n0)\tKoi\n1)\tGoldfish\n2)\tPike\n\nRow 2\n3)\tFishing Rod\n", encoding="utf-8"
    )
    objects = Image.new("RGBA", (48, 64), (0, 0, 0, 0))
    for c in range(3):  # three barrels side by side, touching, and a post under the first
        objects.paste((140, 90, 50, 255), (c * 16, 6, c * 16 + 16, 32))
    objects.paste((110, 70, 40, 255), (6, 34, 10, 64))
    objects.save(pack / "fishing objects 16x32.png")
    school = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for f in range(4):
        school.paste((40, 120, 140, 255), (f * 16 + f * 3, 2 + f, f * 16 + f * 3 + 4, 5 + f))
    school.save(pack / "school of fish anim" / "school of fish, spring 16x16.png")
    return pack


def test_a_small_sheet_is_cut_by_the_cell_its_name_gives(tmp_path: Path) -> None:
    cat, _issues = _catalog(_fishing_pack(tmp_path))
    koi = catalog.effective(_asset(cat, "fishing_icons_16x16#koi"))
    assert koi["role"] == "ITEM" and koi["usage"] == "object" and koi["size"] == [12, 10]
    assert "fish" in koi["tags"]
    assert catalog.effective(_asset(cat, "fishing_icons_16x16#fishing_rod"))["role"] == "TOOL"
    assert not [a for a in cat.assets if "fishing_icons_16x16#c" in a.id]  # every cell named
    barrels = [a for a in cat.assets if "fishing_objects_16x32#" in a.id]
    assert sorted(a.id.rsplit("#", 1)[1] for a in barrels) == ["c0_0", "c0_1", "c1_0", "c2_0"]
    assert all(catalog.effective(a)["role"] == "DECORATION" for a in barrels)
    sheet = catalog.effective(_asset(cat, "fishing_icons_16x16"))
    assert sheet["role"] == "NONE" and "unused_because:cell_sheet" in sheet["tags"]


def test_the_icons_of_a_sheet_are_the_fish_of_the_pond(tmp_path: Path) -> None:
    from rpggen.core import forage_plan

    cat, _issues = _catalog(_fishing_pack(tmp_path))
    names = [f["name"] for f in forage_plan.facts_of(cat)["fish"]]
    assert names == ["goldfish", "koi", "pike"]  # the rod is no catch


def test_a_strip_whose_frames_move_about_is_read_by_its_name(tmp_path: Path) -> None:
    cat, _issues = _catalog(_fishing_pack(tmp_path))
    school = catalog.effective(_asset(cat, "school_of_fish_spring_16x16"))
    assert school["grid"]["cell"] == [16, 16]
    assert [len(a["frames"]) for a in school["animations"].values()] == [4]
    assert school["role"] == "DECORATION"  # fish swimming: nobody to talk to
