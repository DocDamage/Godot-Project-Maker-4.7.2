"""T16.21: names as artists write them, and the files of a pack that are no assets."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, catalog, classifier, explain, inventory
from rpggen.core.adapters import AdapterContext, naming
from rpggen.core.adapters.strips import StripsAdapter


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _picture(path: Path, size: tuple[int, int] = (16, 16), solid: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (40, 160, 60, 255) if solid else (0, 0, 0, 0)).save(path)


def _open(pack_dir: Path):
    pack = archive.open_pack(pack_dir, set())
    return pack, inventory.build_inventory(pack)


def _catalog(pack_dir: Path) -> catalog.Catalog:
    pack, inv = _open(pack_dir)
    cat, _issues, _generated = catalog.assemble([(pack, inv)], None, [])
    return cat


def _asset(cat: catalog.Catalog, name: str) -> catalog.Asset:
    return next(a for a in cat.assets if a.path.endswith("/" + name))


# ----------------------------------------------------------------------------- sizes in a name


@pytest.mark.parametrize(
    ("stem", "rest", "cell", "frames", "split", "directions"),
    [
        ("cow_01_brown_move_down_32x32_4frames", "cow_01_brown_move_down", (32, 32), 4, None, None),
        ("corn_16x32_8frames", "corn", (16, 32), 8, None, None),
        ("default_01_16x16_9split", "default_01", (16, 16), None, 9, None),
        ("hero_walk_4dir", "hero_walk", None, None, None, 4),
        ("hero_8directions_24x32", "hero", (24, 32), None, None, 8),
        ("slime-6frames", "slime", None, 6, None, None),
        ("bird 1frame", "bird", None, 1, None, None),
        ("hero_walk", "hero_walk", None, None, None, None),
        ("map_0x0", "map_0x0", None, None, None, None),  # no size is a size of nothing
        ("tiles_16x16_32x32", "tiles_16x16", (32, 32), None, None, None),  # one of a kind
        ("4frames", "4frames", None, None, None, None),  # a suffix needs a name before it
    ],
)
def test_the_facts_at_the_end_of_a_name(stem, rest, cell, frames, split, directions) -> None:
    facts = naming.name_facts(stem)
    assert (facts.stem, facts.cell, facts.frames, facts.split, facts.directions) == (
        rest,
        cell,
        frames,
        split,
        directions,
    )
    assert facts.any == (rest != stem)


@pytest.mark.parametrize(
    ("raw", "name"),
    [
        ("move_down", "walk_down"),
        ("dead", "death_down"),
        ("sleep_left", "sleep_left"),
        ("fly", "fly_down"),
    ],
)
def test_move_is_walk_and_sleep_dead_and_fly_are_actions(raw: str, name: str) -> None:
    assert naming.normalize_name(raw).name == name
    assert {"sleep", "fly", "death", "walk"} <= naming.CANONICAL_ACTIONS
    assert naming.is_looping("sleep") and naming.is_looping("fly")


def test_a_strip_is_cut_as_its_name_says_not_as_its_gaps_suggest(tmp_path: Path) -> None:
    """Four frames of 32 x 32 with the animal drawn in two of them only: the gaps of the
    picture would give another cut, the name gives the right one."""
    pack = tmp_path / "ranch"
    strip = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
    for frame in (0, 2):
        strip.paste(Image.new("RGBA", (20, 20), (120, 80, 40, 255)), (frame * 32 + 6, 8))
    (pack / "animals").mkdir(parents=True)
    strip.save(pack / "animals" / "cow_01_brown_move_down_32x32_4frames.png")
    strip.save(pack / "animals" / "cow_01_brown_sleep_32x32_4frames.png")
    opened, inv = _open(pack)
    result = StripsAdapter().extract(inv, opened.root, AdapterContext(pack_id=inv.pack_id))
    (cow,) = result.assets
    assert cow.facets["frame"] == [32, 32]
    assert sorted(cow.facets["animations"]) == ["sleep_down", "walk_down"]
    assert cow.facets["animations"]["walk_down"]["frames"] == [[0, 0], [1, 0], [2, 0], [3, 0]]


def test_a_name_that_does_not_fit_its_picture_is_not_believed(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    _picture(pack / "cow_move_32x32_4frames.png", (96, 32))  # three cells, the name says four
    _picture(pack / "corn_16x32_8frames.png", (128, 32))
    _picture(pack / "wheat_growth_16x32_5frames.png", (80, 32))
    _picture(pack / "rock_16x16_1frames.png", (16, 16))  # one frame is no animation
    opened, inv = _open(pack)
    result = StripsAdapter().extract(inv, opened.root, AdapterContext(pack_id=inv.pack_id))
    by_path = {f.path: f.facets for f in result.assets}
    assert "rock_16x16_1frames.png" not in by_path
    corn = by_path["corn_16x32_8frames.png"]  # frames and no action: one looping animation
    assert corn["frame"] == [16, 32] and len(corn["animations"]["idle_down"]["frames"]) == 8
    assert "tags" not in corn
    assert by_path["wheat_growth_16x32_5frames.png"]["tags"] == ["growth"]
    cow = by_path.get("cow_move_32x32_4frames.png")
    assert cow is None or cow["frame"] != [32, 32] or len(cow["animations"]) == 1


# ----------------------------------------------------------------------------- words


@pytest.mark.parametrize(
    ("path", "folders", "names"),
    [
        ("1. Ground & Terrain Tiles.png", [], ["ground", "terrain", "tiles"]),
        (
            "pack/10. Doors, Windows & Architectural Pieces.png",
            ["pack"],
            ["doors", "windows", "architectural", "pieces"],
        ),
        ("BACKGROUD/BACKGROUND (1) .png", ["background"], ["background"]),
        ("Enviroment/tire.png", ["environment"], ["tire"]),
        ("3_walls+cliffs.png", [], ["walls", "cliffs"]),
        ("Haunted \U0001f47b Platforms/2. Platform Tiles \U0001f3ae.png", ["haunted", "platforms"],
         ["platform", "tiles"]),
    ],
)  # fmt: skip
def test_names_as_artists_write_them(path: str, folders: list[str], names: list[str]) -> None:
    assert classifier.tokens(path) == (folders, names)


@pytest.mark.parametrize(
    ("written", "read"),
    [
        ("backgroud", "background"),  # a letter left out
        ("backgrounnd", "background"),  # one too many
        ("backgriund", "background"),  # one wrong
        ("enviroment", "environment"),
        ("backgrxxd", "backgrxxd"),  # two apart: not folded
        ("bckgrnd", "bckgrnd"),
        ("players", "players"),  # a plural is grammar, not a slip
        ("village", "village"),  # a word of its own, not a villager with a letter missing
        ("status", "status"),  # nor a statue
        ("walk", "walk"),  # under six letters: too close to other words
        ("stome", "stome"),
        ("background", "background"),
    ],
)
def test_a_typo_one_letter_away_is_read_as_the_word(written: str, read: str) -> None:
    assert classifier.fold_typo(written) == read


def test_the_why_line_says_what_was_read_for_a_typo(tmp_path: Path) -> None:
    pack = tmp_path / "village"
    _picture(pack / "BACKGROUD" / "sky.png", (480, 270))
    _picture(pack / "tiles" / "grass.png", (64, 64))
    cat = _catalog(pack)
    sky = _asset(cat, "sky.png")
    assert catalog.effective(sky)["role"] == "BACKGROUND"
    assert "backgroud read as background" in explain.why(sky)
    assert "read as" not in explain.why(_asset(cat, "grass.png"))
    assert classifier.folded_typos("BACKGROUD/Enviroment/sky.png") == {
        "backgroud": "background",
        "enviroment": "environment",
    }


# ----------------------------------------------------------------------------- not assets


def test_what_is_no_asset_is_left_out_of_the_inventory(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    _picture(pack / "tiles" / "grass.png")
    for name, data in {
        "tiles/._grass.png": b"\x00\x05\x16\x07",  # a resource fork of macOS
        "Get more packs.html": b"<html></html>",
        "shop.url": b"[InternetShortcut]\n",
        "crops/In development": b"",
        "crops/In development.txt": b"soon",
        "tiles/empty.png": b"",
        "LICENSE": b"",  # empty, and still the licence
        "readme.txt": b"hello",
        "notes.txt": b"hello",
    }.items():
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        (pack / name).write_bytes(data)
    _opened, inv = _open(pack)
    assert [f.path for f in inv.files] == ["LICENSE", "notes.txt", "readme.txt", "tiles/grass.png"]
    assert {s["path"]: s["reason"] for s in inv.skipped} == dict.fromkeys(
        [
            "crops/In development",
            "crops/In development.txt",
            "Get more packs.html",
            "shop.url",
            "tiles/._grass.png",
            "tiles/empty.png",
        ],
        "not_an_asset",
    )
    assert not inv.issues, "an empty picture is not reported as a broken one"


@pytest.mark.parametrize(
    ("path", "wrapper", "reason"),
    [
        ("test.png", "", classifier.UNUSED_GUIDE_PICTURE),
        ("Preview 2.png", "", classifier.UNUSED_GUIDE_PICTURE),
        ("pack_mockup.png", "", classifier.UNUSED_GUIDE_PICTURE),
        ("Village/test.png", "Village", classifier.UNUSED_GUIDE_PICTURE),  # the archive's folder
        ("Enviroment/Grid Slots.png", "", classifier.UNUSED_GUIDE_PICTURE),  # nothing but such
        ("PREVIEW/Preview (11) .png", "", classifier.UNUSED_PREVIEW_FOLDER),
        ("art/screenshots/town.png", "", classifier.UNUSED_PREVIEW_FOLDER),
        ("tiles/test_tiles.png", "", None),  # a word among others, in a folder: game art
        ("ui/grid_panel.png", "", None),
        ("characters/template_hero.png", "", None),
        ("grass.png", "", None),
        ("previews_of_summer/town.png", "", None),  # the folder's whole name decides
    ],
)
def test_previews_and_guides_are_told_from_game_art(path, wrapper, reason) -> None:
    assert classifier.not_game_art(path, wrapper) == reason


def test_a_preview_is_unused_says_why_and_comes_back_with_one_choice(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    _picture(pack / "tiles" / "grass.png", (64, 64))
    _picture(pack / "test.png", (64, 64))
    _picture(pack / "PREVIEW" / "town.png", (480, 270))
    cat = _catalog(pack)
    assert _asset(cat, "grass.png").status != "UNUSED"
    for name, words in (
        ("test.png", "preview, test or layout guide"),
        ("town.png", "preview folder"),
    ):
        asset = _asset(cat, name)
        assert asset.status == "UNUSED" and catalog.effective(asset)["role"] == "NONE"
        assert explain.why(asset).startswith("unused: ") and words in explain.why(asset)
    # it is in the catalog, not left out: a role chosen in the audit brings it back
    test = _asset(cat, "test.png")
    test.overrides["role"] = "GROUND"
    test.status = catalog.recompute_status(test)
    assert test.status == "CONFIRMED" and explain.why(test) == "You chose this role."
    again, _issues, _generated = catalog.assemble([_open(pack)], cat, [])
    assert _asset(again, "test.png").status == "CONFIRMED"
    assert catalog.effective(_asset(again, "test.png"))["role"] == "GROUND"


# ----------------------------------------------------------------------------- numbered sheets


_SHEETS = 0


def _sheet(path: Path, size: tuple[int, int], cell: int) -> None:
    """A sheet of opaque tiles in two colours, so that its grid can be measured; every sheet
    in a colour of its own, so that none is taken for a copy of another."""
    global _SHEETS
    _SHEETS += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            shade = 60 + 90 * (((x // cell) + (y // cell)) % 2)
            tile = Image.new("RGBA", (cell, cell), (shade, (_SHEETS * 37) % 256, 60, 255))
            img.paste(tile, (x, y))
    img.save(path)


def test_a_sheet_named_by_a_number_takes_its_words_from_its_folder(tmp_path: Path) -> None:
    pack = tmp_path / "bundle"
    town = pack / "Medieval Fantasy Town Pixel Art Tileset Pack"
    for n in (1, 2, 3, 5, 8):  # a gap in the numbers is nothing
        _sheet(town / f"{n}.png", (768, 768), 96 if n == 2 else 48)
    _sheet(town / "ww1" / "4.png", (1024, 1024), 32)  # one folder down
    _sheet(pack / "Haunted Manor Tileset" / "1.png", (2048, 2048), 64)
    _picture(pack / "Haunted Manor Tileset" / "2.png", (100, 100))  # small: not a sheet
    _sheet(pack / "Characters" / "1.png", (512, 512), 32)  # no folder says tile set
    cat = _catalog(pack)
    town_sheets = [a for a in cat.assets if "/Medieval" in a.path and "/ww1/" not in a.path]
    assert len(town_sheets) == 5, "five numbered sheets are five tile sheets, not one animation"
    for asset in town_sheets:
        eff = catalog.effective(asset)
        assert eff["usage"] == "tiles" and eff["grid"]["cell"] == [48, 48], asset.path
        assert eff["tags"] == ["fantasy", "medieval", "town"]
        assert asset.status == "NEEDS_REVIEW"
        assert explain.why(asset).startswith("the file name is only a number")
    deeper = catalog.effective(_asset(cat, "ww1/4.png"))
    assert deeper["grid"]["cell"] == [32, 32] and deeper["tags"] == [
        "fantasy",
        "medieval",
        "town",
        "ww1",
    ]
    manor = catalog.effective(_asset(cat, "Haunted Manor Tileset/1.png"))
    assert manor["usage"] == "tiles" and manor["tags"] == ["haunted", "manor"]
    assert manor["grid"]["cell"] in ([64, 64], [32, 32])  # measured, else the usual tile
    assert "tags" not in catalog.effective(_asset(cat, "Haunted Manor Tileset/2.png"))
    assert "only a number" not in explain.why(_asset(cat, "Characters/1.png")) or (
        catalog.effective(_asset(cat, "Characters/1.png"))["usage"] == "tiles"
    )
    assert "tags" not in catalog.effective(_asset(cat, "Characters/1.png"))


def test_a_folder_of_a_bundle_added_on_its_own_is_named_by_the_pack(tmp_path: Path) -> None:
    pack = tmp_path / "Modern Gym Fitness Center Pixel Art Tileset Pack"
    _sheet(pack / "1.png", (768, 768), 48)
    cat = _catalog(pack)
    eff = catalog.effective(cat.assets[0])
    assert eff["usage"] == "tiles" and eff["grid"]["cell"] == [48, 48]
    assert eff["tags"] == ["center", "fitness", "gym", "modern"]


def test_the_words_of_a_folder(tmp_path: Path) -> None:
    path = "Medieval Fantasy Town Pixel Art Tileset Pack/tileset-1/3.png"
    assert classifier.is_numbered_name(path) and classifier.is_numbered_name("a/ 12 .png")
    assert not classifier.is_numbered_name("a/tile12.png") and not classifier.is_numbered_name(
        "a/B-10.png"
    )
    assert classifier.folder_words(path)[:2] == ["tileset", "medieval"]  # the nearest folder first
    assert classifier.folder_tags(path) == ["medieval", "fantasy", "town"]
    assert classifier.folder_tags("3.png", "abandoned hospital tileset") == [
        "abandoned",
        "hospital",
    ]


# ----------------------------------------------------------------------------- copies, photos


@pytest.mark.parametrize(
    ("name", "base"),
    [
        ("B-10_\u526f\u672c.jpg", "B-10"),  # "copy", as a Chinese Windows names one
        ("tree - Copy.png", "tree"),
        ("tree (copy).png", "tree"),
        ("tree_copy.png", "tree"),
        ("TREE COPY.png", "TREE"),
        ("house (2)_\u526f\u672c.png", "house (2)"),
        ("tree.png", None),
        ("tree_2.png", None),
        ("copy.png", None),  # a name of its own
        ("bush_copy.png", None),  # no bush beside it
        ("caf\u00e9.png", None),
    ],
)
def test_a_copy_is_told_by_its_name_and_the_file_beside_it(name: str, base: str | None) -> None:
    stems = {("town", "b-10"), ("town", "tree"), ("town", "house (2)"), ("other", "bush")}
    assert classifier.copy_of(f"Town/{name}", stems) == base


def test_a_copy_is_unused_and_a_jpg_is_never_a_tile_sheet(tmp_path: Path) -> None:
    pack = tmp_path / "Wild West Pixel Art Tileset"
    _sheet(pack / "B-10.png", (768, 768), 48)
    Image.new("RGB", (768, 768), (90, 60, 30)).save(pack / "B-10_\u526f\u672c.jpg")
    Image.new("RGB", (768, 768), (30, 60, 90)).save(pack / "7.jpg")  # a number, a tile-set folder
    Image.new("RGB", (64, 48), (30, 60, 90)).save(pack / "badge.jpg")
    cat = _catalog(pack)
    copy = _asset(cat, "B-10_\u526f\u672c.jpg")
    assert copy.status == "UNUSED" and "copy of the file beside it" in explain.why(copy)
    assert catalog.effective(_asset(cat, "B-10.png"))["usage"] == "tiles"
    photo = catalog.effective(_asset(cat, "7.jpg"))
    assert photo["usage"] == "background" and "grid" not in photo
    assert catalog.effective(_asset(cat, "badge.jpg"))["usage"] == "sprite"
