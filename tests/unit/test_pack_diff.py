from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rpggen import schema
from rpggen.core import archive, catalog, inventory, pack_diff
from rpggen.core.inventory import Inventory, InventoryFile

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _file(path: str, sha: str, size: tuple[int, int] | None = (16, 16)) -> InventoryFile:
    image = {"w": size[0], "h": size[1]} if size else None
    return InventoryFile(path, sha * 64, 10, ".png", "image" if size else "doc", image)


def _inv(*files: InventoryFile) -> Inventory:
    return Inventory("p", "0" * 64, list(files))


def test_diff_classifies_every_file() -> None:
    old = _inv(
        _file("same.png", "a"),
        _file("edited.png", "b"),
        _file("resized.png", "c", (16, 16)),
        _file("gone.png", "d"),
        _file("notes.txt", "e", None),
    )
    new = _inv(
        _file("same.png", "a"),
        _file("edited.png", "f"),
        _file("resized.png", "g", (32, 16)),
        _file("fresh.png", "h"),
        _file("notes.txt", "i", None),
    )
    d = pack_diff.diff(old, new)
    assert d.unchanged == ["same.png"]
    assert d.changed_same_size == ["edited.png", "notes.txt"]
    assert d.changed_resized == ["resized.png"]
    assert d.added == ["fresh.png"]
    assert d.removed == ["gone.png"]
    assert d.renamed == {}
    assert not d.is_empty
    assert d.changed_paths() == ["fresh.png", "gone.png", "resized.png"]


def test_a_moved_file_with_the_same_hash_is_a_rename() -> None:
    old = _inv(_file("tiles/grass.png", "a"), _file("keep.png", "b"))
    new = _inv(_file("terrain/grass.png", "a"), _file("keep.png", "b"))
    d = pack_diff.diff(old, new)
    assert d.renamed == {"terrain/grass.png": "tiles/grass.png"}
    assert d.added == [] and d.removed == []


def test_identical_files_that_cannot_be_matched_uniquely_are_not_renames() -> None:
    old = _inv(_file("a.png", "x"), _file("b.png", "x"))
    new = _inv(_file("c.png", "x"))
    d = pack_diff.diff(old, new)
    assert d.renamed == {} and d.added == ["c.png"] and d.removed == ["a.png", "b.png"]


def test_an_unchanged_pack_gives_an_empty_diff() -> None:
    inv = _inv(_file("a.png", "a"))
    assert pack_diff.diff(inv, inv).is_empty


# --------------------------------------------------------------------------- renames in the catalog


@pytest.fixture
def renamed_pack(tmp_path: Path) -> tuple[catalog.Catalog, Path, Path]:
    first = tmp_path / "v1"
    shutil.copytree(SYNTH / "basic16", first)
    opened = archive.open_pack(first, set(), pack_id="basic16")
    cat, _issues, _gen = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    second = tmp_path / "v2"
    shutil.copytree(first, second)
    return cat, first, second


def _assemble(pack: Path, previous: catalog.Catalog) -> catalog.Catalog:
    opened = archive.open_pack(pack, set(), pack_id="basic16")
    cat, _issues, _gen = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], previous, []
    )
    return cat


def test_a_renamed_file_keeps_its_overrides_and_source_id(
    renamed_pack: tuple[catalog.Catalog, Path, Path],
) -> None:
    previous, _first, second = renamed_pack
    tile_asset = next(
        a
        for a in previous.assets
        if a.id in {s["asset"] for t in previous.tilesets for s in t.sources}
    )
    previous.asset(tile_asset.id).overrides = {"tags": ["mine"]}  # type: ignore[union-attr]
    old_source = next(
        s["source_id"] for t in previous.tilesets for s in t.sources if s["asset"] == tile_asset.id
    )
    rel = tile_asset.path.removeprefix("assets/packs/basic16/")
    renamed_rel = str(Path(rel).with_name("moved_" + Path(rel).name)).replace("\\", "/")
    (second / rel).rename(second / renamed_rel)

    new = _assemble(second, previous)
    moved = next(a for a in new.assets if a.path.endswith(renamed_rel))
    assert moved.renamed_from == rel
    assert moved.overrides == {"tags": ["mine"]}
    assert moved.status != "MISSING"
    assert not any(a.id == tile_asset.id for a in new.assets), "no MISSING asset under the old id"
    source = next(s for t in new.tilesets for s in t.sources if s["asset"] == moved.id)
    assert source["source_id"] == old_source
    schema.validate("catalog", new.to_json())


def test_a_changed_file_that_is_not_a_rename_becomes_missing(
    renamed_pack: tuple[catalog.Catalog, Path, Path],
) -> None:
    previous, _first, second = renamed_pack
    victim = previous.assets[0]
    rel = victim.path.removeprefix("assets/packs/basic16/")
    (second / rel).unlink()
    new = _assemble(second, previous)
    assert next(a for a in new.assets if a.id == victim.id).status == "MISSING"
    assert all(a.renamed_from is None for a in new.assets)
