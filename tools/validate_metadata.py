"""Check a saved catalog against image headers without rerunning imports or changing metadata.

Example: python tools/validate_metadata.py --catalog catalog.json --root pack=PATH
    --generated generated.json --out validation.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rpggen import jsonio  # noqa: E402
from rpggen.core import catalog, metadata_validation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--root", action="append", default=[], metavar="PACK_ID=DIR")
    parser.add_argument("--generated", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    roots = {}
    for value in args.root:
        name, separator, folder = value.partition("=")
        if not separator or not name or not folder:
            parser.error("--root must be PACK_ID=DIR")
        roots[name] = Path(folder)
    generated = jsonio.read(args.generated) if args.generated else {}

    def resolve(path: str) -> Path | None:
        path = path.removeprefix("res://")
        if path in generated:
            return Path(generated[path])
        parts = path.split("/", 3)
        if len(parts) == 4 and parts[:2] == ["assets", "packs"] and parts[2] in roots:
            return roots[parts[2]] / parts[3]
        return None

    report = metadata_validation.validate_images(catalog.load(args.catalog), resolve)
    jsonio.write(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
