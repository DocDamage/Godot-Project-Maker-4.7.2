from __future__ import annotations

import io
import os
import shutil
import struct
import unicodedata
import zipfile
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import archive
from rpggen.errors import RpgGenError

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return paths.cache_dir()


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
    monkeypatch.setattr(archive, "find_bsdtar", lambda: None)
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


# ------------------------------------------------------------------------ progress and cancel (T12.06)


def _no_partial(cache: Path) -> bool:
    extracted = cache / "extracted"
    return not extracted.exists() or not any(
        p.name.endswith(".partial") for p in extracted.iterdir()
    )


def test_extraction_reports_bytes_and_ends_on_the_total(tmp_path: Path) -> None:
    block = bytes(range(256)) * 4096  # 1 MiB
    source = _zip(tmp_path / "big.zip", [(f"a{i}.bin", block) for i in range(4)])
    seen: list[tuple[str, int, int]] = []
    archive.open_pack(source, set(), progress=lambda *a: seen.append(a))
    extracting = [e for e in seen if e[0].startswith("Extracting big.zip")]
    assert extracting and all(total == 4 * len(block) for _l, _d, total in extracting)
    done = [d for _l, d, _t in extracting]
    assert done == sorted(done) and done[-1] == 4 * len(block)
    assert [e for e in seen if e[0].startswith("Reading big.zip")]  # the hash is a stage too


def test_a_cancel_stops_between_chunks_and_removes_the_partial_folder(
    tmp_path: Path, cache_dir: Path
) -> None:
    block = bytes(range(256)) * 4096
    source = _zip(tmp_path / "big.zip", [(f"a{i}.bin", block) for i in range(6)])
    calls = {"n": 0}

    def cancelled() -> bool:
        calls["n"] += 1
        return calls["n"] > 9  # after the hash (6 chunks) and a few chunks of the extraction

    with pytest.raises(archive.Cancelled):
        archive.open_pack(source, set(), is_cancelled=cancelled)
    assert _no_partial(cache_dir)
    assert not (cache_dir / "extracted" / archive.sha256_file(source)).exists()


def test_a_cancel_stops_a_7z_extraction(tmp_path: Path, cache_dir: Path) -> None:
    import py7zr

    source = tmp_path / "many.7z"
    with py7zr.SevenZipFile(source, "w") as z:
        for i in range(8):
            z.writestr(bytes([i]) * 200_000, f"f{i}.bin")
    reports: list[tuple[str, int, int]] = []
    archive.open_pack(source, set(), progress=lambda *a: reports.append(a))
    assert reports[-1][1] == reports[-1][2] == 8 * 200_000
    shutil.rmtree(cache_dir)
    seen = {"n": 0}

    def cancelled() -> bool:
        seen["n"] += 1
        return seen["n"] > 3

    with pytest.raises(archive.Cancelled):
        archive.open_pack(source, set(), is_cancelled=cancelled)
    assert _no_partial(cache_dir)


# ------------------------------------------------------------------------ links, collisions, budget (T12.09)


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("this account may not create symbolic links")


def test_nested_archives_share_one_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = bytes(range(256)) * 8  # 2 KB each
    inner_a = _zip(tmp_path / "a.zip", [("a.bin", payload)])
    inner_b = _zip(tmp_path / "b.zip", [("b.bin", payload)])
    outer = _zip(
        tmp_path / "outer.zip",
        [("a.zip", inner_a.read_bytes()), ("b.zip", inner_b.read_bytes())],
    )
    # the outer archive declares about 4.4 KB, each inner one 2 KB: alone each is below 6 KB
    monkeypatch.setitem(archive.LIMITS, "max_total_bytes", 6000)
    with pytest.raises(RpgGenError) as raised:
        archive.open_pack(outer, set())
    assert raised.value.code == "ARCH-004"
    monkeypatch.setitem(archive.LIMITS, "max_total_bytes", 10_000)
    pack = archive.open_pack(outer, set())  # the same archive within a bigger budget
    assert "ARCH-006" in _codes(pack)


def test_nested_archives_count_their_files_in_the_same_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inner = _zip(tmp_path / "i.zip", [(f"f{n}.txt", b"x") for n in range(4)])
    outer = _zip(tmp_path / "o.zip", [("i.zip", inner.read_bytes()), ("j.zip", inner.read_bytes())])
    monkeypatch.setitem(archive.LIMITS, "max_files", 8)  # 2 outer + 4 + 4 = 10 > 8
    with pytest.raises(RpgGenError) as raised:
        archive.open_pack(outer, set())
    assert raised.value.code == "ARCH-004"


