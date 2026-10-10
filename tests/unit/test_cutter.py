"""T16.21: the manifest a sprite-cutting tool left in a pack gives the sheets their objects."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, catalog, explain, inventory

SPRITES = [  # id, sheet, category, x, y, width, height
    ("sheet_01_tall_shelves_and_racks_001", "sheet_01", "tall_shelves_and_racks", 0, 0, 96, 144),
    ("sheet_01_baskets_crates_and_bins_001", "sheet_01", "baskets_crates_and_bins", 96, 0, 48, 48),
    ("sheet_03_baskets_crates_and_bins_001", "sheet_03", "baskets_crates_and_bins", 48, 96, 40, 30),
]
OWN_DISK = "G:\\All 2D Assets Stay Here\\Bundle\\Supermarket Tileset\\"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _png(path: Path, size: tuple[int, int], shade: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (shade, 90, 40, 255)).save(path)


def _pack(tmp: Path, *, as_json: bool = True, as_csv: bool = True, sprites=SPRITES) -> Path:
    pack = tmp / "Supermarket Tileset"
    for n in (1, 2, 3):  # sheet_03 is the file 3.png
        _png(pack / f"{n}.png", (768, 768), 40 * n)
    out = pack / "_organized_sprites"
    for index, (name, _sheet, category, _x, _y, w, h) in enumerate(sprites):
        _png(out / "sprites" / category / f"{name}.png", (max(1, w), max(1, h)), 200 - index)
    _png(out / "previews" / "sheet_01_boxes.png", (768, 768), 7)
    _png(out / "previews" / "sheet_01_contact.png", (400, 300), 8)
    (out / "manifest").mkdir(parents=True)
    if as_json:
        entries = [
            {
                "id": name,
                "source_sheet": sheet,
                "source_file": OWN_DISK + f"{int(sheet[-2:])}.png",
                "category": category,
                "output_file": OWN_DISK + f"_organized_sprites\\sprites\\{category}\\{name}.png",
                "bbox": {"x": x, "y": y, "width": w, "height": h},
                "width": w,
                "height": h,
            }
            for name, sheet, category, x, y, w, h in sprites
        ]
        (out / "manifest" / "sprites.json").write_text(json.dumps(entries), encoding="utf-8")
    if as_csv:
        text = io.StringIO()
        writer = csv.writer(text)
        writer.writerow(
            ["id", "source_sheet", "category", "output_file", "x", "y", "width", "height"]
        )
        for name, sheet, category, x, y, w, h in sprites:
            writer.writerow([name, sheet, category, OWN_DISK + name + ".png", x, y, w, h])
        (out / "manifest" / "sprites.csv").write_text(text.getvalue(), encoding="utf-8")
    (out / "manifest" / "summary.txt").write_text("3 sprites", encoding="utf-8")
    return pack


def _catalog(pack: Path) -> tuple[catalog.Catalog, list]:
    opened = archive.open_pack(pack, set())
    cat, issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    return cat, list(issues)


@pytest.mark.parametrize(("as_json", "as_csv"), [(True, True), (True, False), (False, True)])
def test_the_rectangles_of_the_manifest_are_the_objects_of_the_sheets(
    tmp_path: Path, as_json: bool, as_csv: bool
) -> None:
    cat, issues = _catalog(_pack(tmp_path, as_json=as_json, as_csv=as_csv))
    assert "ADAPT-007" not in [i.code for i in issues]
    sheets = {a.path.rsplit("/", 1)[-1]: a for a in cat.assets if "_organized" not in a.path}
    assert sorted(sheets) == ["1.png", "2.png", "3.png"]
    assert all(catalog.effective(a)["usage"] == "tiles" for a in sheets.values())
    objects = {o.name: o for o in cat.objects}
    assert sorted(objects) == sorted(s[0] for s in SPRITES), "these and no guessed ones"
    shelf = objects["sheet_01_tall_shelves_and_racks_001"]
    assert shelf.sheet == sheets["1.png"].id and shelf.region == [0, 0, 96, 144]
    assert shelf.tags == ["tall_shelves_and_racks"] and shelf.origin == [48, 143]
    crate = objects["sheet_03_baskets_crates_and_bins_001"]
    assert crate.sheet == sheets["3.png"].id and crate.region == [48, 96, 40, 30]
    # the cut copies and the previews are in the catalog, unused, and say why
    left = [a for a in cat.assets if "_organized_sprites" in a.path]
    assert len(left) == 5 and {a.status for a in left} == {"UNUSED"}
    reasons = {a.path.rsplit("/", 1)[-1]: explain.why(a) for a in left}
    assert "cut out of a sheet" in reasons["sheet_01_tall_shelves_and_racks_001.png"]
    assert "preview picture" in reasons["sheet_01_contact.png"]
    assert "G:" not in json.dumps(cat.to_json()), "the artist's own disk is in no catalog"


def test_a_sheet_is_found_by_its_place_when_no_file_has_its_number(tmp_path: Path) -> None:
    pack = _pack(tmp_path, as_json=False)
    for n, name in ((1, "town_a.png"), (2, "town_b.png"), (3, "town_c.png")):
        (pack / f"{n}.png").rename(pack / name)
    cat, issues = _catalog(pack)
    assert "ADAPT-007" not in [i.code for i in issues]
    by_name = {o.name: o.sheet for o in cat.objects}
    assert by_name["sheet_03_baskets_crates_and_bins_001"].endswith("town_c")


@pytest.mark.parametrize(
    ("sprites", "words"),
    [
        ([*SPRITES[:2], ("far_001", "sheet_01", "bins", 700, 700, 100, 40)], "is outside 1.png"),
        ([("lost_001", "sheet_09", "bins", 0, 0, 10, 10)], "which is not in the pack"),
        ([("flat_001", "sheet_01", "bins", 0, 0, 0, 10)], "is outside 1.png"),
        ([], "it lists no sprite"),
    ],
)
def test_a_manifest_that_does_not_fit_its_sheets_is_a_note(tmp_path: Path, sprites, words) -> None:
    cat, issues = _catalog(_pack(tmp_path, sprites=sprites, as_csv=False))
    (note,) = [i for i in issues if i.code == "ADAPT-007"]
    assert note.severity.value == "info" and words in note.message
    assert "manifest/sprites.json" in note.message
    assert not [o for o in cat.objects if o.name in {s[0] for s in sprites}]
    cut = [a for a in cat.assets if "/sprites/" in a.path]
    assert len(cut) == len(sprites) and all(a.status != "UNUSED" for a in cut), (
        "the cut pictures are what there is: they are used as sprites"
    )
    previews = [a for a in cat.assets if "/previews/" in a.path]
    assert previews and all(a.status == "UNUSED" for a in previews)


def test_a_file_that_is_no_manifest_is_a_note_too(tmp_path: Path) -> None:
    pack = _pack(tmp_path, as_csv=False)
    (pack / "_organized_sprites" / "manifest" / "sprites.json").write_text("{", encoding="utf-8")
    _cat, issues = _catalog(pack)
    assert [i.code for i in issues if i.code.startswith("ADAPT")] == ["ADAPT-007"]


def test_a_pack_without_a_manifest_is_not_touched(tmp_path: Path) -> None:
    pack = tmp_path / "plain"
    _png(pack / "1.png", (768, 768), 50)
    _png(pack / "data" / "sprites.json.png", (16, 16), 60)
    (pack / "data" / "sprites.json").write_text("[]", encoding="utf-8")  # not in a manifest folder
    cat, issues = _catalog(pack)
    assert not [i for i in issues if i.code == "ADAPT-007"]
    assert "cutter" not in cat.packs[0].adapters_matched
