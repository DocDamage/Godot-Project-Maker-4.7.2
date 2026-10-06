"""Download and unpack the official Windows Godot build for CI.

Usage: python tools/fetch_godot.py --version 4.7.2 --out .cache/godot

Prints the path of the console executable on the last line of stdout. The SHA-512 of the zip is
verified against SHA512-SUMS.txt from the same release when that file exists.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://github.com/godotengine/godot/releases/download/{v}-stable"


def zip_name(version: str) -> str:
    return f"Godot_v{version}-stable_win64.exe.zip"


def console_name(version: str) -> str:
    return f"Godot_v{version}-stable_win64_console.exe"


def release_url(version: str, filename: str) -> str:
    return f"{BASE.format(v=version)}/{filename}"


def parse_sums(text: str) -> dict[str, str]:
    """Parse ``<hash>  <filename>`` lines of a SHA512-SUMS file."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            sums[parts[-1].lstrip("*")] = parts[0].lower()
    return sums


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)


def fetch(version: str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    console = out / console_name(version)
    if console.exists():
        return console
    archive = out / zip_name(version)
    _download(release_url(version, zip_name(version)), archive)
    try:
        with urllib.request.urlopen(release_url(version, "SHA512-SUMS.txt"), timeout=60) as resp:
            sums = parse_sums(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        sums = {}
    expected = sums.get(zip_name(version))
    if expected is not None:
        actual = hashlib.sha512(archive.read_bytes()).hexdigest()
        if actual != expected:
            archive.unlink()
            raise SystemExit(f"SHA-512 mismatch for {archive.name}: {actual} != {expected}")
    else:
        print("warning: no SHA512-SUMS entry found; skipping checksum", file=sys.stderr)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out)
    archive.unlink()
    if not console.exists():
        raise SystemExit(f"{console.name} not found in the downloaded archive")
    return console


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="4.7.2")
    parser.add_argument("--out", type=Path, default=Path(".cache/godot"))
    args = parser.parse_args(argv)
    print(fetch(args.version, args.out).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