@pytest.mark.skipif(archive.find_7z() is None, reason="7-Zip is not installed")
def test_a_rar_extracts_exactly_the_file_the_collision_report_keeps(tmp_path: Path) -> None:
    import py7zr

    # 7-Zip reads any format through the same command line as a RAR; the entries are named in
    # the order that makes "the last one wins" differ from "the first sorted one is kept".
    source = tmp_path / "pack.7z"
    with py7zr.SevenZipFile(source, "w") as z:
        z.writestr(b"upper", "Tree.png")
        z.writestr(b"lower", "tree.png")
        z.writestr(b"junk", "Thumbs.db")
    dest = tmp_path / "out"
    dest.mkdir()
    issues = archive.IssueList()
    archive._extract_rar(source, dest, issues, archive.Control())
    codes = [i.code for i in issues]
    assert "ARCH-005" in codes and "ARCH-008" in codes
    kept = next(i for i in issues if i.code == "ARCH-005").detail["kept"]
    assert (dest / kept).read_bytes() == b"upper"  # the file ARCH-005 names is the one on disk
    assert not (dest / "Thumbs.db").exists()  # junk was never extracted


def test_a_folder_pack_does_not_follow_a_link_out_of_itself(tmp_path: Path) -> None:
    from rpggen.core import config, inventory

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"\x89PNG-secret")
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "a.png").write_bytes(b"\x89PNG-a")
    _symlink_or_skip(pack / "linked_file.png", outside / "secret.png")
    _symlink_or_skip(pack / "linked_dir", outside)
    files, links = archive.walk_files(pack)
    assert files == ["a.png"] and links == ["linked_dir", "linked_file.png"]
    inv = inventory.build_inventory(archive.open_pack(pack, set()))
    assert [f.path for f in inv.files] == ["a.png"]
    assert sorted(s["path"] for s in inv.skipped if s["reason"] == "link") == [
        "linked_dir",
        "linked_file.png",
    ]
    assert [i.code for i in inv.issues].count("ARCH-009") == 2
    only_a = tmp_path / "only_a"
    only_a.mkdir()
    (only_a / "a.png").write_bytes(b"\x89PNG-a")
    assert config.folder_sha256(pack) == config.folder_sha256(only_a)  # links are not hashed


def test_a_7z_symlink_entry_is_not_extracted(tmp_path: Path) -> None:
    import py7zr

    target = tmp_path / "real.txt"
    target.write_text("real", encoding="utf-8")
    link = tmp_path / "link.txt"
    _symlink_or_skip(link, target)
    source = tmp_path / "links.7z"
    with py7zr.SevenZipFile(source, "w") as z:
        z.write(target, "real.txt")
        z.write(link, "link.txt")
    pack = archive.open_pack(source, set())
    assert "ARCH-009" in _codes(pack)
    assert (pack.root / "real.txt").is_file() and not (pack.root / "link.txt").exists()


def test_scrubbing_removes_links_left_by_an_extractor(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "ok.txt").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    _symlink_or_skip(dest / "sneaky.txt", outside)
    issues = archive.IssueList()
    archive._scrub_links(dest, issues)
    assert (
        not (dest / "sneaky.txt").is_symlink() and outside.read_text(encoding="utf-8") == "outside"
    )
    assert [i.code for i in issues] == ["ARCH-009"]


@pytest.mark.skipif(os.name != "nt", reason="junctions exist on Windows only")
def test_a_junction_is_a_link_too(tmp_path: Path) -> None:
    import subprocess

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"\x89PNG-secret")
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "a.png").write_bytes(b"\x89PNG-a")
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(pack / "junction"), str(outside)],
        capture_output=True,
        check=False,
    )
    if made.returncode != 0:
        pytest.skip("could not create a junction")
    assert archive.walk_files(pack) == (["a.png"], ["junction"])
    issues = archive.IssueList()
    archive._scrub_links(pack, issues)
    assert [i.code for i in issues] == ["ARCH-009"]
    assert not (pack / "junction").exists() and (outside / "secret.png").is_file()  # target intact
