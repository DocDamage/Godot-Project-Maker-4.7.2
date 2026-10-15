"""T17.13: the isometric tile set. The ``projection`` of the config (its default, the kinds that
have it, what is refused), the atlases the single tiles are packed into (the same every time,
and no cell moves when a tile is added), footprints that do not mix, and what the mapping and
the requirements say for the two projections."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import features, paths, schema
from rpggen.core import (
    archive,
    catalog,
    config,
    dry_run,
    inventory,
    iso_atlas,
    labels,
    mapping,
    orchestrator,
    requirements,
)
from rpggen.errors import RpgGenError

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
GRASS = "iso_tiles.png.isotile_001_0"
PACK = config.PackRef("iso_tiles", str(SYNTH / "iso_tiles"), "0" * 64, "folder")


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture(scope="module")
def tool():  # noqa: ANN201
    spec = importlib.util.spec_from_file_location(
        "make_synthetic_packs", REPO / "tools" / "make_synthetic_packs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _assemble(
    sources: list[Path], root: Path | None = None, previous: catalog.Catalog | None = None
) -> catalog.Catalog:
    """The catalog of ``sources``; with ``root`` the packs are installed there as a run does."""
    packs = []
    for source in sources:
        opened = archive.open_pack(source, {p[0].pack_id for p in packs})
        packs.append((opened, inventory.build_inventory(opened)))
        if root is not None:
            dest = root / "assets" / "packs" / opened.pack_id
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(opened.root, dest)
    cat, _issues, _generated = catalog.assemble(packs, previous, [], use_cache=False)
    return cat


def _cfg(archetype: str = "turn_based", projection: str = "isometric") -> config.GeneratorConfig:
    cfg = config.default_for("x", [PACK], archetype=archetype)
    cfg.projection = projection
    return cfg


def _iso_pack(tool, pack: Path, foot, canvas, count: int = 3, side: int = 8) -> Path:  # noqa: ANN001
    """A small isometric pack: ``count`` flat tiles turned four ways."""
    for i in range(1, count + 1):
        for turn in range(4):
            img = tool._iso_block(canvas, foot, side, tool.pal(i), turn=turn)
            path = pack / "PNG" / f"tile_{i:03d}_{turn}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, format="PNG")
    (pack / "License.txt").write_text("CC0-1.0 test\n", encoding="utf-8")
    return pack


# ------------------------------------------------------------------------------ the config


def test_a_config_without_the_key_is_top_down_and_what_it_was() -> None:
    cfg = config.default_for("x", [PACK])
    assert cfg.projection == "top_down"
    data = cfg.to_json()
    assert "projection" not in data, "a top-down config has no key: it is byte for byte the old one"
    schema.validate("config", data)
    assert config.GeneratorConfig.from_json(data).projection == "top_down"
    assert features.ISOMETRIC_AVAILABLE is True, "the wizard offers it since the gate of 1.5"


def test_the_projection_is_kept_through_a_save(tmp_path: Path) -> None:
    cfg = _cfg("arpg")
    assert cfg.to_json()["projection"] == "isometric"
    config.save(cfg, tmp_path / "cfg.json")
    assert config.load(tmp_path / "cfg.json").projection == "isometric"
    assert config.load(tmp_path / "cfg.json").to_json() == cfg.to_json()


@pytest.mark.parametrize("archetype", ["turn_based", "arpg", "farm", "racing", "assets"])
def test_the_kinds_that_have_an_isometric_view(archetype: str, tmp_path: Path) -> None:
    # the four kinds have the view, and the maps of all four are made (T17.14; the tracks of
    # the race: T17.15): none says "not yet" any more (tests/unit/test_iso_maps.py); and the
    # assets of isometric packs (T17.33: no maps)
    assert config.ISOMETRIC_KINDS == ("turn_based", "arpg", "farm", "racing", "assets")
    assert archetype in config.ISOMETRIC_KINDS and archetype not in config.ISOMETRIC_NOT_YET
    config.save(_cfg(archetype), tmp_path / "cfg.json")
    assert config.load(tmp_path / "cfg.json").projection == "isometric"


@pytest.mark.parametrize("archetype", ["metroidvania", "shmup", "run_and_gun"])
def test_a_kind_without_an_isometric_view_refuses_it(archetype: str, tmp_path: Path) -> None:
    cfg = _cfg(archetype)
    with pytest.raises(RpgGenError) as saved:
        config.save(cfg, tmp_path / "cfg.json")
    assert saved.value.issue.code == "CAT-002" and "/projection" in saved.value.issue.message
    assert archetype in saved.value.issue.message
    # a config somebody wrote by hand is refused when it is read
    (tmp_path / "hand.json").write_text(json.dumps(cfg.to_json()), encoding="utf-8")
    with pytest.raises(RpgGenError) as loaded:
        config.load(tmp_path / "hand.json")
    assert loaded.value.issue.code == "CAT-002"
    config.save(_cfg(archetype, "top_down"), tmp_path / "cfg.json")  # top-down is every kind's


def test_a_projection_nobody_knows_is_refused_by_the_schema(tmp_path: Path) -> None:
    data = _cfg().to_json()
    data["projection"] = "oblique"
    (tmp_path / "cfg.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RpgGenError) as found:
        config.load(tmp_path / "cfg.json")
    assert found.value.issue.code == "CAT-002"


def test_isometric_without_isometric_ground_is_refused(tmp_path: Path) -> None:
    square = _assemble([SYNTH / "basic16"])
    with pytest.raises(RpgGenError) as found:
        iso_atlas.check_ground(square, _cfg())
    assert found.value.issue.code == "CAT-002"
    assert "no isometric ground tile" in found.value.issue.message
    iso_atlas.check_ground(square, _cfg(projection="top_down"))  # nothing to say
    iso_atlas.check_ground(_assemble([SYNTH / "iso_tiles"]), _cfg())
    # ... and by the dry run, which is what a run does before Godot starts
    cfg = orchestrator.default_config_for_pack(SYNTH / "basic16", "x")
    cfg.projection = "isometric"
    config.save(cfg, tmp_path / "cfg.json")
    result = dry_run.run(tmp_path / "cfg.json", tmp_path / "out", placeholders=["PLAYER"])
    assert not result.ok and result.failed_phase == "catalog"
    assert [i.code for i in result.issues if i.severity.value == "error"] == ["CAT-002"]


def test_a_generated_project_cannot_change_its_projection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    saved = paths.from_posix_rel(paths.CONFIG, project)
    saved.parent.mkdir(parents=True)
    config.save(_cfg(projection="top_down"), saved)
    with pytest.raises(RpgGenError) as found:
        config.check_projection_kept(_cfg(), project)
    assert found.value.issue.code == "CAT-002" and "top_down" in found.value.issue.message
    config.check_projection_kept(_cfg(projection="top_down"), project)  # the same: fine
    config.save(_cfg(), saved)
    config.check_projection_kept(_cfg(), project)
    with pytest.raises(RpgGenError):
        config.check_projection_kept(_cfg(projection="top_down"), project)
    config.check_projection_kept(_cfg(), tmp_path / "nothing_there")  # a new project
    # the check of the target, which a run and the dry run make before anything else
    config.save(_cfg(projection="top_down"), saved)
    cfg = orchestrator.default_config_for_pack(SYNTH / "iso_tiles", "x")
    cfg.projection = "isometric"
    config.save(cfg, tmp_path / "cfg.json")
    result = dry_run.run(tmp_path / "cfg.json", project, placeholders=["PLAYER"])
    assert not result.ok and result.failed_phase == "preflight"
    assert "CAT-002" in [i.code for i in result.issues if i.severity.value == "error"]


def test_the_dry_run_of_an_isometric_project(tmp_path: Path) -> None:
    cfg = orchestrator.default_config_for_pack(SYNTH / "iso_tiles", "x")
    cfg.projection = "isometric"
    config.save(cfg, tmp_path / "cfg.json")
    result = dry_run.run(tmp_path / "cfg.json", tmp_path / "out", placeholders=["PLAYER"])
    assert [i for i in result.issues if i.severity.value == "error"] == []
    assert result.ok


# ------------------------------------------------------------------------------- the atlas


def _tile_set(cat: catalog.Catalog) -> catalog.TileSetDef:
    found = iso_atlas.existing_def(cat)
    assert found is not None
    return found


def test_the_tiles_of_a_pack_are_packed_into_atlases(tmp_path: Path) -> None:
    root = tmp_path / "root"
    cat = _assemble([SYNTH / "iso_tiles"], root)
    made = iso_atlas.add(cat, _cfg(), root)
    assert made == ["rpggen_iso.iso_tiles_0", "rpggen_iso.iso_tiles_1"]
    schema.validate("catalog", cat.to_json())
    tdef = _tile_set(cat)
    assert tdef.name == "iso" and tdef.projection == "isometric"
    assert tdef.tile_size == [60, 34], "the diamond of the pack, not half its width"
    assert tdef.sources == [
        {"asset": "rpggen_iso.iso_tiles_0", "source_id": 0},
        {"asset": "rpggen_iso.iso_tiles_1", "source_id": 1},
    ]
    assert {c["name"] for c in tdef.custom_data} >= {"asset_id", "footstep", "tillable", "water"}
    assert len(tdef.tiles) == 96, "every tile and every turn of it"
    # in the order of the ids, eight to a row, 64 to a picture
    assert tdef.tiles[GRASS] == {"source": 0, "coords": [0, 0], "at": [0, 0], "of": GRASS}
    assert tdef.tiles["iso_tiles.png.isotile_001_3"]["coords"] == [3, 0]
    assert tdef.tiles["iso_tiles.png.isotile_001_3"]["of"] == GRASS
    assert tdef.tiles["iso_tiles.png.isotile_003_0"]["coords"] == [0, 1]
    assert tdef.tiles["iso_tiles.png.isotile_017_0"] == {
        "source": 1,
        "coords": [0, 0],
        "at": [0, 0],
        "of": "iso_tiles.png.isotile_017_0",
    }
    record = cat.id_allocations["iso_atlases"]["iso_tiles"]
    assert record["cell"] == [60, 64] and (record["columns"], record["rows"]) == (8, 8)
    assert record["next_cell"] == 96 and record["sources"] == [0, 1]
    assert cat.id_allocations["tilesets"]["iso"]["next_source_id"] == 2
    # the pictures: every tile where the catalog says, pixel for pixel
    first = cat.asset("rpggen_iso.iso_tiles_0")
    second = cat.asset("rpggen_iso.iso_tiles_1")
    assert first is not None and second is not None
    assert first.detected["usage"] == "iso_atlas" and first.detected["role"] == "NONE"
    assert first.detected["grid"]["cell"] == [60, 64]
    assert first.detected["size"] == [480, 512] and second.detected["size"] == [480, 256]
    assert first.path == "generated/iso_atlases/iso_tiles_0.png"
    with Image.open(root / first.path) as sheet:
        assert sheet.size == (480, 512)
        for asset_id in (GRASS, "iso_tiles.png.isotile_009_2", "iso_tiles.png.isotile_016_3"):
            placed = tdef.tiles[asset_id]
            asset = cat.asset(asset_id)
            assert asset is not None
            x, y = placed["coords"][0] * 60, placed["coords"][1] * 64
            with Image.open(root / asset.path) as picture:
                cut = sheet.convert("RGBA").crop((x, y, x + 60, y + 64))
                assert cut.tobytes() == picture.convert("RGBA").tobytes(), asset_id
    assert labels.usage_label("iso_atlas") == "Isometric tile atlas"
    # the objects of the pack are no tiles: they are not in the atlas
    assert "iso_tiles.png.tree_01_0" not in tdef.tiles


def test_the_atlas_is_the_same_every_time(tmp_path: Path) -> None:
    results = []
    for name in ("one", "two"):
        root = tmp_path / name
        cat = _assemble([SYNTH / "iso_tiles"], root)
        iso_atlas.add(cat, _cfg(), root)
        pictures = {
            a.id: (root / a.path).read_bytes() for a in cat.assets if a.pack_id == "rpggen_iso"
        }
        results.append((cat.to_json(), pictures))
    assert results[0][0] == results[1][0]
    assert results[0][1] == results[1][1], "the pictures are the same bytes"
    # ... and running it again over its own result changes nothing
    root = tmp_path / "one"
    cat = _assemble([SYNTH / "iso_tiles"], root)
    iso_atlas.add(cat, _cfg(), root)
    again = catalog.Catalog.from_json(cat.to_json())
    iso_atlas.add(again, _cfg(), root)
    assert again.to_json() == cat.to_json()


def test_the_dry_run_describes_the_same_tile_set_without_the_files(tmp_path: Path) -> None:
    root = tmp_path / "root"
    cat = _assemble([SYNTH / "iso_tiles"], root)
    written = catalog.Catalog.from_json(cat.to_json())
    iso_atlas.add(written, _cfg(), root)
    empty = tmp_path / "empty"
    empty.mkdir()
    described = catalog.Catalog.from_json(cat.to_json())
    iso_atlas.add(described, _cfg(), empty)
    assert described.to_json() == written.to_json(), "so the fingerprint of a run is the dry run's"
    assert list(empty.iterdir()) == [], "and nothing is written where no pack is installed"


def test_an_added_tile_gets_a_new_cell_and_no_old_cell_moves(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = _iso_pack(tool, tmp_path / "isometric_village", (60, 34), (60, 64), count=3)
    root = tmp_path / "root"
    first = _assemble([pack], root)
    iso_atlas.add(first, _cfg(), root)
    before = {k: dict(v) for k, v in _tile_set(first).tiles.items()}
    assert len(before) == 12
    with Image.open(root / "generated/iso_atlases/isometric_village_0.png") as sheet:
        old_sheet = sheet.convert("RGBA")
    # the vendor adds two tiles, and one of them sorts before every tile there was
    for name, colour in (("aaa_first", 7), ("tile_004", 8)):
        for turn in range(4):
            img = tool._iso_block((60, 64), (60, 34), 8, tool.pal(colour), turn=turn)
            img.save(pack / "PNG" / f"{name}_{turn}.png", format="PNG")
    second = _assemble([pack], root, previous=first)
    assert _tile_set(second).projection == "isometric", "the tile set is carried through assembly"
    iso_atlas.add(second, _cfg(), root)
    after = _tile_set(second).tiles
    assert len(after) == 20
    for asset_id, placed in before.items():
        assert after[asset_id] == placed, f"{asset_id} moved"
    new = sorted(k for k in after if k not in before)
    assert [after[k]["coords"] for k in new] == [
        [4, 1], [5, 1], [6, 1], [7, 1], [0, 2], [1, 2], [2, 2], [3, 2],
    ]  # fmt: skip
    assert _tile_set(second).sources == _tile_set(first).sources, "the source keeps its id"
    with Image.open(root / "generated/iso_atlases/isometric_village_0.png") as sheet:
        new_sheet = sheet.convert("RGBA")
    assert new_sheet.size == (480, 192) and old_sheet.size == (480, 128)
    assert new_sheet.crop((0, 0, 240, 128)).tobytes() == old_sheet.crop((0, 0, 240, 128)).tobytes()
    assert new_sheet.crop((0, 0, 480, 64)).tobytes() == old_sheet.crop((0, 0, 480, 64)).tobytes()

    # a tile leaves the pack: its cell stays empty and is given to nobody
    for turn in range(4):
        (pack / "PNG" / f"tile_002_{turn}.png").unlink()
    (pack / "PNG" / "zzz_last_0.png").write_bytes((pack / "PNG" / "tile_001_0.png").read_bytes())
    third = _assemble([pack], root, previous=second)
    iso_atlas.add(third, _cfg(), root)
    last = _tile_set(third).tiles
    gone = [k for k in after if k not in last]
    assert sorted(gone) == [f"isometric_village.png.tile_002_{t}" for t in range(4)]
    for asset_id, placed in after.items():
        if asset_id not in gone:
            assert last[asset_id] == placed, f"{asset_id} moved"
    added = [k for k in last if k not in after]
    assert len(added) == 1 and last[added[0]]["coords"] == [4, 2], "the next cell, not a freed one"
    record = third.id_allocations["iso_atlases"]["isometric_village"]
    assert record["next_cell"] == 21 and len(record["cells"]) == 21
    with Image.open(root / "generated/iso_atlases/isometric_village_0.png") as sheet:
        hole = sheet.convert("RGBA").crop((240, 0, 480, 64))  # where tile_002 was
    assert hole.getbbox() is None, "the cell of the tile that left is empty"


def test_a_second_picture_is_begun_when_the_first_is_full(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = _iso_pack(tool, tmp_path / "isometric_big", (60, 34), (60, 64), count=16)
    root = tmp_path / "root"
    first = _assemble([pack], root)
    iso_atlas.add(first, _cfg(), root)
    assert [s["source_id"] for s in _tile_set(first).sources] == [0]
    for turn in range(4):
        img = tool._iso_block((60, 64), (60, 34), 8, tool.pal(3), turn=turn)
        img.save(pack / "PNG" / f"tile_017_{turn}.png", format="PNG")
    second = _assemble([pack], root, previous=first)
    iso_atlas.add(second, _cfg(), root)
    tdef = _tile_set(second)
    assert [s["source_id"] for s in tdef.sources] == [0, 1]
    assert tdef.tiles["isometric_big.png.tile_017_0"] == {
        "source": 1,
        "coords": [0, 0],
        "at": [0, 0],
        "of": "isometric_big.png.tile_017_0",
    }
    for asset_id, placed in _tile_set(first).tiles.items():
        assert tdef.tiles[asset_id] == placed


def test_one_width_and_several_heights_share_a_cell_of_the_largest(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_old"
    foot = (64, 32)
    for index, (lift, height) in enumerate(((0, 40), (16, 56), (48, 88))):
        for copy in range(2):
            img = tool._iso_block((64, height), foot, 8 + lift, tool.pal(index + copy + 1))
            path = pack / f"landscapeTiles_{index * 2 + copy:03d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, format="PNG")
    root = tmp_path / "root"
    cat = _assemble([pack], root)
    tiles = [a for a in cat.assets if catalog.is_iso_tile(a)]
    assert len(tiles) == 6 and {tuple(a.detected["size"]) for a in tiles} == {
        (64, 40),
        (64, 56),
        (64, 88),
    }
    for asset in tiles:
        asset.detected["role"] = "GROUND"
    iso_atlas.add(cat, _cfg(), root)
    tdef = _tile_set(cat)
    record = cat.id_allocations["iso_atlases"]["isometric_old"]
    assert record["cell"] == [64, 88], "the cell of the largest picture"
    by_height = {a.detected["size"][1]: tdef.tiles[a.id]["at"] for a in tiles}
    assert by_height == {40: [0, 48], 56: [0, 32], 88: [0, 0]}, "each on the bottom of its cell"
    # the diamond of every one lies at the same place of its cell: origin + at
    middles = {
        (a.detected["origin"][0] + tdef.tiles[a.id]["at"][0])
        for a in tiles
    } | {
        (a.detected["origin"][1] + tdef.tiles[a.id]["at"][1]) for a in tiles
    }  # fmt: skip
    assert middles == {32, 64}, "x 32 and y 88 - 8 - 16 for all six"


# ------------------------------------------------------------ footprints that do not mix


def test_tiles_of_another_footprint_are_left_out_with_a_note(tool, tmp_path: Path) -> None:  # noqa: ANN001
    other = _iso_pack(tool, tmp_path / "isometric_other", (64, 32), (64, 60), count=2)
    root = tmp_path / "root"
    cat = _assemble([SYNTH / "iso_tiles", other], root)
    cfg = _cfg()
    assert iso_atlas.project_footprint(cat, cfg) == (60, 34), "the footprint of the first ground"
    assert iso_atlas.other_footprints(cat, cfg) == [("isometric_other", (64, 32), (60, 34))]
    notes = [i for i in requirements.check(cat, cfg) if i.code == "TILE-012"]
    assert len(notes) == 1 and notes[0].severity.value == "warning"
    assert "isometric_other" in notes[0].message and "64 x 32" in notes[0].message
    assert "60 x 34" in notes[0].message
    iso_atlas.add(cat, cfg, root)
    tdef = _tile_set(cat)
    assert tdef.tile_size == [60, 34]
    assert len(tdef.tiles) == 96 and all(k.startswith("iso_tiles.") for k in tdef.tiles)
    assert list(cat.id_allocations["iso_atlases"]) == ["iso_tiles"]

    # the ground that is chosen says the footprint: the other pack's makes it the project's
    chosen = _assemble([SYNTH / "iso_tiles", other], root)
    cfg.starter = {"ground": "isometric_other.png.tile_001_0"}
    assert iso_atlas.project_footprint(chosen, cfg) == (64, 32)
    assert iso_atlas.other_footprints(chosen, cfg) == [("iso_tiles", (60, 34), (64, 32))]
    iso_atlas.add(chosen, cfg, root)
    assert _tile_set(chosen).tile_size == [64, 32] and len(_tile_set(chosen).tiles) == 8
    # ... until the project has its tile set: then the tile set says it
    cfg.starter = {"ground": GRASS}
    assert iso_atlas.project_footprint(chosen, cfg) == (64, 32)
    # a top-down project is told nothing of footprints
    top = requirements.check(_assemble([SYNTH / "iso_tiles", other]), _cfg(projection="top_down"))
    assert not [i for i in top if i.code == "TILE-012"]


def test_two_packs_of_one_footprint_share_the_tile_set(tool, tmp_path: Path) -> None:  # noqa: ANN001
    same = _iso_pack(tool, tmp_path / "isometric_same", (60, 34), (60, 80), count=2)
    root = tmp_path / "root"
    cat = _assemble([SYNTH / "iso_tiles", same], root)
    assert iso_atlas.other_footprints(cat, _cfg()) == []
    iso_atlas.add(cat, _cfg(), root)
    tdef = _tile_set(cat)
    assert len(tdef.tiles) == 104
    # each pack has its own pictures, in a cell of its own canvas
    assert [s["asset"] for s in tdef.sources] == [
        "rpggen_iso.iso_tiles_0",
        "rpggen_iso.iso_tiles_1",
        "rpggen_iso.isometric_same_0",
    ]
    assert cat.id_allocations["iso_atlases"]["isometric_same"]["cell"] == [60, 80]
    assert tdef.tiles["isometric_same.png.tile_001_0"]["source"] == 2


# --------------------------------------------------- the mapping and the requirements


def test_ground_is_isometric_in_an_isometric_project_and_never_in_a_top_down_one() -> None:
    cat = _assemble([SYNTH / "iso_tiles", SYNTH / "basic16"])
    assert mapping.best_for(cat, "GROUND") == "basic16.tiles.terrain"
    assert mapping.best_for(cat, "GROUND", "isometric") == GRASS, "the first turn of the first"
    top = mapping.candidates(cat, "GROUND")
    iso = mapping.candidates(cat, "GROUND", "isometric")
    assert top and all(catalog.effective(a)["usage"] == "tiles" for a in top)
    assert iso and all(catalog.is_iso_tile(a) for a in iso)
    assert mapping.valid_selection(cat, "GROUND", GRASS, "isometric")
    assert not mapping.valid_selection(cat, "GROUND", GRASS)
    assert not mapping.valid_selection(cat, "GROUND", "basic16.tiles.terrain", "isometric")
    assert mapping.default_starter(cat, "turn_based")["ground"] == "basic16.tiles.terrain"
    assert mapping.default_starter(cat, "turn_based", "isometric")["ground"] == GRASS
    assert (
        mapping.resolve_starter(
            cat, "turn_based", {"ground": "basic16.tiles.terrain"}, "isometric"
        )["ground"]
        == GRASS
    ), "a square ground is no choice of an isometric project"
    # a hero drawn for a top-down game walks both
    assert mapping.best_for(cat, "PLAYER") == mapping.best_for(cat, "PLAYER", "isometric")
    assert mapping.best_for(cat, "PLAYER") is not None
    assert mapping.plausible_usage("GROUND") == {"tiles"}
    assert mapping.plausible_usage("GROUND", "isometric") == {"iso_tile"}
    assert mapping.plausible_usage("PLAYER", "isometric") == {"sprite"}


def test_what_was_drawn_for_the_other_view_fills_no_role() -> None:
    cat = _assemble([SYNTH / "iso_tiles"])
    tree = cat.asset("iso_tiles.png.tree_01_0")
    house = cat.asset("iso_tiles.png.house_01_0")
    ground = cat.asset(GRASS)
    assert tree is not None and house is not None and ground is not None
    for asset in (tree, house, ground):
        assert not catalog.fits_projection(asset), asset.id
        assert catalog.fits_projection(asset, "isometric"), asset.id
    assert mapping.best_for(cat, "BUILDING") is None, "no isometric house in a top-down village"
    assert mapping.best_for(cat, "BUILDING", "isometric") == "iso_tiles.png.house_01_0"
    square = _assemble([SYNTH / "basic16"])
    sheet = square.asset("basic16.tiles.terrain")
    assert sheet is not None
    assert catalog.fits_projection(sheet) and not catalog.fits_projection(sheet, "isometric")
    hero = square.asset(mapping.best_for(square, "PLAYER") or "")
    assert hero is not None and catalog.fits_projection(hero, "isometric")


def test_the_requirements_of_the_two_projections() -> None:
    iso_only = _assemble([SYNTH / "iso_tiles"])

    def missing(cat: catalog.Catalog, cfg: config.GeneratorConfig) -> set[str]:
        found = requirements.check(cat, cfg)
        return {i.detail["role"] for i in found if i.code == "ASSET-010"}

    assert "GROUND" in missing(iso_only, _cfg(projection="top_down"))
    assert "BUILDING" in missing(iso_only, _cfg(projection="top_down"))
    assert "GROUND" not in missing(iso_only, _cfg())
    assert "BUILDING" not in missing(iso_only, _cfg())
    square = _assemble([SYNTH / "basic16"])
    assert "GROUND" not in missing(square, _cfg(projection="top_down"))
    assert "GROUND" in missing(square, _cfg()), "square ground is none of an isometric project"


def test_tile_011_says_which_ground_is_left_out() -> None:
    cat = _assemble([SYNTH / "iso_tiles", SYNTH / "basic16"])
    top = [i for i in requirements.check(cat, _cfg(projection="top_down")) if i.code == "TILE-011"]
    iso = [i for i in requirements.check(cat, _cfg()) if i.code == "TILE-011"]
    assert len(top) == 1 and "the isometric tiles are left out" in top[0].message
    assert len(iso) == 1 and "the square tiles are left out" in iso[0].message
    for cfg in (_cfg(), _cfg(projection="top_down")):
        only = requirements.check(_assemble([SYNTH / "iso_tiles"]), cfg)
        assert not [i for i in only if i.code == "TILE-011"], "one kind of ground: nothing to say"


# ----------------------------------------------------------------- what a run adds


def test_a_run_adds_the_tile_set_to_an_isometric_project_only(tmp_path: Path) -> None:
    root = tmp_path / "root"
    top = _assemble([SYNTH / "iso_tiles", SYNTH / "basic16"], root)
    before = top.to_json()
    orchestrator.add_run_made_assets(top, _cfg(projection="top_down"), [], root)
    assert top.to_json() == before, "a top-down project gets nothing of it"
    assert not (root / "generated").exists()
    iso = _assemble([SYNTH / "iso_tiles", SYNTH / "basic16"], root)
    orchestrator.add_run_made_assets(iso, _cfg(), [], root)
    assert [t.name for t in iso.tilesets] == ["iso", "overworld"]
    overworld = next(t for t in iso.tilesets if t.name == "overworld")
    assert overworld.to_json() == next(t for t in top.tilesets if t.name == "overworld").to_json()
    assert "projection" not in overworld.to_json() and "tiles" not in overworld.to_json()
    # the tile set lives through what assigns the tile sets again (a kit, the audit)
    again = catalog.Catalog.from_json(iso.to_json())
    catalog.assign_tilesets(again, catalog.Catalog.from_json(iso.to_json()))
    assert [t.to_json() for t in again.tilesets] == [t.to_json() for t in iso.tilesets]
    assert again.id_allocations == iso.id_allocations


def test_the_fixture_of_the_gdscript_tests_is_current() -> None:
    spec = importlib.util.spec_from_file_location(
        "make_iso_fixture", REPO / "tools" / "make_iso_fixture.py"
    )
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.check() == [], "run python tools/make_iso_fixture.py"


# ------------------------------------ an existing kind with an isometric pack (top-down)


def test_a_top_down_game_whose_only_ground_is_isometric_gets_the_placeholder(
    tmp_path: Path,
) -> None:
    """The requirements say a top-down game has no ground in an isometric pack, so the run
    that fills the missing roles with placeholders has to make that ground: it must not take
    the isometric tiles for it."""
    cat = _assemble([SYNTH / "iso_tiles"])
    cfg = _cfg(projection="top_down")
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    assert missing == ["PLAYER", "GROUND"]
    orchestrator.add_run_made_assets(cat, cfg, missing, tmp_path)
    ground = cat.asset("debug_placeholders.ground")
    assert ground is not None and ground.detected["usage"] == "tiles"
    assert (tmp_path / ground.path).is_file()
    assert [t.name for t in cat.tilesets] == ["overworld"], "the placeholder's, and no other"
    assert not [i for i in requirements.check(cat, cfg) if i.severity.value == "error"]
    assert mapping.default_starter(cat, "turn_based")["ground"] == "debug_placeholders.ground"
    assert "building" not in mapping.default_starter(cat, "turn_based")
    # the placeholder ground is square: it is none of an isometric project
    assert not catalog.fits_projection(ground, "isometric")


def test_a_top_down_race_does_not_drive_the_car_of_an_isometric_pack(tmp_path: Path) -> None:
    from rpggen.core import arcade_kit

    cat = _assemble([SYNTH / "iso_miniature"])
    car = next(a for a in cat.assets if a.detected.get("role") == "VEHICLE")
    assert car.detected["projection"] == "isometric"
    top = [s.name for s in arcade_kit.lacking(cat, "racing")]
    assert top == ["car", "road"], "both are drawn for the view from above"
    assert [s.name for s in arcade_kit.lacking(cat, "racing", "isometric")] == []
    notes = requirements.check(cat, _cfg("racing", "top_down"))
    assert sorted(i.detail["thing"] for i in notes if i.code == "ASSET-031") == [
        "car in sixteen headings",
        "road",
    ]
    assert not [i for i in notes if i.severity.value == "error"]
    orchestrator.add_run_made_assets(cat, _cfg("racing", "top_down"), [], tmp_path)
    assert cat.asset("rpggen_arcade_kit.car") is not None
    assert cat.asset("rpggen_arcade_kit.road") is not None
    assert iso_atlas.existing_def(cat) is None


def test_the_farm_kit_looks_at_what_fits_the_view() -> None:
    from rpggen.core import farm_kit

    cat = _assemble([SYNTH / "iso_miniature"])
    soil = next(
        a for a in cat.assets if "soil" in (a.detected.get("tags") or []) and a.status != "UNUSED"
    )
    assert catalog.is_iso_tile(soil)
    assert soil not in farm_kit._own(cat), "a top-down farm does not own an isometric tile"
    assert soil in farm_kit._own(cat, "isometric")
