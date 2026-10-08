"""Download the official Godot build (T11.04).

Used by the Project page's "Download Godot" button and, through ``tools/fetch_godot.py``, by CI.
The archive is streamed to ``<name>.part``, its SHA-512 is checked *before* anything is
extracted, and only the expected executables are extracted (any other member, ``..`` or a drive
letter rejects the archive).

The checksum of the version this program is built for is pinned in ``godot_target.SHA512``; the
release's ``SHA512-SUMS.txt`` is still read and must agree with it. Another version
(``tools/fetch_godot.py --version``) is verified against the sums file alone.

On macOS the archive holds ``Godot.app``: every member must lie under that folder (no ``..``, no
links), the tree is extracted as it is, and the executable is ``Godot.app/Contents/MacOS/Godot``.

A download that stops (the network, or the user) leaves ``<name>.part`` and ``<name>.part.json``
(url, bytes, etag); the next attempt asks for the rest with ``Range`` / ``If-Range`` and only
starts again when the server cannot continue. A network error is retried three times (2, 5 and
10 seconds apart); the half file of a week ago is removed by ``cache_policy``.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import shutil
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from rpggen import godot_target, paths
from rpggen.errors import RpgGenError

BASE = "https://github.com/godotengine/godot/releases/download/{v}-stable"
DEFAULT_VERSION = godot_target.VERSION
CHUNK = 1 << 20
DOWNLOAD_TIMEOUT_S = 60
SUMS_LIMIT = 1 << 20

# ``opener(url)`` or, to resume, ``opener(url, headers)``: a context manager with ``.read(n)``,
# and optionally ``.headers`` and ``.status`` (206 when the server continues a download).
Opener = Callable[..., Any]
Progress = Callable[[int, int], None]
RETRY_DELAYS_S = (2.0, 5.0, 10.0)  # the pauses before the 1st, 2nd and 3rd retry


class FetchCancelled(Exception):
    """The user cancelled the download; nothing is left behind."""


PLATFORMS = ("windows", "linux", "macos")
MAC_APP = "Godot.app"
# the size of the download in MB, for the button text (approximate, the same for every 4.x)
DOWNLOAD_MB = {"windows": 85, "linux": 80, "macos": 170}


def current_platform() -> str:
    """``windows``, ``macos`` or ``linux``: the Godot build that runs on this computer."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def zip_name(version: str, platform: str = "windows") -> str:
    if platform == "linux":
        return f"Godot_v{version}-stable_linux.x86_64.zip"
    if platform == "macos":
        return f"Godot_v{version}-stable_macos.universal.zip"
    return f"Godot_v{version}-stable_win64.exe.zip"


def console_name(version: str, platform: str = "windows") -> str:
    """The executable to run, relative to the download folder: the console build on Windows,
    the only build on Linux, the executable inside the app on macOS."""
    if platform == "linux":
        return f"Godot_v{version}-stable_linux.x86_64"
    if platform == "macos":
        return f"{MAC_APP}/Contents/MacOS/Godot"
    return f"Godot_v{version}-stable_win64_console.exe"


def expected_members(version: str, platform: str = "windows") -> set[str]:
    """The exact members of a flat archive (Windows, Linux); macOS uses ``_safe_app_member``."""
    if platform == "linux":
        return {console_name(version, platform)}
    return {console_name(version, platform), f"Godot_v{version}-stable_win64.exe"}


def release_url(version: str, filename: str) -> str:
    return f"{BASE.format(v=version)}/{filename}"


SOURCE_LABEL = "github.com/godotengine/godot/releases"


