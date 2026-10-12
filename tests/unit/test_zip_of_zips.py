"""T16.21: an archive whose packs are archives of their own (the side-scroller zip of eight
zips): told as a bundle from the listings, and one inner archive opened as a pack."""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, inventory, pack_sniff
from rpggen.errors import RpgGenError

THEMES = ("Castle", "Cave", "Forest", "Lava Chambers")
SHEETS = ("1. Ground & Terrain Tiles", "2. Platform Tiles", "10. Doors, Windows & Pieces")


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _png(shade: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (16, 16), (shade, 90, 40, 255)).save(out, format="PNG")
    return out.getvalue()


def _inner(theme: str, shade: int, wrapped: bool = False) -> bytes:
    """One pack as a zip: three sheets, a licence and what macOS leaves behind."""
    out = io.BytesIO()
    top = f"Side-Scroller Tileset {theme}/" if wrapped else ""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, sheet in enumerate(SHEETS):
            zf.writestr(f"{top}{sheet}.png", _png(shade + n))
        zf.writestr(f"{top}License.txt", "CC0")
        zf.writestr("__MACOSX/._1. Ground & Terrain Tiles.png", b"junk")
    return out.getvalue()


def _outer(path: Path, top: str = "", method: int = zipfile.ZIP_DEFLATED) -> Path:
    with zipfile.ZipFile(path, "w", method) as zf:
        for index, theme in enumerate(THEMES):
            zf.writestr(
                f"{top}Side-Scroller Tileset {theme}.zip", _inner(theme, 20 * index, index == 1)
            )
        zf.writestr(f"{top}Read me.txt", "eight packs")
    return path


@pytest.mark.parametrize("top", ["", "side scrollers/"])
@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_a_zip_of_zips_is_a_bundle_of_its_inner_archives(
    tmp_path: Path, top: str, method: int
) -> None:
    outer = _outer(tmp_path / "side scrollers.zip", top, method)
    before = sorted(p.name for p in tmp_path.rglob("*"))
    result = pack_sniff.sniff(outer)
    assert sorted(p.name for p in tmp_path.rglob("*")) == before, "nothing is unpacked"
    assert not result.issues and result.format == "generic"
    assert [p.name for p in result.bundle] == [f"Side-Scroller Tileset {t}" for t in THEMES]
    first = result.bundle[0]
    assert first.path == f"{top}Side-Scroller Tileset Castle.zip"
    assert pack_sniff.is_inner_archive(first.path) and not pack_sniff.is_inner_archive(first.name)
    sizes = [len(_png(n)) for n in range(3)]
    assert (first.images, first.bytes) == (3, sum(sizes)), "the pictures of the inner listing"
    assert {p.images for p in result.bundle} == {3}
    assert pack_sniff.folder_in_bundle(outer, "side-scroller tileset cave").path.endswith(
        "Cave.zip"
    )


def test_a_folder_of_zips_is_one_too(tmp_path: Path) -> None:
    root = tmp_path / "side scrollers"
    root.mkdir()
    for index, theme in enumerate(THEMES[:2]):
        (root / f"{theme}.zip").write_bytes(_inner(theme, 30 * index))
    result = pack_sniff.sniff(root)
    assert [(p.name, p.path, p.images) for p in result.bundle] == [
        ("Castle", "Castle.zip", 3),
        ("Cave", "Cave.zip", 3),
    ]
    opened = archive.open_pack(root, set(), folder="Cave")
    assert opened.kind == "zip" and opened.pack_id == "cave"
    assert len([f for f in inventory.build_inventory(opened).files if f.kind == "image"]) == 3


def _zip_with(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_what_is_no_bundle_of_archives(tmp_path: Path) -> None:
    pack = _inner("Castle", 10)
    cases = {
        "one archive inside": {"a.zip": pack},
        "a picture beside the archives": {"a.zip": pack, "b.zip": pack, "cover.png": _png(1)},
        "archives in two folders": {"x/a.zip": pack, "y/b.zip": pack},
        "an archive without pictures": {"a.zip": pack, "b.zip": _zip_bytes({"notes.txt": b"hi"})},
        "a file that is no zip": {"a.zip": pack, "b.zip": b"not a zip at all"},
    }
    for why, members in cases.items():
        outer = _zip_with(tmp_path / "outer.zip", members)
        result = pack_sniff.sniff(outer)
        assert result.bundle == () and result.format == "generic" and not result.issues, why
        outer.unlink()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return out.getvalue()


def test_an_archive_the_time_does_not_reach_is_listed_by_its_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outer = _outer(tmp_path / "outer.zip")
    with zipfile.ZipFile(outer) as zf:
        source = pack_sniff._Zip(zf)
        names = source.names()
        asked: list[float] = []
        monkeypatch.setattr(time, "monotonic", lambda: asked.append(0.0) or 5.0 * (len(asked) > 1))
        found = pack_sniff.find_archive_bundle(source, names, deadline=1.0)  # up after one
        monkeypatch.undo()
        sizes = source.sizes()
    assert [p.images for p in found] == [3, 0, 0, 0]
    assert found[1].bytes == sizes["Side-Scroller Tileset Cave.zip"] > 0
    with zipfile.ZipFile(outer) as zf:
        source = pack_sniff._Zip(zf)
        assert pack_sniff.find_archive_bundle(source, source.names(), deadline=-1.0) == ()


def test_one_inner_archive_is_opened_as_a_pack(tmp_path: Path) -> None:
    outer = _outer(tmp_path / "side scrollers.zip", "side scrollers/")
    listed = pack_sniff.sniff(outer).bundle
    # by the path the wizard gives a pack taken from a bundle, which is not on the disk
    member = pack_sniff.member_path(outer, listed[1].name)
    opened = archive.open_pack(member, set())
    assert (opened.kind, opened.pack_id) == ("zip", "side_scroller_tileset_cave")
    inv = inventory.build_inventory(opened)
    pictures = sorted(f.path for f in inv.files if f.kind == "image")
    assert pictures == sorted(f"Side-Scroller Tileset Cave/{s}.png" for s in SHEETS)
    assert any(f.kind == "license" for f in inv.files), "the pack's own licence"
    assert opened.root.is_dir() and (tmp_path / "cache") in opened.root.parents
    # ... and by the folder option; the same archive again comes from the cache, by its content
    again = archive.open_pack(outer, {opened.pack_id}, folder=listed[1].path)
    assert again.root == opened.root and again.source_sha256 == opened.source_sha256 != ""
    assert again.pack_id == "side_scroller_tileset_cave_2"
    other = pack_sniff.open_inner_archive(outer, listed[0].path, set(), "castle")
    assert other.pack_id == "castle" and other.root != opened.root
    with pytest.raises(RpgGenError) as error:
        pack_sniff.open_inner_archive(outer, "side scrollers/Nothing.zip", set())
    assert error.value.code == "ARCH-001"
    with pytest.raises(RpgGenError):
        archive.open_pack(pack_sniff.member_path(outer, "No such pack"), set())
    # the whole archive is still one pack, its inner archives unpacked into it, as before
    whole = archive.open_pack(outer, set())
    names = [f.path for f in inventory.build_inventory(whole).files if f.kind == "image"]
    assert len(names) == 12 and all("_extracted/" in n for n in names)
