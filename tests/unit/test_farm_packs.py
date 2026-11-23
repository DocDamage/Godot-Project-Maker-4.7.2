"""Real farming packs (T17.29): one tile set in several forms, a pack in several sizes, crops by
their pictures beside food icons, farm animals, layered characters and previews."""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen.core import archive, catalog, crop_plan, explain, inventory, lpc_compose, pack_forms
from rpggen.core.adapters import farm

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(source: Path, previous: catalog.Catalog | None = None):
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened)
    cat, issues, generated = catalog.assemble([(opened, inv)], previous, [], use_cache=False)
    return cat, issues, generated


def _by_rel(cat: catalog.Catalog, rel: str) -> catalog.Asset:
    found = [a for a in cat.assets if a.path.endswith("/" + rel) and "#" not in a.id]
    assert found, rel
    return found[0]


def _reason(asset: catalog.Asset) -> str:
    tags = catalog.effective(asset).get("tags") or []
    return next((t.split(":", 1)[1] for t in tags if t.startswith("unused_because:")), "")


# --------------------------------------------------------------------------- growth


def test_reviewed_orchard_uses_only_selected_cells_and_rejects_changed_art(tmp_path, monkeypatch):
    from rpggen.core.adapters import orchard
    from rpggen.core.adapters.base import AdapterResult

    root = tmp_path / "Farm"
    root.mkdir()
    sheet = np.zeros((96, 96, 4), dtype=np.uint8)
    for index in range(6):
        sheet[index // 3 * 48 : (index // 3 + 1) * 48, index % 3 * 32 : (index % 3 + 1) * 32] = [
            index * 30,
            80,
            30,
            255,
        ]
    Image.fromarray(sheet).save(root / "Tree.png")
    inv = inventory.build_inventory(archive.open_pack(root, set()))
    source = inv.files[0]
    layout = {
        "name": "apple",
        "frame": [32, 48],
        "cells": [3, 1, 5],
        "mature_stage": 1,
        "season": "autumn",
    }
    layouts = {source.sha256: layout}
    monkeypatch.setattr(orchard, "layouts", lambda: layouts)
    adapter = farm.FarmPackAdapter()
    result = AdapterResult("test")
    assert adapter._orchard(root, source, tmp_path / "work", result)
    image = np.array(Image.open(next(iter(result.generated.values()))))
    assert image.shape == (48, 96, 4)
    assert [image[20, i * 32, 0] for i in range(3)] == [90, 30, 150]
    assert result.assets[0].facets["stages"] == 3
    source = dataclasses.replace(source, sha256="f" * 64)
    assert not adapter._orchard(root, source, tmp_path / "work", result)


def test_reviewed_orchard_sheet_is_not_made_into_a_scenery_tree(
    tmp_path: Path, monkeypatch
) -> None:
    from rpggen.core import pack_readings

    root = tmp_path / "Farm Tileset"
    folder = root / "Crops" / "Fruit Trees"
    folder.mkdir(parents=True)
    image = Image.new("RGBA", (96, 48))
    for column in range(3):
        image.paste((40, 160, 60, 255), (column * 32 + 8, 8, column * 32 + 24, 48))
    image.save(folder / "Apple Tree.png")
    opened = archive.open_pack(root, set())
    inv = inventory.build_inventory(opened)
    source = next(f for f in inv.files if f.path.endswith("Apple Tree.png"))
    monkeypatch.setattr(pack_readings, "readings", lambda: {source.sha256: {"": {"role": "CROP"}}})
    cat, _, _ = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    tree = _by_rel(cat, "Crops/Fruit Trees/Apple Tree.png")
    assert catalog.effective(tree)["role"] == "CROP"
    assert not any(o.sheet == tree.id for o in cat.objects)
    assert tree.status != "CONFIRMED", "a role choice does not certify growth metadata"


def test_stages_grow_from_the_seed_to_the_ripe_plant_and_stop_at_the_produce() -> None:
    # seeds, a sprout, two larger stages, an empty cell and the produce harvested
    counts = [(20, 4, 0.0), (12, 4, 0.9), (30, 8, 0.9), (60, 12, 0.8), (0, 0, 0.0), (50, 10, 0.0)]
    assert farm.stage_cells(counts, 0) == [0, 1, 2, 3]
    assert farm.growth_run(counts, 0, 1.2, from_least=True) == 4
    assert farm.growth_run(counts, 0, farm.GROWTH_RATIO) == 4