def parse_sums(text: str) -> dict[str, str]:
    """Parse ``<hash>  <filename>`` lines of a SHA512-SUMS file."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            sums[parts[-1].lstrip("*")] = parts[0].lower()
    return sums


def managed_dir(version: str = DEFAULT_VERSION) -> Path:
    """Where rpggen keeps the Godot it downloaded itself."""
    return paths.data_dir() / "godot" / version


def managed_executable(version: str = DEFAULT_VERSION, platform: str | None = None) -> Path:
    """The downloaded Godot for ``platform`` (default: this computer's)."""
    return managed_dir(version) / console_name(version, platform or current_platform())


def default_opener(url: str, headers: dict[str, str] | None = None) -> Any:
    if not url.lower().startswith("https://"):
        raise OSError(f"refusing a non-https URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "rpggen", **(headers or {})})
    return urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S)  # noqa: S310


def pinned_sha512(version: str, platform: str) -> str | None:
    """The checksum built into this program for ``version`` (only the validated version has one)."""
    if version != godot_target.VERSION:
        return None
    value = godot_target.SHA512.get(platform)
    return value.lower() if value else None


def _fail(reason: str) -> RpgGenError:
    return RpgGenError("ENV-011", reason=reason)


def _safe_member(name: str, allowed: set[str]) -> bool:
    if name not in allowed:
        return False
    return not (
        ".." in PurePosixPath(name).parts
        or PureWindowsPath(name).drive
        or name.startswith(("/", "\\"))
        or "\\" in name
        or "/" in name
    )


def _safe_app_member(info: zipfile.ZipInfo) -> bool:
    """A member of the macOS archive: a relative path under ``Godot.app/`` without ``..``,
    backslashes or a drive, and not a link."""
    name = info.filename
    parts = PurePosixPath(name).parts
    if (
        not parts
        or parts[0] != MAC_APP
        or ".." in parts
        or "\\" in name
        or name.startswith("/")
        or PureWindowsPath(name).drive
    ):
        return False
    return not stat.S_ISLNK(info.external_attr >> 16)


def _extract_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, staging: Path) -> None:
    dst = staging.joinpath(*PurePosixPath(info.filename).parts)
    if info.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(info) as src, dst.open("wb") as out:
        shutil.copyfileobj(src, out)
    mode = (info.external_attr >> 16) & 0o777
    if mode & 0o111:  # keep the executable bit (macOS): 0755, never more
        dst.chmod(0o755)


def _info_path(part: Path) -> Path:
    return part.with_name(part.name + ".json")


def _forget(part: Path) -> None:
    """Remove a half download and its description."""
    with contextlib.suppress(OSError):
        part.unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        _info_path(part).unlink(missing_ok=True)


