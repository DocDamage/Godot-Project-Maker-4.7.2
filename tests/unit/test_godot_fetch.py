from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from rpggen import godot_target
from rpggen.core import godot_fetch
from rpggen.errors import RpgGenError

VERSION = "4.7.2"


@pytest.fixture(autouse=True)
def _unpinned(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tests below build their own archives, whose hash is not the one pinned for 4.7.2; the
    pinned check has tests of its own further down."""
    monkeypatch.setattr(godot_target, "SHA512", {})


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


def test_cancel_mid_download_keeps_the_part_file_for_the_next_attempt(tmp_path: Path) -> None:
    calls = {"n": 0}

    def cancelled() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    big = _zip({godot_fetch.console_name(VERSION): b"x" * (3 << 20)})
    with pytest.raises(godot_fetch.FetchCancelled):
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(big), is_cancelled=cancelled)
    part = tmp_path / f"{godot_fetch.zip_name(VERSION)}.part"
    assert part.is_file() and part.stat().st_size > 0
    assert (tmp_path / (part.name + ".json")).is_file()  # what the next attempt needs to continue
    assert not (tmp_path / godot_fetch.console_name(VERSION)).exists()


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


# ------------------------------------------------------------------------ pinned, resumed, retried (T12.21)

BIG = _zip({**GOOD, godot_fetch.console_name(VERSION): b"c" * (3 << 20)})
NAME = godot_fetch.zip_name(VERSION)


class _Range(io.BytesIO):
    def __init__(self, data: bytes, *, status: int = 200, total: int | None = None, etag="v1"):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Length": str(len(data)), "ETag": etag}
        if status == 206:
            self.headers["Content-Range"] = f"bytes 0-{len(data)}/{total}"
        self.fail_after: int | None = None
        self._given = 0

    def read(self, n: int = -1) -> bytes:
        if self.fail_after is not None and self._given >= self.fail_after:
            raise ConnectionResetError("the connection dropped")
        chunk = super().read(n)
        self._given += len(chunk)
        return chunk


class Server:
    """A fake release server: sums and the archive, with Range support, and a way to break."""

    def __init__(self, archive: bytes, *, ranges: bool = True, drop_first_at: int | None = None):
        self.archive = archive
        self.ranges = ranges
        self.drop_first_at = drop_first_at
        self.requests: list[dict[str, str]] = []
        self.digest = hashlib.sha512(archive).hexdigest()

    def __call__(self, url: str, headers: dict[str, str] | None = None):
        if url.endswith("SHA512-SUMS.txt"):
            return _Resp(f"{self.digest}  {NAME}\n".encode())
        self.requests.append(dict(headers or {}))
        start = 0
        if headers and self.ranges and "Range" in headers:
            start = int(headers["Range"].removeprefix("bytes=").removesuffix("-"))
            assert headers.get("If-Range") == "v1"  # the etag of the first response
            resp = _Range(self.archive[start:], status=206, total=len(self.archive))
        else:
            resp = _Range(self.archive)
        if self.drop_first_at is not None and len(self.requests) == 1:
            resp.fail_after = self.drop_first_at
        return resp


def _pin(monkeypatch: pytest.MonkeyPatch, archive: bytes, platform: str = "windows") -> str:
    digest = hashlib.sha512(archive).hexdigest()
    monkeypatch.setattr(godot_target, "SHA512", {platform: digest})
    return digest


def test_the_pinned_checksum_is_required_even_when_the_release_list_agrees_with_the_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _zip(GOOD)
    monkeypatch.setattr(godot_target, "SHA512", {"windows": "0" * 128})  # not this file's hash
    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(archive))  # sums say it is fine
    assert ei.value.code == "ENV-011"
    assert not (tmp_path / godot_fetch.console_name(VERSION)).exists()


def test_a_release_list_that_disagrees_with_the_pin_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _zip(GOOD)
    _pin(monkeypatch, archive)
    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(archive, sha="1" * 128))
    assert ei.value.code == "ENV-011" and "does not match" in ei.value.issue.message


def test_the_pin_alone_is_enough_when_the_list_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _zip(GOOD)
    _pin(monkeypatch, archive)
    exe = godot_fetch.fetch(VERSION, tmp_path, opener=_opener(archive, sums=False))
    assert exe.read_bytes() == b"console"


def test_another_version_is_checked_against_the_list_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(godot_target, "SHA512", {"windows": "0" * 128})  # pins 4.7.2 only
    other = "4.6.1"
    archive = _zip(
        {godot_fetch.console_name(other): b"c", f"Godot_v{other}-stable_win64.exe": b"g"}
    )
    name = godot_fetch.zip_name(other)
    digest = hashlib.sha512(archive).hexdigest()

    def opener(url: str, headers=None):
        if url.endswith("SHA512-SUMS.txt"):
            return _Resp(f"{digest}  {name}\n".encode())
        return _Resp(archive)

    assert godot_fetch.fetch(other, tmp_path, opener=opener).exists()


def test_the_pinned_hashes_of_this_version_are_present_and_well_formed() -> None:
    import importlib

    real = importlib.reload(godot_target)  # undo the fixture's empty pin for this check
    assert set(real.SHA512) == {"windows", "linux", "macos"}
    for digest in real.SHA512.values():
        assert len(digest) == 128 and int(digest, 16) >= 0 and digest == digest.lower()
    assert godot_fetch.pinned_sha512(real.VERSION, "linux") == real.SHA512["linux"]
    assert godot_fetch.pinned_sha512("4.0.0", "linux") is None


def test_a_dropped_connection_is_resumed_with_range_and_if_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin(monkeypatch, BIG)
    server = Server(BIG, drop_first_at=1 << 20)
    sleeps: list[float] = []
    seen: list[tuple[int, int]] = []
    exe = godot_fetch.fetch(
        VERSION,
        tmp_path,
        opener=server,
        sleep=sleeps.append,
        progress=lambda d, t: seen.append((d, t)),
    )
    assert exe.read_bytes() == b"c" * (3 << 20)
    assert len(server.requests) == 2 and server.requests[0] == {}
    resumed = server.requests[1]["Range"]
    assert resumed.startswith("bytes=") and int(resumed[6:-1]) >= 1 << 20
    assert server.requests[1]["If-Range"] == "v1"
    assert round(sum(sleeps), 1) == 2.0  # one retry, after two seconds
    assert seen[-1][0] == seen[-1][1] == len(BIG)  # the progress covers the whole file
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(GOOD)  # no .part left


def test_a_server_that_ignores_range_restarts_from_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin(monkeypatch, BIG)
    server = Server(BIG, ranges=False, drop_first_at=1 << 20)
    exe = godot_fetch.fetch(VERSION, tmp_path, opener=server, sleep=lambda s: None)
    assert exe.exists() and len(server.requests) == 2
    assert "Range" in server.requests[1]  # it asked, and got the whole file with a 200


def test_a_cancelled_download_is_resumed_by_the_next_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin(monkeypatch, BIG)
    server = Server(BIG)
    flips = {"n": 0}

    def cancel_after_one_chunk() -> bool:
        flips["n"] += 1
        return flips["n"] > 2

    with pytest.raises(godot_fetch.FetchCancelled):
        godot_fetch.fetch(VERSION, tmp_path, opener=server, is_cancelled=cancel_after_one_chunk)
    kept = (tmp_path / (NAME + ".part")).stat().st_size
    assert 0 < kept < len(BIG)
    exe = godot_fetch.fetch(VERSION, tmp_path, opener=server)
    assert exe.exists()
    assert server.requests[-1]["Range"] == f"bytes={kept}-"


def test_a_network_error_is_retried_three_times_with_growing_pauses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _zip(GOOD)
    _pin(monkeypatch, archive)
    tries = {"n": 0}

    def opener(url: str, headers=None):
        if url.endswith("SHA512-SUMS.txt"):
            return _Resp(f"{hashlib.sha512(archive).hexdigest()}  {NAME}\n".encode())
        tries["n"] += 1
        raise ConnectionResetError("no route")

    sleeps: list[float] = []
    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, opener=opener, sleep=sleeps.append)
    assert ei.value.code == "ENV-011" and tries["n"] == 4  # the first try and three retries
    assert round(sum(sleeps), 1) == 17.0  # 2 + 5 + 10 seconds
    assert godot_fetch.RETRY_DELAYS_S == (2.0, 5.0, 10.0)


def test_an_answer_that_waiting_cannot_change_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    archive = _zip(GOOD)
    _pin(monkeypatch, archive)
    tries = {"n": 0}

    def opener(url: str, headers=None):
        if url.endswith("SHA512-SUMS.txt"):
            return _Resp(f"{hashlib.sha512(archive).hexdigest()}  {NAME}\n".encode())
        tries["n"] += 1
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    with pytest.raises(RpgGenError):
        godot_fetch.fetch(VERSION, tmp_path, opener=opener, sleep=lambda s: None)
    assert tries["n"] == 1


def test_a_range_that_cannot_be_satisfied_starts_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    _pin(monkeypatch, BIG)
    (tmp_path / (NAME + ".part")).write_bytes(b"garbage")
    (tmp_path / (NAME + ".part.json")).write_text(
        json.dumps({"url": godot_fetch.release_url(VERSION, NAME), "bytes": 7, "etag": "v1"}),
        encoding="utf-8",
    )
    server = Server(BIG)

    def opener(url: str, headers=None):
        if headers and "Range" in headers:
            raise urllib.error.HTTPError(url, 416, "Range Not Satisfiable", {}, None)  # type: ignore[arg-type]
        return server(url, headers)

    assert godot_fetch.fetch(VERSION, tmp_path, opener=opener).exists()


def test_a_bad_download_is_not_kept_for_resuming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _zip(GOOD)
    monkeypatch.setattr(godot_target, "SHA512", {"windows": "0" * 128})
    with pytest.raises(RpgGenError):
        godot_fetch.fetch(VERSION, tmp_path, opener=_opener(archive))
    assert list(tmp_path.iterdir()) == []  # a wrong file is not a half file


# ------------------------------------------------------------------ T12.63: Linux and macOS


@pytest.mark.parametrize(
    ("platform", "archive", "exe"),
    [
        ("windows", "Godot_v4.7.2-stable_win64.exe.zip", "Godot_v4.7.2-stable_win64_console.exe"),
        ("linux", "Godot_v4.7.2-stable_linux.x86_64.zip", "Godot_v4.7.2-stable_linux.x86_64"),
        ("macos", "Godot_v4.7.2-stable_macos.universal.zip", "Godot.app/Contents/MacOS/Godot"),
    ],
)
def test_file_names_per_platform(platform: str, archive: str, exe: str) -> None:
    assert godot_fetch.zip_name(VERSION, platform) == archive
    assert godot_fetch.console_name(VERSION, platform) == exe
    assert godot_target.SHA512.get(platform) is None  # the autouse fixture clears the pins
    assert platform in godot_fetch.PLATFORMS and platform in godot_fetch.DOWNLOAD_MB


def test_the_current_platform_follows_sys_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    for value, expected in (("win32", "windows"), ("darwin", "macos"), ("linux", "linux")):
        monkeypatch.setattr(godot_fetch.sys, "platform", value)
        assert godot_fetch.current_platform() == expected


def _mac_zip(extra: dict[str, tuple[bytes, int]] | None = None) -> bytes:
    """A small Godot.app: (data, unix mode) per member; directories end with a slash."""
    members = {
        "Godot.app/": (b"", 0o40755),
        "Godot.app/Contents/": (b"", 0o40755),
        "Godot.app/Contents/Info.plist": (b"<plist/>", 0o100644),
        "Godot.app/Contents/MacOS/": (b"", 0o40755),
        "Godot.app/Contents/MacOS/Godot": (b"mach-o", 0o100755),
        "Godot.app/Contents/Resources/en.lproj/": (b"", 0o40755),
        **(extra or {}),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, (data, mode) in members.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            zf.writestr(info, data)
    return buf.getvalue()


def _mac_opener(archive: bytes):
    name = godot_fetch.zip_name(VERSION, "macos")
    digest = hashlib.sha512(archive).hexdigest()

    def opener(url: str):
        if url.endswith("SHA512-SUMS.txt"):
            return _Resp(f"{digest}  {name}\n".encode())
        assert url.endswith(name)
        return _Resp(archive)

    return opener


def test_the_macos_app_is_extracted_as_a_tree(tmp_path: Path) -> None:
    exe = godot_fetch.fetch(VERSION, tmp_path, "macos", opener=_mac_opener(_mac_zip()))
    assert exe == tmp_path / "Godot.app" / "Contents" / "MacOS" / "Godot"
    assert exe.read_bytes() == b"mach-o"
    assert (tmp_path / "Godot.app/Contents/Info.plist").is_file()
    assert (tmp_path / "Godot.app/Contents/Resources/en.lproj").is_dir()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Godot.app"]  # no .part, no .extract
    # a second call finds it without downloading
    assert godot_fetch.fetch(VERSION, tmp_path, "macos", opener=None) == exe


@pytest.mark.parametrize(
    ("name", "mode"),
    [
        ("evil.sh", 0o100755),  # outside Godot.app
        ("Godot.app/../evil.sh", 0o100644),
        ("/Godot.app/evil.sh", 0o100644),
        ("Godot.app/Contents/link", 0o120777),  # a symbolic link
    ],
)
def test_unsafe_macos_members_are_rejected(tmp_path: Path, name: str, mode: int) -> None:
    archive = _mac_zip({name: (b"x", mode)})
    with pytest.raises(RpgGenError) as ei:
        godot_fetch.fetch(VERSION, tmp_path, "macos", opener=_mac_opener(archive))
    assert ei.value.code == "ENV-011"
    assert list(tmp_path.iterdir()) == []


def test_a_macos_archive_without_the_executable_is_refused(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Godot.app/Contents/Info.plist", b"<plist/>")
    with pytest.raises(RpgGenError, match="Godot.app/Contents/MacOS/Godot"):
        godot_fetch.fetch(VERSION, tmp_path, "macos", opener=_mac_opener(buf.getvalue()))
