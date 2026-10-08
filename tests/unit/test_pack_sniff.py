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
