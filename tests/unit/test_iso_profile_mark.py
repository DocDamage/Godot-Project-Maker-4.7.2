"""A pack read through its profile keeps its isometric mark (T17.18). The profile claims every
picture, so the isometric reader looked at none and the pack warning `isometric:<w>x<h>:<source>`
was not written: `catalog.isometric_footprint` was None and the pack card could not say
*Isometric tiles, 40 x 22*."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory, options, profiles

REPO = Path(__file__).resolve().parents[2]
ISLE = REPO / "sample_pack_iso"


@pytest.fixture(autouse=True)
def _own_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "rpggen"))


def _assemble() -> catalog.Catalog:
    opened = archive.open_pack(ISLE, set(), pack_id=ISLE.name)
    cat, _issues, _made = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    return cat


def test_the_diamond_is_said_with_and_without_the_profile() -> None:
    plain = _assemble()
    assert catalog.isometric_footprint(plain.packs[0]) == (40, 22, "tile_information")
    profiles.install_profile(ISLE / "sample_iso.rpgprofile.json")
    read = _assemble()
    assert read.assets[0].detected_by == "profile" or any(
        a.detected_by == "profile" for a in read.assets
    ), "the profile was used"
    assert catalog.isometric_footprint(read.packs[0]) == (40, 22, "profile")
    assert options.pack_footprint(read) == (40, 22)
    marks = [w for w in read.packs[0].warnings if w.startswith("isometric:")]
    assert marks == ["isometric:40x22:profile"], "one mark, and not the reader's beside it"


def test_the_diamond_of_tiles_is_the_one_most_of_them_stand_on() -> None:
    tile = {"usage": "iso_tile", "footprint": [40, 22]}
    other = {"usage": "iso_tile", "footprint": [64, 32]}
    assert catalog._diamond_of_tiles([tile, tile, other]) == (40, 22)
    assert catalog._diamond_of_tiles([tile, other]) == (40, 22), "a tie: the smaller"
    assert catalog._diamond_of_tiles([{"usage": "sprite", "footprint": [40, 22]}]) is None
    assert (
        catalog._diamond_of_tiles([{"usage": "iso_tile"}, {"usage": "iso_tile", "footprint": []}])
        is None
    )
