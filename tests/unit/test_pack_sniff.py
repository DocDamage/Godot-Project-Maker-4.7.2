"""T12.33: the format, licence and errors of a pack, read without extracting it."""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pytest

from rpggen.core import pack_sniff

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"

EXPECTED = {
    "rpgmaker_like": "rpgmaker",
    "lpc_like": "lpc",
    "tiled_meta": "tiled",
    "aseprite_meta": "aseprite",
    "basic16": "generic",
    "mixed": "generic",
    "audio_basic": "generic",
    "strips": "generic",
    "zipped.zip": "generic",
}


@pytest.mark.parametrize(("pack", "fmt"), sorted(EXPECTED.items()))
def test_every_synthetic_pack_sniffs_to_its_format(pack: str, fmt: str) -> None:
    started = time.monotonic()
    result = pack_sniff.sniff(SYNTH / pack)
    assert result.format == fmt and not result.issues
    assert time.monotonic() - started < pack_sniff.BUDGET_S


def test_rpg_maker_tile_size_comes_from_a_sheet_header() -> None:
    assert pack_sniff.sniff(SYNTH / "rpgmaker_like").tile_size == 48


def test_the_formats_inside_a_zip_are_found_too(tmp_path: Path) -> None:
    out = tmp_path / "rpg.zip"
    with zipfile.ZipFile(out, "w") as zf:
        for path in (SYNTH / "rpgmaker_like").rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(SYNTH / "rpgmaker_like").as_posix())
    result = pack_sniff.sniff(out)
    assert (result.format, result.tile_size, result.has_license) == ("rpgmaker", 48, True)


def test_ldtk_and_licence_detection(tmp_path: Path) -> None:
    (tmp_path / "world.ldtk").write_text("{}")
    result = pack_sniff.sniff(tmp_path)
    assert result.format == "ldtk" and result.has_license is False
    for name in ("LICENSE.txt", "Licence.md", "credits.txt", "README", "COPYING"):
        folder = tmp_path / name.split(".")[0]
        folder.mkdir()
        (folder / name).write_text("x")
        assert pack_sniff.sniff(folder).has_license is True, name


def test_problems_are_returned_not_raised(tmp_path: Path) -> None:
    missing = pack_sniff.sniff(tmp_path / "nope")
    assert [i.code for i in missing.issues] == ["ARCH-001"] and not missing.format
    odd = tmp_path / "notes.txt"
    odd.write_text("x")
    assert [i.code for i in pack_sniff.sniff(odd).issues] == ["ARCH-001"]
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    assert pack_sniff.sniff(broken).issues[0].code == "ARCH-001"


def test_a_password_protected_zip_is_arch_002(tmp_path: Path) -> None:
    out = tmp_path / "locked.zip"
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("a.png", b"x")
    data = bytearray(out.read_bytes())
    # set the "encrypted" bit in the local and the central header
    for marker, at in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = data.find(marker)
        data[i + at] |= 1
    out.write_bytes(bytes(data))
    assert [i.code for i in pack_sniff.sniff(out).issues] == ["ARCH-002"]


# ------------------------------------------------------------------------ changed since (T13.08)


def test_a_stamp_changes_with_the_pack_and_only_then(tmp_path: Path) -> None:
    import os
    import time

    folder = tmp_path / "town"
    (folder / "tiles").mkdir(parents=True)
    (folder / "tiles" / "a.png").write_bytes(b"1234")
    (folder / "readme.txt").write_bytes(b"hello")
    recorded = pack_sniff.stamp(folder)
    assert recorded is not None and recorded.startswith("dir:2:9:")
    assert pack_sniff.stamp(folder) == recorded
    assert pack_sniff.changed_since(folder, recorded) is None
    # a file touched later (same bytes): changed, on that day
    later = time.time() + 5 * 24 * 3600
    os.utime(folder / "tiles" / "a.png", (later, later))
    when = pack_sniff.changed_since(folder, recorded)
    assert when is not None and abs(when.timestamp() - later) < 2
    # a file added, a file removed
    recorded = pack_sniff.stamp(folder)
    (folder / "new.png").write_bytes(b"x")
    assert pack_sniff.changed_since(folder, recorded) is not None
    recorded = pack_sniff.stamp(folder)
    (folder / "new.png").unlink()
    assert pack_sniff.changed_since(folder, recorded) is not None
    # an archive: its size and time
    archive = tmp_path / "forest.zip"
    archive.write_bytes(b"PK" + b"\x00" * 30)
    recorded = pack_sniff.stamp(archive)
    assert recorded is not None and recorded.startswith("file:32:")
    assert pack_sniff.changed_since(archive, recorded) is None
    archive.write_bytes(b"PK" + b"\x00" * 31)
    assert pack_sniff.changed_since(archive, recorded) is not None


