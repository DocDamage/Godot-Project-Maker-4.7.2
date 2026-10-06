from __future__ import annotations

import io
import shutil
import struct
import unicodedata
import zipfile
from pathlib import Path

import pytest

from rpggen.core import archive
from rpggen.errors import RpgGenError

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(cache))
    return cache


def _zip(
    path: Path, entries: list[tuple[str, bytes]], compression: int = zipfile.ZIP_STORED
) -> Path:
    with zipfile.ZipFile(path, "w", compression=compression) as zf:
        for name, data in entries:
            zf.writestr(
                zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0)),
                data,
                compress_type=compression,
            )
    return path


def _codes(pack: archive.OpenedPack) -> list[str]:
    return [i.code for i in pack.issues]


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


@pytest.mark.parametrize(
    "bad", ["../evil.png", "a/../../evil.png", "/abs.png", "C:/x.png", "..\\evil.png"]
)
def test_zip_slip_is_rejected(tmp_path: Path, cache_dir: Path, bad: str) -> None:
    src = _zip(tmp_path / "evil.zip", [("ok.png", b"x"), (bad, b"evil")])
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(src, set())
    assert ei.value.code == "ARCH-003"
    # nothing was written outside the cache, and no half-extracted directory remains
    assert not (tmp_path / "evil.png").exists()
    assert not (tmp_path.parent / "evil.png").exists()
    assert not list(cache_dir.rglob("*.partial"))


def test_zip_bomb_is_rejected(tmp_path: Path) -> None:
    src = _zip(
        tmp_path / "bomb.zip", [("zeros.bin", b"\0" * (50 * 1024 * 1024))], zipfile.ZIP_DEFLATED
    )
    assert src.stat().st_size < 200_000
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(src, set())
    assert ei.value.code == "ARCH-004"


def test_entry_larger_than_declared_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(archive.LIMITS, "max_entry_bytes", 10)
    src = _zip(tmp_path / "big.zip", [("big.bin", b"x" * 100)])
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(src, set())
    assert ei.value.code == "ARCH-004"


def test_too_many_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(archive.LIMITS, "max_files", 2)
    src = _zip(tmp_path / "many.zip", [(f"{i}.png", b"x") for i in range(3)])
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(src, set())
    assert ei.value.code == "ARCH-004"


def test_case_collision_keeps_first_sorted(tmp_path: Path) -> None:
    src = _zip(tmp_path / "case.zip", [("tree.png", b"lower"), ("Tree.PNG", b"upper")])
    pack = archive.open_pack(src, set())
    names = [n for n in _files(pack.root) if n != ".complete"]
    assert names == ["Tree.PNG"]
    assert (pack.root / "Tree.PNG").read_bytes() == b"upper"
    assert _codes(pack) == ["ARCH-005"]


def test_weird_names_pack(tmp_path: Path) -> None:
    pack = archive.open_pack(SYNTH / "weird_names.zip", set())
    assert pack.kind == "zip" and pack.pack_id == "weird_names"
    files = [n for n in _files(pack.root) if n != ".complete"]
    assert "extra_extracted/sign.png" in files
    assert "extra.zip" not in files
    assert not any("__MACOSX" in f or f.endswith(".DS_Store") for f in files)
    assert "\u00c1rbol Grande.png" in files
    assert unicodedata.is_normalized("NFC", "\u00c1rbol Grande.png")
    assert "Tree.PNG" in files and "tree.png" not in files
    codes = sorted(set(_codes(pack)))
    assert codes == ["ARCH-005", "ARCH-006", "ARCH-008"]
    assert len(pack.source_sha256) == 64


def test_nfd_names_become_nfc(tmp_path: Path) -> None:
    nfd = unicodedata.normalize("NFD", "\u00c1rbol.png")
    assert nfd != "\u00c1rbol.png"
    pack = archive.open_pack(_zip(tmp_path / "u.zip", [(nfd, b"x")]), set())
    assert "\u00c1rbol.png" in _files(pack.root)


def test_cp437_names_are_repaired() -> None:
    mangled = "\u00c1rbol".encode().decode("cp437")
    assert archive.normalize_name(mangled, utf8_flag=False) == "\u00c1rbol"
    # with the UTF-8 flag set the name is trusted as-is
    assert archive.normalize_name("\u00c1rbol", utf8_flag=True) == "\u00c1rbol"
    # not valid UTF-8 when re-encoded: keep the cp437 text
    assert archive.normalize_name("caf\u00e9", utf8_flag=False) == "caf\u00e9"
    assert archive.normalize_name("a\\b.png") == "a/b.png"


