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