def test_nothing_recorded_or_a_pack_that_is_away_is_not_a_change(tmp_path: Path) -> None:
    folder = tmp_path / "town"
    folder.mkdir()
    assert pack_sniff.changed_since(folder, "") is None, "a project from 1.0 recorded nothing"
    recorded = pack_sniff.stamp(folder)
    assert recorded == "dir:0:0:0"
    missing = tmp_path / "unplugged"
    assert pack_sniff.stamp(missing) is None
    assert pack_sniff.changed_since(missing, "dir:3:10:5") is None


# ----------------------------------------------------------------- a bundle of packs (T16.21)

THEMES = ["Abandoned Hospital", "Alien Jungle", "Backrooms", "Cyberpunk City", "Desert Ruins",
          "Haunted Manor", "Medieval Fantasy Town", "Modern Gym", "Monder Interiors", "Pirate Cove",
          "Space Station", "WW1 Trench & Bunker"]  # fmt: skip


def _bundle_names(top: str = "Bundle/", suffix: str = " Pixel Art Tileset Pack") -> list[str]:
    names = []
    for index, theme in enumerate(THEMES):
        folder = f"{top}{theme}{suffix}"
        names += [f"{folder}/{n}.png" for n in (1, 2, 3, 5)]  # a gap in the numbers
        if index == 0:
            names.append(f"{folder}/deeper/tileset-1/9.png")  # sheets one folder down
    return names


def test_a_bundle_is_told_from_the_listing_of_its_archive_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for name in _bundle_names():
            zf.writestr(name, b"x" * 100)
        zf.writestr("Bundle/Backrooms Pixel Art Tileset Pack/__MACOSX/._1.png", b"junk")
        zf.writestr("Bundle/Backrooms Pixel Art Tileset Pack/notes.txt", b"hello")
    reads: list[str] = []
    monkeypatch.setattr(pack_sniff._Zip, "head", lambda self, name, size: reads.append(name) or b"")
    result = pack_sniff.sniff(archive)
    assert reads == [], "nothing is opened: the names and sizes of the listing are enough"
    assert not result.issues and result.format == "generic"
    assert [p.name for p in result.bundle] == sorted(
        (f"{theme} Pixel Art Tileset Pack" for theme in THEMES), key=str.casefold
    )
    first = result.bundle[0]
    assert first.path == "Bundle/Abandoned Hospital Pixel Art Tileset Pack"
    assert (first.images, first.bytes) == (5, 500), "the sheets one folder down count"
    assert {(p.images, p.bytes) for p in result.bundle[1:]} == {(4, 400)}


def test_a_folder_of_packs_is_a_bundle_and_one_of_its_folders_is_a_pack(tmp_path: Path) -> None:
    root = tmp_path / "CuteSCKR"
    for name in _bundle_names(top=""):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(b"x" * 10)
    result = pack_sniff.sniff(root)
    assert len(result.bundle) == 12 and result.bundle[3].path == result.bundle[3].name
    assert sum(p.images for p in result.bundle) == 49 and result.bundle[1].bytes == 40
    one = pack_sniff.sniff(root / result.bundle[1].path)
    assert one.bundle == () and one.format == "generic"


@pytest.mark.parametrize(
    ("names", "why"),
    [
        (_bundle_names()[: 4 * 9 + 1], "nine folders are the folders of one pack"),
        ([*_bundle_names(), "Bundle/cover.png"], "a picture beside the folders"),
        (_bundle_names(suffix=""), "folders named after what is in them, not as packs"),
        (
            [f"lpc/{part}/{n}.png" for part in ["body", "hair", "torso", "legs", "feet", "head", "hands", "belt", "cape", "wings"] for n in (1, 2)],
            "the ten part folders of a character pack",
        ),
        (["readme.txt", "a/b.txt"], "no picture at all"),
        ([], "nothing"),
    ],
)  # fmt: skip
def test_one_pack_with_many_folders_is_no_bundle(names: list[str], why: str) -> None:
    assert pack_sniff.find_bundle(names) == (), why


def test_half_of_the_folders_named_as_packs_is_enough() -> None:
    names = _bundle_names()
    plain = [n.replace(" Pixel Art Tileset Pack", "") if i % 2 else n for i, n in enumerate(names)]
    by_folder = {n.split("/")[1] for n in plain}
    assert len(by_folder) > 12  # both spellings of some folders: still half are named as packs
    assert len(pack_sniff.find_bundle(plain)) == len(by_folder)
    assert len(pack_sniff.find_bundle([n.replace("/", "\\") for n in names])) == 12