def _read_info(part: Path, url: str) -> dict[str, Any]:
    """What was recorded about the half download, or {} when it cannot be continued."""
    try:
        info = json.loads(_info_path(part).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return info if isinstance(info, dict) and info.get("url") == url and part.is_file() else {}


def _content_total(headers: Any, ranged: bool) -> int:
    """The size of the whole file from the response headers (0 when unknown)."""
    if headers is None:
        return 0
    try:
        if ranged:
            return int(str(headers.get("Content-Range", "")).rpartition("/")[2])
        return int(headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        return 0


def _download_once(
    opener: Opener,
    url: str,
    part: Path,
    progress: Progress | None,
    is_cancelled: Callable[[], bool] | None,
) -> str:
    """One attempt: continue ``part`` when the server can, else start again. Returns the SHA-512
    hex digest of the whole file."""
    info = _read_info(part, url)
    have = part.stat().st_size if info else 0
    wanted: dict[str, str] = {}
    if have:
        wanted["Range"] = f"bytes={have}-"
        if info.get("etag"):
            wanted["If-Range"] = str(info["etag"])
    try:
        response = opener(url, wanted) if wanted else opener(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and have:  # the half file is not a part of what the server has
            _forget(part)
            return _download_once(opener, url, part, progress, is_cancelled)
        raise
    digest = hashlib.sha512()
    with response as resp:
        headers = getattr(resp, "headers", None)
        ranged = have > 0 and getattr(resp, "status", 200) == 206
        if ranged:  # the hash reads what is already there once
            with part.open("rb") as kept:
                for chunk in iter(lambda: kept.read(CHUNK), b""):
                    digest.update(chunk)
            done = have
        else:
            done = 0
        total = _content_total(headers, ranged)
        etag = headers.get("ETag") if headers is not None else None
        _info_path(part).write_text(
            json.dumps({"url": url, "bytes": done, "etag": etag or ""}), encoding="utf-8"
        )
        with part.open("ab" if ranged else "wb") as fh:
            while True:
                if is_cancelled is not None and is_cancelled():
                    raise FetchCancelled
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
    return digest.hexdigest()


def _is_final(exc: BaseException) -> bool:
    """An answer that waiting will not change (404, 403 ...); 408 and 429 are worth a retry."""
    return (
        isinstance(exc, urllib.error.HTTPError)
        and 400 <= exc.code < 500
        and exc.code not in (408, 429)
    )


def _pause(
    seconds: float, is_cancelled: Callable[[], bool] | None, sleep: Callable[[float], None]
) -> None:
    """Wait before a retry in short steps, so that a cancel is not held up."""
    waited = 0.0
    while waited < seconds:
        if is_cancelled is not None and is_cancelled():
            raise FetchCancelled
        step = min(0.2, seconds - waited)
        sleep(step)
        waited += step


def _download(
    opener: Opener,
    url: str,
    part: Path,
    progress: Progress | None,
    is_cancelled: Callable[[], bool] | None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Stream ``url`` to ``part`` (resuming a kept half file), retrying a network error three
    times; returns the SHA-512 hex digest of the whole file. A cancel or a failure that survives
    the retries keeps ``part`` for the next attempt."""
    attempt = 0
    while True:
        try:
            return _download_once(opener, url, part, progress, is_cancelled)
        except FetchCancelled:
            raise
        except (OSError, http.client.HTTPException) as exc:
            if _is_final(exc) or attempt >= len(RETRY_DELAYS_S):
                raise _fail(f"the download stopped and could not be continued: {exc}") from exc
            delay = RETRY_DELAYS_S[attempt]
            attempt += 1
            _pause(delay, is_cancelled, sleep)


def fetch(
    version: str,
    out: Path,
    platform: str = "windows",
    *,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    opener: Opener | None = None,
    require_checksum: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Download Godot ``version`` into ``out`` and return the console executable.

    The validated version must match the checksum pinned in ``godot_target.SHA512``, and the
    release's own list must say the same (ENV-011 when they differ); another version is checked
    against the release's list alone. A download that is cancelled or runs out of retries leaves
    its ``.part`` file for the next attempt; every other outcome removes it.

    Raises ``RpgGenError("ENV-011")`` for every failure and ``FetchCancelled`` on cancel."""
    opener = opener or default_opener
    out = Path(out)
    console = out / console_name(version, platform)
    if console.exists():
        return console
    name = zip_name(version, platform)
    part = out / f"{name}.part"
    staging = out / ".extract"
    keep_part = False
    try:
        out.mkdir(parents=True, exist_ok=True)
        try:
            with opener(release_url(version, "SHA512-SUMS.txt")) as resp:
                sums = parse_sums(resp.read(SUMS_LIMIT).decode("utf-8", "replace"))
        except OSError:
            sums = {}
        listed = sums.get(name)
        pinned = pinned_sha512(version, platform)
        if pinned is not None and listed is not None and pinned != listed:
            raise _fail("the release's checksum list does not match the checksum built into rpggen")
        expected = pinned or listed
        if expected is None and require_checksum:
            raise _fail("the release has no SHA-512 checksum to verify the download against")
        keep_part = True  # until the download is whole, what was fetched is worth keeping
        try:
            actual = _download(
                opener, release_url(version, name), part, progress, is_cancelled, sleep
            )
        except FetchCancelled:
            raise
        keep_part = False
        if expected is not None and actual != expected:
            raise _fail(f"the download's SHA-512 does not match the release ({name})")
        allowed = expected_members(version, platform)
        rel = console_name(version, platform)
        try:
            with zipfile.ZipFile(part) as zf:
                if platform == "macos":
                    infos = zf.infolist()
                    bad = [i.filename for i in infos if not _safe_app_member(i)]
                else:
                    infos = [i for i in zf.infolist() if not i.is_dir()]
                    bad = [i.filename for i in infos if not _safe_member(i.filename, allowed)]
                if bad:
                    raise _fail(f"the archive contains an unexpected file: {bad[0]}")
                shutil.rmtree(staging, ignore_errors=True)
                staging.mkdir()
                for info in infos:
                    _extract_member(zf, info, staging)
        except zipfile.BadZipFile as exc:
            raise _fail("the downloaded file is not a valid archive") from exc
        if not staging.joinpath(*PurePosixPath(rel).parts).is_file():
            raise _fail(f"{rel} is not in the downloaded archive")
        for member in staging.iterdir():
            member.replace(out / member.name)
        if platform != "windows":
            console.chmod(0o755)
    except FetchCancelled:
        raise
    except OSError as exc:
        raise _fail(str(exc) or type(exc).__name__) from exc
    finally:
        if not keep_part:
            _forget(part)
        shutil.rmtree(staging, ignore_errors=True)
    return console
