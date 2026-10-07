"""Download the official Godot build (T11.04).

Used by the Project page's "Download Godot" button and, through ``tools/fetch_godot.py``, by CI.
The archive is streamed to ``<name>.part``, its SHA-512 is checked against the release's
``SHA512-SUMS.txt`` *before* anything is extracted, and only the expected executables are
extracted (any other member, ``..`` or a drive letter rejects the archive).
"""

from __future__ import annotations

import contextlib
import hashlib
import shutil
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

Opener = Callable[[str], Any]  # url -> context manager with .read(n) (and optional .headers)
Progress = Callable[[int, int], None]


class FetchCancelled(Exception):
    """The user cancelled the download; nothing is left behind."""


def zip_name(version: str, platform: str = "windows") -> str:
    if platform == "linux":
        return f"Godot_v{version}-stable_linux.x86_64.zip"
    return f"Godot_v{version}-stable_win64.exe.zip"


def console_name(version: str, platform: str = "windows") -> str:
    """The executable to run: the console build on Windows, the only build on Linux."""
    if platform == "linux":
        return f"Godot_v{version}-stable_linux.x86_64"
    return f"Godot_v{version}-stable_win64_console.exe"


def expected_members(version: str, platform: str = "windows") -> set[str]:
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
    return paths.local_cache_dir() / "godot" / version


def managed_executable(version: str = DEFAULT_VERSION, platform: str = "windows") -> Path:
    return managed_dir(version) / console_name(version, platform)


def default_opener(url: str) -> Any:
    if not url.lower().startswith("https://"):
        raise OSError(f"refusing a non-https URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "rpggen"})
    return urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S)  # noqa: S310


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


def _download(
    opener: Opener,
    url: str,
    part: Path,
    progress: Progress | None,
    is_cancelled: Callable[[], bool] | None,
) -> str:
    """Stream ``url`` to ``part``; returns the SHA-512 hex digest of what was written."""
    digest = hashlib.sha512()
    done = 0
    with opener(url) as resp, part.open("wb") as fh:
        headers = getattr(resp, "headers", None)
        try:
            total = int(headers.get("Content-Length", 0)) if headers is not None else 0
        except (TypeError, ValueError):
            total = 0
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


def fetch(
    version: str,
    out: Path,
    platform: str = "windows",
    *,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    opener: Opener | None = None,
    require_checksum: bool = True,
) -> Path:
    """Download Godot ``version`` into ``out`` and return the console executable.

    Raises ``RpgGenError("ENV-011")`` for every failure and ``FetchCancelled`` on cancel."""
    opener = opener or default_opener
    out = Path(out)
    console = out / console_name(version, platform)
    if console.exists():
        return console
    name = zip_name(version, platform)
    part = out / f"{name}.part"
    staging = out / ".extract"
    try:
        out.mkdir(parents=True, exist_ok=True)
        try:
            with opener(release_url(version, "SHA512-SUMS.txt")) as resp:
                sums = parse_sums(resp.read(SUMS_LIMIT).decode("utf-8", "replace"))
        except OSError:
            sums = {}
        expected = sums.get(name)
        if expected is None and require_checksum:
            raise _fail("the release has no SHA-512 checksum to verify the download against")
        actual = _download(opener, release_url(version, name), part, progress, is_cancelled)
        if expected is not None and actual != expected:
            raise _fail(f"the download's SHA-512 does not match the release ({name})")
        allowed = expected_members(version, platform)
        try:
            with zipfile.ZipFile(part) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir()]
                bad = [i.filename for i in infos if not _safe_member(i.filename, allowed)]
                if bad:
                    raise _fail(f"the archive contains an unexpected file: {bad[0]}")
                shutil.rmtree(staging, ignore_errors=True)
                staging.mkdir()
                for info in infos:
                    with zf.open(info) as src, (staging / info.filename).open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        except zipfile.BadZipFile as exc:
            raise _fail("the downloaded file is not a valid archive") from exc
        if not (staging / console.name).exists():
            raise _fail(f"{console.name} is not in the downloaded archive")
        for member in staging.iterdir():
            member.replace(out / member.name)
        if platform == "linux":
            console.chmod(0o755)
    except OSError as exc:
        raise _fail(str(exc) or type(exc).__name__) from exc
    finally:
        with contextlib.suppress(OSError):
            part.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
    return console
