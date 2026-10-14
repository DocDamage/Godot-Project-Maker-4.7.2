"""Write godot_templates/tests/fixtures/iso_tiles/: the isometric tile set of the synthetic
pack ``iso_tiles`` as rpggen describes it (T17.13), for the GDScript tests of the builder.

* ``catalog.json``: the catalog of the pack after ``iso_atlas.add`` for an isometric project,
  cut down to what the tile set is built from (the tiles, the atlases, one tree and one house)
  and with the pictures' paths pointing into the fixture folder.
* ``iso_tiles_0.png``, ``iso_tiles_1.png``: the atlas pictures. ``tree.png``, ``house.png``: two
  objects of the pack, for the picture a probe renders.

A few tiles are given what the audit would give them, so that the tests have a wall, water,
ground that can be tilled and a surface: see ``AUDIT``.

The GDScript test builds the Godot ``TileSet`` from this with the real recipe; a Python test
checks that the fixture is what the code makes now.

Usage: python tools/make_iso_fixture.py [--check]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from rpggen.core import (  # noqa: E402
    archive,
    catalog,
    inventory,
    iso_atlas,
    orchestrator,
)

PACK = REPO / "test_packs" / "synthetic" / "iso_tiles"
OUT = REPO / "godot_templates" / "tests" / "fixtures" / "iso_tiles"
FIXTURE_DIR = "tests/fixtures/iso_tiles"
OBJECTS = {"iso_tiles.png.tree_01_0": "tree.png", "iso_tiles.png.house_01_0": "house.png"}
# What the audit would say of a few tiles: the raised blocks of tile 19 are walls, tile 2 is
# water, tile 3 can be tilled and sounds like grass.
AUDIT: dict[str, dict[str, Any]] = {
    "isotile_019": {"role": "WALL"},
    "isotile_002": {"tags": ["water"]},
    "isotile_003": {"tags": ["tillable", "surface:grass"]},
}
# The second fixture (T17.22): the tile set of the synthetic pack ``iso_kit``, whose walls stand
# along one side of a diamond, with a door, a window, a roof and road corners that are round
# and square. ``catalog.json`` and the atlas pictures, as the first; nothing is given by hand.
KIT_PACK = REPO / "test_packs" / "synthetic" / "iso_kit"
KIT_OUT = REPO / "godot_templates" / "tests" / "fixtures" / "iso_kit"
# name -> (the pack, the fixture's folder in the test project, its objects, its audit)
FIXTURES: dict[str, tuple[Path, str, dict[str, str], dict[str, dict[str, Any]]]] = {
    "iso_tiles": (PACK, FIXTURE_DIR, OBJECTS, AUDIT),
    "iso_kit": (KIT_PACK, "tests/fixtures/iso_kit", {"iso_kit.png.tree_01_0": "tree.png"}, {}),
}
OUTS = {"iso_tiles": OUT, "iso_kit": KIT_OUT}


def build(work: Path, name: str = "iso_tiles") -> tuple[dict[str, Any], dict[str, Path]]:
    """``(the fixture catalog, {file name: picture to copy})`` of the fixture ``name``, made in
    the folder ``work``."""
    pack, fixture_dir, objects, audit = FIXTURES[name]
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    for asset in cat.assets:
        stem = asset.id.rsplit(".", 1)[-1]
        for word, change in audit.items():
            if not stem.startswith(word + "_"):
                continue
            change = dict(change)
            if "tags" in change:
                change["tags"] = sorted({*asset.detected.get("tags", []), *change["tags"]})
            asset.overrides = change
    root = work / "root"
    shutil.copytree(opened.root, root / "assets" / "packs" / opened.pack_id)
    cfg = orchestrator.default_config_for_pack(pack, "Iso tiles")
    cfg.projection = "isometric"
    iso_atlas.add(cat, cfg, root)
    pictures: dict[str, Path] = {}
    data = cat.to_json()
    kept = []
    for entry in data["assets"]:
        asset = cat.asset(entry["id"])
        assert asset is not None
        if entry["pack_id"] == iso_atlas.ATLAS_PACK:
            file_name = Path(entry["path"]).name
            pictures[file_name] = root / entry["path"]
            entry["path"] = f"{fixture_dir}/{file_name}"
        elif entry["id"] in objects:
            pictures[objects[entry["id"]]] = root / entry["path"]
            entry["path"] = f"{fixture_dir}/{objects[entry['id']]}"
        elif not catalog.is_iso_tile(asset):
            continue
        kept.append(entry)
    data["assets"] = kept
    data["generator_version"] = "fixture"
    for row in data["packs"]:
        row["source_sha256"] = "0" * 64  # the pack's own hash says nothing to the builder
    return data, pictures


def _text(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _same_picture(a: Path, b: Path) -> bool:
    if not a.is_file() or not b.is_file():
        return False
    with Image.open(a) as first, Image.open(b) as second:
        one, two = first.convert("RGBA"), second.convert("RGBA")
        return one.size == two.size and one.tobytes() == two.tobytes()


def check() -> list[str]:
    """What of the fixtures is not what the code makes now (empty: they are current)."""
    stale: list[str] = []
    for fixture, out in OUTS.items():
        with tempfile.TemporaryDirectory(prefix="rpggen_iso_fixture_") as tmp:
            data, pictures = build(Path(tmp), fixture)
            target = out / "catalog.json"
            if not target.is_file() or json.loads(target.read_text(encoding="utf-8")) != json.loads(
                _text(data)
            ):
                stale.append(f"{fixture}/catalog.json")
            for name, source in sorted(pictures.items()):
                if not _same_picture(source, out / name):
                    stale.append(f"{fixture}/{name}")
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when a fixture is stale")
    args = parser.parse_args(argv)
    if args.check:
        stale = check()
        for name in stale:
            print(f"stale: {name}")
        return 1 if stale else 0
    for fixture, out in OUTS.items():
        with tempfile.TemporaryDirectory(prefix="rpggen_iso_fixture_") as tmp:
            data, pictures = build(Path(tmp), fixture)
            out.mkdir(parents=True, exist_ok=True)
            (out / "catalog.json").write_text(_text(data), encoding="utf-8", newline="\n")
            for name, source in sorted(pictures.items()):
                shutil.copyfile(source, out / name)
                print(f"wrote {out / name}")
        print(f"wrote {out / 'catalog.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
