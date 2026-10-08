"""Download and unpack the official Godot build for CI (this computer's platform by default).

Usage: python tools/fetch_godot.py --version 4.7.2 --out .cache/godot [--platform linux|macos]

Prints the path of the executable on the last line of stdout. The SHA-512 of the zip must match
the one pinned in ``rpggen/godot_target.py`` (for the version this program is built for) and the
one in SHA512-SUMS.txt of the same release; another ``--version`` is verified against the sums
file alone when it lists the zip. The logic lives in ``rpggen.core.godot_fetch`` (the wizard's
Download Godot button uses the same code).
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


def fetch(version: str, out: Path, platform: str | None = None) -> Path:
    platform = platform or godot_fetch.current_platform()
    try:
        return godot_fetch.fetch(version, out, platform, require_checksum=False)
    except RpgGenError as exc:
        raise SystemExit(exc.issue.message) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=godot_target.VERSION)
    parser.add_argument("--out", type=Path, default=Path(".cache/godot"))
    parser.add_argument(
        "--platform", choices=godot_fetch.PLATFORMS, default=godot_fetch.current_platform()
    )
    args = parser.parse_args(argv)
    print(fetch(args.version, args.out, args.platform).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
