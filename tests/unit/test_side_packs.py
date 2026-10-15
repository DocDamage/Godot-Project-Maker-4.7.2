"""Real side-view packs (T17.32) on the synthetic packs of each shape: a numbered tile sheet with
a sheet of characters (``side_numbered_platformer``), ground pieces named by their place
(``side_named_platformer``), a character as frames in action folders with strips and previews
beside it (``side_action_frames``) and a stage of layered backgrounds (``side_layered_platformer``);
and the readers' parts one by one."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen.core import archive, catalog, classifier, inventory, licenses, side_packs, side_tiles
from rpggen.core.adapters import action_frames
from rpggen.errors import IssueList

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(name: str, tmp_path: Path) -> tuple[catalog.Catalog, IssueList, dict[str, str]]:
    opened = archive.open_pack(SYNTH / name, set())
    inv = inventory.build_inventory(opened)
    return catalog.assemble([(opened, inv)], None, [], work_dir=tmp_path / "work")


def _asset(cat: catalog.Catalog, suffix: str) -> catalog.Asset:
    found = [a for a in cat.assets if a.id.endswith(suffix)]
    assert found, suffix
    return found[0]


# ------------------------------------------------------------------ a numbered tile sheet


def test_the_cells_of_a_numbered_sheet_are_read_from_their_pictures(tmp_path: Path) -> None:
    cat, issues, _gen = _assemble("side_numbered_platformer", tmp_path)
    sheet = _asset(cat, "tilemap.tilemap_packed")
    assert sheet.status == "AUTO_DETECTED"
    over = sheet.detected["tile_overrides"]
    # the grass-topped block: its top and ends, its inside, its faces and its bottom
    peering = {k: v["terrain"]["peering"] for k, v in over.items() if "terrain" in v}
    assert peering["1,0"]["top_side"] == -1 and peering["1,0"]["bottom_side"] == 0
    assert peering["0,0"]["left_side"] == -1 and peering["0,0"]["right_side"] == 0
    assert peering["2,0"]["right_side"] == -1 and peering["2,0"]["left_side"] == 0
    assert all(
        peering["1,1"][s] == 0 for s in ("top_side", "right_side", "bottom_side", "left_side")
    )
    assert peering["1,2"]["bottom_side"] == -1
    kinds = {k: v["custom"]["side"] for k, v in over.items()}
    assert [kinds[f"{x},0"] for x in (3, 4, 5)] == ["one_way"] * 3
    assert over["3,0"]["collision"] == {"profile": "ONE_WAY"}
    assert kinds["6,0"] == "ladder" and over["6,0"]["collision"] == {"profile": "LADDER"}
    assert kinds["7,0"] == "spikes" and over["7,0"]["custom"]["hazard"] is True
    assert kinds["3,1"] == "water" and kinds["4,1"] == "coin"
    assert "5,1" not in over and "6,1" not in over, "a key and a door stay unread"
    assert any(i.code == "TILE-016" and sheet.id in i.message for i in issues)
    (tileset,) = [t for t in cat.tilesets if any(s["asset"] == sheet.id for s in t.sources)]
    (side,) = [s for s in tileset.terrain_sets if s["sheet"] == sheet.id]
    assert side["shape"] == "side" and side["mode"] == "sides" and side["surface"] == "grass"


def test_a_sheet_of_characters_is_characters(tmp_path: Path) -> None:
    cat, _issues, _gen = _assemble("side_numbered_platformer", tmp_path)
    sheet = _asset(cat, "tilemap.tilemap_characters_packed")
    assert sheet.status == "UNUSED"
    assert "unused_because:characters_cut" in sheet.detected["tags"]
    cut = [a for a in cat.assets if a.id.startswith(sheet.id + "#ch")]
    assert len(cut) == 9
    assert [a.detected["role"] for a in cut].count("PLAYER") == 1
    first = _asset(cat, "#ch0_0")
    assert first.detected["role"] == "PLAYER" and first.detected["frame"] == [24, 24]
    assert first.detected["animations"]["walk_down"]["frames"] == [[0, 0], [1, 0]]
    straddling = _asset(cat, "#ch8_0")  # its second frame is the first cell of the next row
    assert straddling.detected["animations"]["walk_down"]["frames"] == [[8, 0], [0, 1]]
    assert not any(
        t.sources and any(s["asset"] == sheet.id for s in t.sources) for t in cat.tilesets
    )


def test_the_numbered_files_are_copies_of_the_sheet(tmp_path: Path) -> None:
    cat, _issues, _gen = _assemble("side_numbered_platformer", tmp_path)
    singles = [a for a in cat.assets if ".tiles.tile_" in a.id]
    assert singles and all(a.status == "UNUSED" for a in singles)


# ------------------------------------------------------------------ pieces named by their place


def test_pieces_named_by_their_place_are_one_terrain(tmp_path: Path) -> None:
    cat, _issues, generated = _assemble("side_named_platformer", tmp_path)
    (sheet,) = [
        a for a in cat.assets if a.pack_id == "generated" and "side_terrain" in a.detected["tags"]
    ]
    assert sheet.detected["role"] == "GROUND" and sheet.detected["grid"]["cell"] == [32, 32]
    assert sheet.path in generated and Path(generated[sheet.path]).is_file()
    kinds = {k: v["custom"]["side"] for k, v in sheet.detected["tile_overrides"].items()}
    row0 = [kinds[f"{x},0"] for x in range(6)]
    assert row0 == ["center", "mid", "left", "right", "single", "cliff"]
    assert [kinds[f"{x},1"] for x in range(3)] == ["one_way_left", "one_way_mid", "one_way_right"]
    assert sheet.detected["tile_overrides"]["1,1"]["collision"] == {"profile": "ONE_WAY"}
    assert sorted(kinds[f"{x},2"] for x in range(2)) == ["slope_left", "slope_right"]
    mid = sheet.detected["tile_overrides"]["1,0"]["terrain"]["peering"]
    assert (mid["top_side"], mid["left_side"], mid["right_side"], mid["bottom_side"]) == (
        -1,
        0,
        0,
        0,
    )
    assert sheet.detected["tile_overrides"]["5,0"]["probability"] == 0.0, (
        "a cliff's end is no first choice"
    )
    piece = _asset(cat, "grass.grassmid")
    assert piece.status == "UNUSED" and f"same_as:{sheet.path}" in piece.detected["tags"]
    assert piece.detected["usage"] == "sprite", "a piece set aside joins no tile set"
    assert _asset(cat, "tiles.grassledgeleft").detected["role"] == "DECORATION"
    assert _asset(cat, "tiles.signright").detected["role"] == "DECORATION"
    (tileset,) = [t for t in cat.tilesets if any(s["asset"] == sheet.id for s in t.sources)]
    assert tileset.name == "overworld"
    assert [s["shape"] for s in tileset.terrain_sets] == ["side"]


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("grassLeft", ("grass", "left")),
        ("grassMid", ("grass", "mid")),
        ("castleHillRight2", ("castle", "slope_right")),
        ("grassHalf_mid", ("grass", "one_way_mid")),
        ("grassCliffAlt_left", ("grass", "cliff")),
        ("grass", None),  # no place: a single block when it lies among pieces (see the sheet)
        ("signRight", None),
        ("grassLedgeLeft", ("grass", None)),
    ],
)
def test_the_place_a_name_gives(stem: str, expected: tuple[str, str | None] | None) -> None:
    found = side_packs._piece(stem)
    if expected is None:
        assert found is None or side_packs._layout(found[1]) is None or found[1] == frozenset()
        return
    assert found is not None and found[0] == expected[0]
    layout = side_packs._layout(found[1])
    assert (layout[2] if layout else None) == expected[1]


# ------------------------------------------------------------------ characters in action folders


def test_a_character_is_its_action_folders(tmp_path: Path) -> None:
    cat, _issues, generated = _assemble("side_action_frames", tmp_path)
    hero = _asset(cat, "hero_files.sprites.attack.frame1")
    assert hero.detected["role"] == "PLAYER" and hero.status == "AUTO_DETECTED"
    anims = hero.detected["animations"]
    assert sorted(anims) == ["attack_down", "idle_down", "jump_down", "run_down"]
    assert len(anims["run_down"]["frames"]) == 4 and anims["attack_down"]["loop"] is False
    assert all(spec["source"] in generated for spec in anims.values())
    assert not [a for a in cat.assets if ".sprites.idle.frame" in a.id], (
        "a frame is no asset of its own"
    )
    for aside in ("spritesheets.hero_idle", "previews.hero_idle"):
        asset = _asset(cat, aside)
        assert asset.status == "UNUSED"
    assert "unused_because:same_frames" in _asset(cat, "spritesheets.hero_run").detected["tags"]
    assert "unused_because:preview_gif" in _asset(cat, "previews.hero_run").detected["tags"]
    ogre = _asset(cat, "ogre.sprites.idle.ogre_idle_1")
    assert ogre.detected["role"] == "ENEMY", "a creature no word names is an enemy"
    assert sorted(ogre.detected["animations"]) == ["idle_down", "walk_unarmed_down"]
    assert ogre.detected["frame"] == [48, 40]
    view = next(p for p in cat.packs if p.pack_id == "side_action_frames")
    assert catalog.VIEW_SIDE in view.warnings


def test_frames_of_several_sizes_share_the_largest_frame(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    for action, size, count in (("Idle", (20, 30), 2), ("Attack", (40, 34), 3)):
        for i in range(count):
            im = Image.new("RGBA", size, (0, 0, 0, 0))
            im.paste((200, 60, 60, 255), (4, 4, size[0] - 4, size[1]))
            (pack / "Monster" / "Sprites" / action).mkdir(parents=True, exist_ok=True)
            im.save(pack / "Monster" / "Sprites" / action / f"frame{i + 1}.png")
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    (character,) = action_frames.find_characters(inv, set())
    assert character.folder == "Monster" and character.size == (40, 34)
    assert [name for name, _a in character.actions] == ["attack", "idle"]
    dest = tmp_path / "strip.png"
    action_frames.write_strip(pack, character.actions[1][1].frames, character.size, dest)
    strip = np.asarray(Image.open(dest).convert("RGBA"))
    assert strip.shape[:2] == (34, 80)
    assert strip[33, 20, 3] == 255 and strip[0, 20, 3] == 0, "a smaller frame stands on the bottom"


def test_files_named_by_actions_are_one_character(tmp_path: Path) -> None:
    pack = tmp_path / "pack" / "Players" / "Beige"
    pack.mkdir(parents=True)
    for name in ("alienBeige_stand", "alienBeige_walk1", "alienBeige_walk2", "alienBeige_jump",
                 "alienBeige_hit", "alienBeige_front"):  # fmt: skip
        Image.new("RGBA", (16, 24), (90, 200, 90, 255)).save(pack / f"{name}.png")
    opened = archive.open_pack(tmp_path / "pack", set())
    inv = inventory.build_inventory(opened)
    (character,) = action_frames.find_action_files(inv, set())
    names = [n for n, _a in character.actions]
    assert names == ["front", "hurt", "idle", "jump", "walk"]
    assert len(dict(character.actions)["walk"].frames) == 2


# ------------------------------------------------------------------ a stage of layers


def test_background_layers_are_one_ordered_set(tmp_path: Path) -> None:
    cat, _issues, _gen = _assemble("side_layered_platformer", tmp_path)
    depth = {}
    for a in cat.assets:
        tags = a.detected.get("tags") or []
        if "parallax_set:Background" in tags:
            depth[a.id.rsplit(".", 1)[-1]] = next(
                int(t[9:]) for t in tags if t.startswith("parallax:")
            )
            assert a.detected["usage"] == "background" and a.status == "AUTO_DETECTED"
    # the opaque sky is the last by number: the order is turned round
    assert depth == {"n1_5": 1, "n1_4": 2, "n1_3": 3, "n1_2": 4}
    assert _asset(cat, "props.props_2").detected["role"] == "DECORATION"
    tiles = _asset(cat, "tileset.tileset")
    assert tiles.detected["usage"] == "tiles" and "side_terrain" in tiles.detected["tags"]


def test_layers_ordered_by_their_words() -> None:
    class A:
        def __init__(self, name: str) -> None:
            self.id = name
            self.path = name + ".png"

    members = [A("front"), A("sky"), A("middle")]
    stems = {"front": "front", "sky": "sky", "middle": "middle"}
    order = side_packs._order(members, stems, Path("nowhere"), "")
    assert [a.id for a in order] == ["sky", "middle", "front"]


# ------------------------------------------------------------------ cells, sizes, licences


def test_one_cell_alone() -> None:
    def cell(draw: callable) -> side_tiles.Cell:  # type: ignore[valid-type]
        a = np.zeros((16, 16, 4), np.uint8)
        draw(a)
        return side_tiles.cells_of(a, 16, 16, (0, 0), (0, 0))[0]

    def fill(a: np.ndarray) -> None:
        a[:, :] = (150, 100, 60, 255)

    def plank(a: np.ndarray) -> None:
        a[:5, :] = (150, 100, 60, 255)

    def coin(a: np.ndarray) -> None:
        a[5:11, 5:11] = (240, 200, 40, 255)

    def water(a: np.ndarray) -> None:
        a[:, :] = (40, 110, 220, 255)

    def nothing(a: np.ndarray) -> None:
        a[0, 0] = (0, 0, 0, 0)

    assert side_tiles.kind_of(cell(fill)) == side_tiles.FILL
    assert side_tiles.kind_of(cell(plank)) == side_tiles.ONE_WAY
    assert side_tiles.kind_of(cell(coin)) == side_tiles.COIN
    assert side_tiles.kind_of(cell(water)) == side_tiles.WATER
    assert side_tiles.kind_of(cell(nothing)) is None


def test_the_same_sheet_reads_the_same(tmp_path: Path) -> None:
    sheet = SYNTH / "side_numbered_platformer" / "Tilemap" / "tilemap_packed.png"
    rgba = np.asarray(Image.open(sheet).convert("RGBA"))
    first = side_tiles.read(rgba, (16, 16))
    second = side_tiles.read(rgba.copy(), (16, 16))
    assert first == second


def test_a_licence_one_folder_above(tmp_path: Path) -> None:
    (tmp_path / "Assets" / "Hero Pack").mkdir(parents=True)
    (tmp_path / "Assets" / "license.txt").write_text(
        "Public Domain Dedication (CC0 1.0)\n", "utf-8"
    )
    found = licenses.licence_above(tmp_path / "Assets" / "Hero Pack")
    assert found is not None and found[0] == "license.txt" and found[1].license_id == "CC0-1.0"
    assert licenses.licence_above(tmp_path / "Assets") is None


def test_a_pack_analysed_alone_takes_the_licence_above(tmp_path: Path) -> None:
    pack = tmp_path / "Assets" / "Hero Pack"
    pack.mkdir(parents=True)
    Image.new("RGBA", (16, 16), (200, 0, 0, 255)).save(pack / "hero.png")
    (tmp_path / "Assets" / "license.txt").write_text("CC0 1.0 Universal\n", "utf-8")
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    cat, issues, _gen = catalog.assemble([(opened, inv)], None, [])
    (p,) = cat.packs
    assert p.license["license_id"] == "CC0-1.0"
    assert f"{catalog.LICENCE_ABOVE}license.txt" in p.warnings
    assert not any(i.code == "ASSET-021" for i in issues)


def test_a_pack_that_calls_itself_a_platformer_is_seen_from_the_side() -> None:
    class Inv:
        pack_id = "platformer_pack_medieval"
        files: list[object] = []

    assert classifier.made_for(Inv()) == "side"