def test_an_empty_stage_is_passed_over_when_the_plant_grows_on_after_it() -> None:
    counts = [(10, 3, 0.9), (0, 0, 0.0), (30, 7, 0.9), (60, 11, 0.9), (70, 12, 0.9)]
    assert farm.stage_cells(counts, 0) == [0, 2, 3, 4]


def test_frames_that_do_not_grow_are_no_crop() -> None:
    # a food icon and the same icon lit; a butterfly that beats its wings
    assert farm.growth_run([(40, 9, 0.0), (44, 10, 0.0)], 0, 1.2, from_least=True) == 0
    assert farm.growth_run([(30, 6, 0.0), (18, 6, 0.0), (30, 6, 0.0)], 0, farm.GROWTH_RATIO) == 0


def test_a_withered_last_stage_is_no_stage() -> None:
    counts = [(20, 5, 0.9), (40, 8, 0.9), (80, 12, 0.9), (60, 12, 0.0)]
    assert farm.growth_run(counts, 0, farm.GROWTH_RATIO) == 3


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("Crops/Spring/Carrot.png", "carrot"),
        ("16x16/Crops_Growth_16x16/Carrot_Growth_Stages_16x16.png", "carrot"),
        ("Crops/Summer/Green Beans.png", "green_beans"),
    ],
)
def test_the_crop_is_named_after_its_produce(path: str, name: str) -> None:
    assert farm.crop_name(path) == name


def test_the_crop_plan_names_a_crop_by_its_produce() -> None:
    asset = catalog.Asset(
        "p.generated.x#crop_1", "p", "generated/farm_crops/x.png", "0", "image", "AUTO_DETECTED",
        {"usage": "growth_strip", "role": "CROP", "stages": 3, "tags": ["produce:carrot"]},
    )  # fmt: skip
    facts = crop_plan.facts_of(catalog.Catalog(assets=[asset]))
    assert facts["crops"] == [{"asset": asset.id, "name": "carrot", "stages": 3}]
    assert crop_plan.crop_name("tiny_farm.tilemap.tilemap#crop_2") == "tilemap_crop_2"


def test_a_cell_width_is_the_one_whose_borders_the_drawings_do_not_cross() -> None:
    a = np.zeros((32, 128, 4), dtype=np.uint8)
    for x0 in range(0, 128, 32):  # four cows of 28 px in cells of 32
        a[4:28, x0 + 2 : x0 + 30, 3] = 255
    assert farm.cell_width(a) == 32


# --------------------------------------------------------------------------- the packs


def test_one_set_in_three_forms_is_one_tile_set() -> None:
    cat, _issues, generated = _assemble(SYNTH / "farm_forms")
    sheet = _by_rel(cat, "Tilemap/tilemap.png")
    assert catalog.effective(sheet)["role"] == "GROUND"
    packed = _by_rel(cat, "Tilemap/tilemap_packed.png")
    assert _reason(packed) == pack_forms.SAME_TILES
    assert pack_forms.SAME_AS_TAG + "Tilemap/tilemap.png" in packed.detected["tags"]
    singles = [a for a in cat.assets if "/Tiles/tile_" in a.path]
    assert len(singles) == 24 and all(_reason(a) == pack_forms.SAME_TILES for a in singles)
    assert "same tiles" in explain.why(packed)
    # the set aside forms join no tile set: one tile set of 16 px with the spaced sheet
    assert [(t.tile_size, [s["asset"] for s in t.sources]) for t in cat.tilesets] == [
        ([16, 16], [sheet.id])
    ]
    crops = [a for a in cat.assets if a.detected.get("usage") == "growth_strip"]
    assert [(a.id.rsplit("#", 1)[-1], a.detected["stages"]) for a in crops] == [("crop_1", 3)]
    assert crops[0].path in generated
    assert catalog.pack_view(cat.packs[0]) == "top"
    assert catalog.VIEW_FARM in cat.packs[0].warnings  # its own name says farm