def test_second_open_reuses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = archive.open_pack(SYNTH / "weird_names.zip", set())

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("zipfile must not be used when the cache is complete")

    monkeypatch.setattr(zipfile, "ZipFile", boom)
    second = archive.open_pack(SYNTH / "weird_names.zip", set())
    assert second.root == first.root
    assert sorted(_codes(second)) == sorted(_codes(first))


def test_encrypted_entry(tmp_path: Path) -> None:
    src = _zip(tmp_path / "enc.zip", [("a.png", b"x")])
    data = bytearray(src.read_bytes())
    for sig, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = data.index(sig)
        flags = struct.unpack_from("<H", data, i + offset)[0] | 1
        struct.pack_into("<H", data, i + offset, flags)
    src.write_bytes(bytes(data))
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(src, set())
    assert ei.value.code == "ARCH-002"


def test_corrupt_and_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(bad, set())
    assert ei.value.code == "ARCH-001"
    other = tmp_path / "x.tar"
    other.write_bytes(b"x")
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(other, set())
    assert ei.value.code == "ARCH-001"
    with pytest.raises(RpgGenError):
        archive.open_pack(tmp_path / "missing.zip", set())


def test_folder_pack_is_read_in_place() -> None:
    pack = archive.open_pack(SYNTH / "basic16", {"basic16"})
    assert pack.kind == "folder"
    assert pack.root == SYNTH / "basic16"
    assert pack.pack_id == "basic16_2"
    assert pack.source_sha256 == ""


def test_rar_requires_7zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive, "find_7z", lambda: None)
    src = tmp_path / "x.rar"
    src.write_bytes(b"Rar!")
    with pytest.raises(RpgGenError) as ei:
        archive.open_pack(src, set())
    assert ei.value.code == "ARCH-007"


def test_parse_7z_listing() -> None:
    text = (
        "Path = x.rar\nType = Rar\n\n----------\n"
        "Path = a/b.png\nSize = 10\nPacked Size = 5\nAttributes = A\n\n"
        "Path = a\nSize = 0\nPacked Size = 0\nAttributes = D\n\n"
    )
    entries = archive._parse_7z_listing(text)
    assert [(e.name, e.size) for e in entries] == [("a/b.png", 10)]


def test_7z_archive(tmp_path: Path) -> None:
    import py7zr

    src = tmp_path / "pack.7z"
    base = tmp_path / "content"
    (base / "tiles").mkdir(parents=True)
    (base / "tiles" / "a.png").write_bytes(b"png")
    (base / "__MACOSX").mkdir()
    (base / "__MACOSX" / "junk").write_bytes(b"j")
    with py7zr.SevenZipFile(src, "w") as z:
        z.writeall(base, arcname=".")
    pack = archive.open_pack(src, set())
    assert pack.kind == "7z"
    files = [n for n in _files(pack.root) if n != ".complete"]
    assert files == ["tiles/a.png"]
    assert "ARCH-008" in _codes(pack)


def test_zipped_extracts_like_the_folder(tmp_path: Path) -> None:
    pack = archive.open_pack(SYNTH / "zipped.zip", set())
    got = [n for n in _files(pack.root) if n != ".complete"]
    want = sorted(
        p.relative_to(SYNTH / "basic16").as_posix()
        for p in (SYNTH / "basic16").rglob("*")
        if p.is_file()
    )
    assert got == want
    for rel in want:
        assert (pack.root / rel).read_bytes() == (SYNTH / "basic16" / rel).read_bytes()


def test_nested_archives_only_one_level(tmp_path: Path) -> None:
    inner2 = io.BytesIO()
    with zipfile.ZipFile(inner2, "w") as z:
        z.writestr("deep.png", b"deep")
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("mid.png", b"mid")
        z.writestr("inner2.zip", inner2.getvalue())
    src = _zip(tmp_path / "outer.zip", [("sub/inner.zip", inner.getvalue())])
    pack = archive.open_pack(src, set())
    files = [n for n in _files(pack.root) if n != ".complete"]
    assert "sub/inner_extracted/mid.png" in files
    assert "sub/inner_extracted/inner2.zip" in files  # not extracted further
    assert "sub/inner.zip" not in files
    shutil.rmtree(pack.root)
