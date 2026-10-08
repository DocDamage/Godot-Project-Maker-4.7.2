"""Make an entry of the private accuracy corpus from a pack and its confirmed profile (T12.26).

Usage:
    python tools/corpus_fingerprint.py --pack "C:\\Packs\\forest" \\
        --profile forest.rpgprofile.json --out corpus/forest.corpus.json [--name forest]

1. Generate or analyze the pack in the wizard and correct the Audit page until it is right.
2. Audit > Profile > Export pack profile... gives ``forest.rpgprofile.json``: the decisions.
3. This tool writes the entry: the fingerprint of the pack (path, size and sha256 of every file)
   and those decisions. It holds **no pixels**, so it can live in a repository.

``rpggen analyze --private-corpus corpus --packs "C:\\Packs"`` then finds each pack by its
fingerprint and reports the accuracy against the confirmed decisions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from rpggen import jsonio  # noqa: E402
from rpggen.core import accuracy, archive, inventory  # noqa: E402


def make(pack: Path, profile: Path, name: str | None = None) -> dict:
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    stem = name or (pack.name if pack.is_dir() else pack.stem)
    return accuracy.make_entry(stem, inv, jsonio.read(profile))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument(
        "--profile", type=Path, required=True, help="the confirmed .rpgprofile.json"
    )
    parser.add_argument("--out", type=Path, required=True, help="the entry to write")
    parser.add_argument("--name", help="the name of the entry (default: the pack's)")
    args = parser.parse_args(argv)
    entry = make(args.pack, args.profile, args.name)
    jsonio.write(args.out, entry)
    print(
        f"{args.out}: {len(entry['fingerprint'])} files, "
        f"{len(entry['profile'].get('assets', {}))} decisions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
