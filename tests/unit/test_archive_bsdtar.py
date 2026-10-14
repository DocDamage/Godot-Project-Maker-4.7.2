"""A rar opened with the system's bsdtar when 7-Zip is not installed (T17.29)."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import archive
from rpggen.errors import RpgGenError

LISTING = (
    "-rw-r--r--  0 0      0        1746 Jun 20  2024 Pack/Animals/Baby Chicken Black.png\r\n"
    "drwxr-xr-x  0 0      0           0 Jun 20  2024 Pack/Animals/\r\n"
    "-rw-rw-r--  0 user   staff      10 Oct 14 01:12 Pack/café/tile [1].png\r\n"
    "-rw-rw-r--  0 0      0           1 déc.  3 01:12 Pack/a  b/ two  spaces .png\r\n"
    "lrw-r--r--  0 0      0           0 Dec 31  1969 Pack/lnk -> Pack/Animals/x.png\r\n"
    "hrw-r--r--  0 0      0           0 Dec 31  1969 Pack/hl link to Pack/x.png\r\n"
    "-rw-r--r--  0 0      0          96 Jun 20  2024 Pack/Can’t find it Read me!.txt\r\n"
    "-rw-r--r--  0 0      0           4 Jun 20  2024 Pack/Thumbs.db\r\n"
    "tar.exe: some note that is not an entry\r\n"
)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return paths.cache_dir()


def test_the_listing_gives_regular_files_with_their_sizes() -> None:
    issues = archive.IssueList()
    entries = archive._parse_tar_listing(LISTING, issues)
    assert [(e.name, e.size) for e in entries] == [
        ("Pack/Animals/Baby Chicken Black.png", 1746),
        ("Pack/café/tile [1].png", 10),
        ("Pack/a  b/ two  spaces .png", 1),
        ("Pack/Can’t find it Read me!.txt", 96),
        ("Pack/Thumbs.db", 4),
    ]
    assert [(i.code, i.detail["entry"]) for i in issues] == [
        ("ARCH-009", "Pack/lnk"),
        ("ARCH-009", "Pack/hl"),
    ]


def _fake_tar(
    monkeypatch: pytest.MonkeyPatch,
    listing: str,
    files: dict[str, bytes],
    *,
    returncode: int = 0,
    stderr: str = "",
) -> list[list[str]]:
    """bsdtar mocked: ``-tvf`` gives ``listing``, ``-xf`` writes ``files`` under ``-C`` (on a
    case-insensitive disk two names that differ in case land in one file, the last winning),
    ``-xOf`` writes the one file named to its stdout."""
    calls: list[list[str]] = []

    def run(command, ctl, encoding, *, stdout=subprocess.PIPE, poll=None):
        calls.append(command)
        if "-tvf" in command:
            return subprocess.CompletedProcess(command, returncode, listing, stderr)
        if "-xf" in command:
            root = Path(command[command.index("-C") + 1])
            for name, data in files.items():
                target = root.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            if poll is not None:
                poll()
            return subprocess.CompletedProcess(command, returncode, "", stderr)
        assert "-xOf" in command
        stdout.write(files[command[-1]])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(archive, "find_7z", lambda: None)
    monkeypatch.setattr(archive, "find_bsdtar", lambda: Path("bsdtar"))
    monkeypatch.setattr(archive, "_run_tool", run)
    return calls


def _listing(files: dict[str, bytes]) -> str:
    return "".join(
        f"-rw-r--r--  0 0      0 {len(data):11d} Jun 20  2024 {name}\n"
        for name, data in files.items()
    )


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_without_7zip_a_rar_is_opened_with_bsdtar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {
        "Pack/a.png": b"aaaa",
        "Pack/sub dir/b.png": b"bb",
        "Pack/Thumbs.db": b"junk",
        "__MACOSX/Pack/._a.png": b"mac",
    }
    _fake_tar(monkeypatch, _listing(files), files)
    source = tmp_path / "x.rar"
    source.write_bytes(b"Rar!")
    reports: list[tuple[str, int, int]] = []
    pack = archive.open_pack(source, set(), progress=lambda *a: reports.append(a))
    assert pack.kind == "rar"
    assert [n for n in _files(pack.root) if n != ".complete"] == [
        "Pack/a.png",
        "Pack/sub dir/b.png",
    ]
    assert [i.code for i in pack.issues].count("ARCH-008") == 2  # the junk never reached it
    assert reports[-1] == ("Extracting x.rar", 6, 6)
    assert not [p for p in pack.root.parent.iterdir() if "rar_" in p.name]


def test_the_kept_name_of_a_case_collision_is_the_file_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {"Tree.png": b"upper", "tree.png": b"lower"}
    calls = _fake_tar(monkeypatch, _listing(files), files)
    dest = tmp_path / "out"
    dest.mkdir()
    issues = archive.IssueList()
    archive._extract_rar(tmp_path / "x.rar", dest, issues, archive.Control())
    kept = next(i for i in issues if i.code == "ARCH-005").detail["kept"]
    assert kept == "Tree.png"
    assert (dest / kept).read_bytes() == b"upper"
    assert ["-xOf" in c for c in calls].count(True) == 1


def test_an_unsafe_name_is_refused_before_anything_is_extracted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_tar(monkeypatch, _listing({"../evil.png": b"x"}), {})
    with pytest.raises(RpgGenError) as raised:
        archive._extract_rar(tmp_path / "x.rar", tmp_path, archive.IssueList(), archive.Control())
    assert raised.value.code == "ARCH-003"
    assert not any("-xf" in c for c in calls)


def test_the_limits_apply_before_anything_is_extracted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(archive.LIMITS, "max_files", 2)
    files = {f"f{n}.png": b"x" for n in range(3)}
    calls = _fake_tar(monkeypatch, _listing(files), files)
    with pytest.raises(RpgGenError) as raised:
        archive._extract_rar(tmp_path / "x.rar", tmp_path, archive.IssueList(), archive.Control())
    assert raised.value.code == "ARCH-004"
    assert not any("-xf" in c for c in calls)


def test_an_archive_that_writes_more_than_it_declares_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tar(monkeypatch, _listing({"a.png": b"x"}), {"a.png": b"x" * 5000})
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(RpgGenError) as raised:
        archive._extract_rar(tmp_path / "x.rar", dest, archive.IssueList(), archive.Control())
    assert raised.value.code == "ARCH-004"


def test_names_bsdtar_cannot_read_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {"a.png": b"x"}
    stderr = (
        "tar.exe: Archive entry has empty or unreadable filename ... skipping\r\n"
        "tar.exe: Error exit delayed from previous errors\r\n"
    )
    _fake_tar(monkeypatch, _listing(files), files, returncode=1, stderr=stderr)
    dest = tmp_path / "out"
    dest.mkdir()
    issues = archive.IssueList()
    archive._extract_rar(tmp_path / "x.rar", dest, issues, archive.Control())
    assert _files(dest) == ["a.png"]
    issue = next(i for i in issues if i.code == "ARCH-010")
    assert issue.detail["count"] == 1


def test_another_tar_error_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_tar(monkeypatch, "", {}, returncode=1, stderr="tar.exe: Unrecognized archive format")
    with pytest.raises(RpgGenError) as raised:
        archive._extract_rar(tmp_path / "x.rar", tmp_path, archive.IssueList(), archive.Control())
    assert raised.value.code == "ARCH-001"
    assert "Unrecognized" in raised.value.detail["reason"]


def test_no_7zip_and_no_bsdtar_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive, "find_7z", lambda: None)
    monkeypatch.setattr(archive, "find_bsdtar", lambda: None)
    with pytest.raises(RpgGenError) as raised:
        archive._extract_rar(tmp_path / "x.rar", tmp_path, archive.IssueList(), archive.Control())
    assert raised.value.code == "ARCH-007"


def test_gnu_tar_is_not_taken_for_bsdtar(monkeypatch: pytest.MonkeyPatch) -> None:
    def version(command, **_kw):
        out = "tar (GNU tar) 1.35\n" if "gnu" in command[0] else "bsdtar 3.8.8 - libarchive\n"
        return subprocess.CompletedProcess(command, 0, out, "")

    archive._is_bsdtar.cache_clear()
    monkeypatch.setattr(archive.subprocess, "run", version)
    try:
        assert not archive._is_bsdtar("gnu/tar")
        assert archive._is_bsdtar("System32/tar.exe")
    finally:
        archive._is_bsdtar.cache_clear()


BSDTAR = archive.find_bsdtar()


@pytest.mark.skipif(BSDTAR is None, reason="the system's tar is not bsdtar")
def test_a_real_archive_through_bsdtar(tmp_path: Path) -> None:
    source = tmp_path / "pack.zip"
    with zipfile.ZipFile(source, "w") as zf:
        zf.writestr("Pack/Tree.png", b"upper")
        zf.writestr("Pack/tree.png", b"lower")
        zf.writestr("Pack/sub dir/a b.png", b"ab")
        zf.writestr("Pack/Thumbs.db", b"junk")
    dest = tmp_path / "out"
    dest.mkdir()
    issues = archive.IssueList()
    assert BSDTAR is not None
    archive._extract_with_bsdtar(BSDTAR, source, dest, issues, archive.Control())
    assert _files(dest) == ["Pack/Tree.png", "Pack/sub dir/a b.png"]
    assert (dest / "Pack" / "Tree.png").read_bytes() == b"upper"
    codes = [i.code for i in issues]
    assert "ARCH-005" in codes and "ARCH-008" in codes
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("rpggen_rar_")]
