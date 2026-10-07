"""Download and unpack the official Godot build for CI (Windows by default, or Linux).

Usage: python tools/fetch_godot.py --version 4.7.2 --out .cache/godot [--platform linux]

Prints the path of the executable on the last line of stdout. The SHA-512 of the zip is
verified against SHA512-SUMS.txt from the same release when that file lists it. The logic lives
in ``rpggen.core.godot_fetch`` (the wizard's Download Godot button uses the same code).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpggen import godot_target  # noqa: E402
from rpggen.core import godot_fetch  # noqa: E402
from rpggen.core.godot_fetch import (  # noqa: E402,F401
    BASE,
    console_name,
    parse_sums,
    release_url,
    zip_name,
)
from rpggen.errors import RpgGenError  # noqa: E402


def fetch(version: str, out: Path, platform: str = "windows") -> Path:
    try:
        return godot_fetch.fetch(version, out, platform, require_checksum=False)
    except RpgGenError as exc:
        raise SystemExit(exc.issue.message) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=godot_target.VERSION)
    parser.add_argument("--out", type=Path, default=Path(".cache/godot"))
    parser.add_argument("--platform", choices=("windows", "linux"), default="windows")
    args = parser.parse_args(argv)
    print(fetch(args.version, args.out, args.platform).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