def test_a_pack_in_two_sizes_uses_the_smallest_and_the_audit_chooses_another() -> None:
    cat, _issues, _generated = _assemble(SYNTH / "farm_sizes")
    assert cat.pack_sizes == {"farm_sizes": 16}
    small = _by_rel(cat, "16x16/1_Terrains_16x16.png")
    big = _by_rel(cat, "32x32/1_Terrains_32x32.png")
    assert catalog.effective(small)["role"] == "GROUND" and big.status == "UNUSED"
    assert _reason(big) == pack_forms.OTHER_SIZE
    assert {t.tile_size[0] for t in cat.tilesets} == {16}
    assert catalog.dominant_tile_size(cat) == 16
    assert pack_forms.sizes_of(cat, "farm_sizes") == [16, 32]
    # the user's choice, as the Audit page makes it
    from rpggen.gui import edits

    chosen = edits.set_pack_size(cat, "farm_sizes", 32)
    assert chosen.pack_sizes == {"farm_sizes": 32}
    assert catalog.effective(chosen.asset(big.id))["role"] == "GROUND"
    assert chosen.asset(small.id).status == "UNUSED"
    assert {t.tile_size[0] for t in chosen.tilesets if t.sources} == {32}
    assert cat.asset(small.id).status != "UNUSED", "the catalog of the undo step is unchanged"
    assert edits.set_pack_size(cat, "farm_sizes", 48) is cat
    # ... and kept by the next analysis
    again, _issues, _generated = _assemble(SYNTH / "farm_sizes", chosen)
    assert again.pack_sizes == {"farm_sizes": 32}
    assert again.asset(small.id).status == "UNUSED"
    assert catalog.Catalog.from_json(again.to_json()).pack_sizes == {"farm_sizes": 32}


def test_the_crops_drawn_from_a_pack_in_two_sizes_are_in_its_sizes_too() -> None:
    from types import SimpleNamespace

    def strip(n: int, name: str) -> SimpleNamespace:
        source = f"Crops_{n}x{n}/{name.title()}_{n}x{n}.png"
        return SimpleNamespace(
            id=f"p.farm_crops.p__{name}_{n}x{n}",
            path=f"generated/farm_crops/p__{name}_{n}x{n}.png",
            detected={
                "size": [4 * n, n],
                "tags": [farm.PRODUCE_TAG + name, farm.SOURCE_TAG + source],
            },
        )

    # Modern Farm grew every crop three times (carrot, carrot_2, carrot_3) before
    strips = [strip(n, name) for n in (16, 32) for name in ("carrot", "corn", "onion")]
    assert pack_forms.mark_sizes(strips, "assets/packs/p") == [16, 32]
    assert [pack_forms.size_of(a) for a in strips] == [16, 16, 16, 32, 32, 32]


def test_a_pack_in_two_sizes_takes_the_size_the_other_packs_use() -> None:
    sizes = archive.open_pack(SYNTH / "farm_sizes", set())
    other = archive.open_pack(SYNTH / "gutter32", set(), "gutter32")
    packs = [(p, inventory.build_inventory(p)) for p in (sizes, other)]
    cat, _issues, _generated = catalog.assemble(packs, None, [], use_cache=False)
    assert cat.pack_sizes == {"farm_sizes": 32}


