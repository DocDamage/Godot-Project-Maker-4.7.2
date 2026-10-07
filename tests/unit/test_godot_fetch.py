from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from rpggen.core import godot_fetch
from rpggen.errors import RpgGenError

VERSION = "4.7.2"


class _Resp(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _opener(archive: bytes, sha: str | None = None, *, sums: bool = True):
    name = godot_fetch.zip_name(VERSION)
    digest = sha or hashlib.sha512(archive).hexdigest()

    def opener(url: str):
        if url.endswith("SHA512-SUMS.txt"):
            if not sums:
                raise OSError("no sums")
            return _Resp(f"{digest}  {name}\n".encode())
        assert url.endswith(name)
        return _Resp(archive)

    return opener


GOOD = {
    godot_fetch.console_name(VERSION): b"console",
    f"Godot_v{VERSION}-stable_win64.exe": b"gui",
}


def test_good_archive_is_extracted_and_leftovers_removed(tmp_path: Path) -> None:
    seen: list[tuple[int, int]] = []
    exe = godot_fetch.fetch(
        VERSION, tmp_path, opener=_opener(_zip(GOOD)), progress=lambda d, t: seen.append((d, t))
    )
    assert exe.read_bytes() == b"console"
    assert seen and seen[-1][0] == seen[-1][1]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(GOOD)


def test_wrong_checksum_extracts_nothing_and_removes_the_part_file(tmp_path: Path) -> None:
    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(_zip(GOOD), sha="0" * 128))
    assert ei.value.code == "ENV-011"
    assert list(tmp_path.iterdir()) == []


def test_missing_checksum_is_refused_unless_allowed(tmp_path: Path) -> None:
    with pytest.raises(RpgGenError):
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(_zip(GOOD), sums=False))
    exe = godot_fetch.fetch(
        VERSION, tmp_path, opener=_opener(_zip(GOOD), sums=False), require_checksum=False
    )
    assert exe.exists()


def test_cancel_mid_download_leaves_nothing(tmp_path: Path) -> None:
    calls = {"n": 0}

    def cancelled() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    big = _zip({godot_fetch.console_name(VERSION): b"x" * (3 << 20)})
    with pytest.raises(godot_fetch.FetchCancelled):
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(big), is_cancelled=cancelled)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("evil", ["..\\evil.exe", "../evil.exe", "C:/evil.exe", "sub/evil.exe"])
def test_archives_with_unexpected_or_unsafe_members_are_rejected(tmp_path: Path, evil: str) -> None:
    archive = _zip({**GOOD, evil: b"bad"})
    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(archive))
    assert ei.value.code == "ENV-011"
    assert list(tmp_path.iterdir()) == []
    assert not (tmp_path.parent / "evil.exe").exists()


def test_network_failure_is_env_011(tmp_path: Path) -> None:
    def broken(url: str):
        raise OSError("offline")

    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, opener=broken)
    assert ei.value.code == "ENV-011"


def test_managed_copy_is_found_first(tmp_path: Path, monkeypatch) -> None:
    from rpggen.core import godot

    managed = tmp_path / "godot" / VERSION
    managed.mkdir(parents=True)
    exe = managed / godot_fetch.console_name(VERSION)
    exe.write_bytes(b"x")
    other = tmp_path / "Godot_a.exe"
    other.write_bytes(b"x")
    monkeypatch.setattr(godot_fetch, "managed_dir", lambda version=VERSION: managed)
    monkeypatch.setenv("RPGGEN_GODOT", str(other))
    found = godot.auto_find_godot()
    assert found[0] == exe
    assert other in found