def test_crops_by_their_pictures_beside_food_icons_a_hen_and_a_preview() -> None:
    cat, _issues, generated = _assemble(SYNTH / "farm_crops")
    crops = sorted((crop_plan.facts_of(cat)["crops"]), key=lambda c: c["name"])
    assert [(c["name"], c["stages"]) for c in crops] == [("cabbage", 6), ("carrot", 5)]
    for crop in crops:
        asset = cat.asset(crop["asset"])
        assert asset is not None and asset.path in generated
        with Image.open(generated[asset.path]) as strip:
            assert strip.size == (16 * crop["stages"], 16)
    season = _by_rel(cat, "Crops/Spring/Spring Crops.png")
    assert _reason(season) == pack_forms.COMPILED_SHEET
    for icon in ("Carrot.png", "Cabbage.png", "Carrot cake.png"):
        assert catalog.effective(_by_rel(cat, f"Icons/Food Icons/{icon}"))["role"] == "ITEM"
    butterfly = catalog.effective(_by_rel(cat, "Animals/Bugs/Cabbage White.png"))
    assert butterfly["role"] != "CROP"
    hen = catalog.effective(_by_rel(cat, "Animals/Farm/Chicken/Chicken White.png"))
    assert hen["role"] == "ANIMAL"
    assert sorted(hen["animations"]) == ["idle_down", "sleep_down", "walk_down"]
    gif = _by_rel(cat, "Animated/Animated_gifs_16x16/Mill_16x16.gif")
    assert _reason(gif) == pack_forms.PREVIEW_GIF and gif.status == "UNUSED"


def test_a_layered_character_is_one_character_with_its_choices(tmp_path: Path) -> None:
    cat, _issues, generated = _assemble(SYNTH / "farm_layered")
    assert len(cat.characters) == 1
    definition = cat.characters[0]
    character = cat.asset(definition["id"])
    assert character is not None and character.path in generated
    eff = catalog.effective(character)
    # the frames are cut to the columns the pieces paint, about the middle (its feet fit a door)
    width = eff["frame"][0]
    assert eff["role"] == "PLAYER" and eff["frame"] == [8, 16]
    middle = width // 2 - 1  # what was the column 7 of a frame of 16
    assert {n.split("_")[0] for n in eff["animations"]} == {"idle", "walk"}
    # body, then eyes, clothes and hair (an accessory is a choice to make)
    body = cat.asset(definition["body"])
    assert body is not None and lpc_compose.is_body(body) and lpc_compose.is_layered(body)
    parts = [lpc_compose.part_of(cat.asset(i)) for i in definition["layers"]]
    assert sorted(parts) == ["eyes", "hair", "torso"]
    choices = lpc_compose.layers_for(cat, body)
    assert sorted(choices) == ["eyes", "hair", "hat", "torso"]
    assert len(choices["torso"]) == 2
    # the pieces are no characters of their own; the walk files are parts of them
    pieces = [a for a in cat.assets if lpc_compose.is_layered(a)]
    assert len(pieces) == 7 and all(catalog.effective(a)["role"] == "NONE" for a in pieces)
    assert not any("2. Walk" in a.path for a in cat.assets)
    # the sheet: the idle file over the walk file, the layers drawn in their order
    with Image.open(generated[character.path]) as sheet:
        assert sheet.size == (4 * 4 * width, 2 * 16)
        rgba = sheet.convert("RGBA")
        assert rgba.getpixel((middle, 2))[:3] == (30, 30, 30)  # hair over the body
        assert rgba.getpixel((middle, 10))[:3] == (60, 90, 200)  # the first clothes over it
    frame = lpc_compose.preview([body, *map(cat.asset, definition["layers"])], _roots(cat))
    assert frame.size == (width, 16)
    # another choice of clothes, as the dialog makes it
    red = next(a for a in choices["torso"] if "Red" in a.path)
    changed = copy.deepcopy(definition)
    changed["layers"] = [
        i for i in definition["layers"] if i not in [c.id for c in choices["torso"]]
    ]
    changed["layers"].append(red.id)
    asset, file, gone = lpc_compose.build_asset(changed, cat, _roots(cat))
    assert not gone
    with Image.open(file) as sheet:
        assert sheet.convert("RGBA").getpixel((middle, 10))[:3] == (200, 60, 60)


def _roots(cat: catalog.Catalog) -> dict[str, Path]:
    from rpggen.core.terrain import GENERATED_PACK  # the portraits and frame a farm is dressed with

    return {
        p.pack_id: archive.open_pack(SYNTH / p.pack_id, set()).root
        for p in cat.packs
        if p.pack_id != GENERATED_PACK
    }


def test_the_forms_of_one_picture_twice_stay_the_duplicate_of_information_only() -> None:
    cat, _issues, _generated = _assemble(SYNTH / "bundle.zip")
    assert not any(_reason(a) == pack_forms.SAME_TILES for a in cat.assets)
