"""T16.21: the three synthetic packs made after what real packs look like: a numbered frame
export, one art for several engines, a bundle of packs."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory, pack_sniff

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(source: Path) -> tuple[catalog.Catalog, list[str]]:
    opened = archive.open_pack(source, set())
    cat, issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat, [i.code for i in issues]


def _by_path(cat: catalog.Catalog) -> dict[str, catalog.Asset]:
    return {a.path.split("/", 3)[-1]: a for a in cat.assets}


def test_the_frame_export_gives_named_animations_where_a_source_names_them() -> None:
    cat, codes = _catalog(SYNTH / "frames_export")
    assets = _by_path(cat)
    hero = catalog.effective(assets["HERO/HERO1.png"])
    assert {k: len(v["frames"]) for k, v in hero["animations"].items()} == {
        "attack_down": 3,
        "idle_down": 4,
        "walk_down": 5,
    }
    assert (
        not hero["animations"]["attack_down"]["loop"]
        and hero["animations"]["idle_down"]["fps"] == 4.0
    )
    slime = catalog.effective(assets["ENEMY/SLIME/SLIME 1.png"])
    assert sorted(slime["animations"]) == ["idle_2_down", "idle_down"], "no source: by its frames"
    assert "ADAPT-005" not in codes and "ADAPT-006" not in codes  # every run named
    assert sorted(catalog.effective(assets["PROPS/FLAME/FLAME1.png"])["animations"]) == [
        "idle_down"
    ]
    coins = [p for p in assets if p.startswith("PROPS/COIN/")]
    assert len(coins) == 3, "numbered pictures nothing marks as frames stay pictures"
    assert [p for p in assets if p.startswith("HERO/")] == ["HERO/HERO1.png"]
    for path in ("PREVIEW/Preview (1).png", "test.png"):
        assert assets[path].status == "UNUSED"
    assert catalog.effective(assets["BACKGROUD/BACKGROUND (1) .png"])["role"] == "BACKGROUND"
    assert len([p for p in assets if p.startswith("BACKGROUD/")]) == 2


def test_the_multi_engine_pack_is_read_once() -> None:
    opened = archive.open_pack(SYNTH / "multi_engine", set())
    inv = inventory.build_inventory(opened)
    assert {s["path"]: s["reason"] for s in inv.skipped} == {
        "assets/__MACOSX/._ground_16x16.png": "os_junk",
        "assets/crops/In development": "not_an_asset",
        "Please_rate.html": "not_an_asset",
    }
    cat, _codes = _catalog(SYNTH / "multi_engine")
    assert "engines:5:Godot" in cat.packs[0].warnings
    assets = _by_path(cat)
    unused = sorted(p for p, a in assets.items() if a.status == "UNUSED")
    assert unused == [
        "assets/autotiles/01_grass.png",
        "engines/Godot/autotiles/2x2/01_grass.png",
        "engines/RPG_Maker_MV_MZ/tiles/grass.png",
        "engines/RPG_Maker_VX_VXace/tiles/grass.png",
        "engines/RPG_Maker_XP/tiles/grass.png",
        "engines/Unity/grass.png",
    ]
    blob = catalog.effective(assets["engines/Godot/autotiles/3x3/01_grass.png"])
    assert blob["usage"] == "tiles" and blob["grid"]["cell"] == [16, 16]
    cows = "assets/animals/cows/cow_01"
    move = {c: assets[f"{cows}/{c}/move/cow_01_{c}_move_down_16x16_4frames.png"] for c in ("black", "black_white", "brown")}  # fmt: skip
    first = move["black"]
    assert len(catalog.effective(first)["animations"]["walk_down"]["frames"]) == 4
    assert [a.path for a in catalog.colour_variants(cat, first.id)] == [
        move["black_white"].path,
        move["brown"].path,
    ]
    assert (
        "growth" in catalog.effective(assets["assets/crops/wheat_growth_16x32_5frames.png"])["tags"]
    )


def test_the_bundle_is_told_from_its_listing_and_read_by_its_folders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads: list[str] = []
    monkeypatch.setattr(pack_sniff._Zip, "head", lambda self, name, size: reads.append(name) or b"")
    sniffed = pack_sniff.sniff(SYNTH / "bundle.zip")
    assert reads == [] and len(sniffed.bundle) == 12 and sniffed.has_license
    assert sum(p.images for p in sniffed.bundle) == 5 + 11 * 2 + 4
    cat, codes = _catalog(SYNTH / "bundle.zip")
    assert "ADAPT-007" not in codes
    assets = _by_path(cat)
    town = sorted(p for p in assets if "/Medieval Fantasy Town" in p)
    assert len(town) == 5, "five numbered 768 px sheets are five tile sheets, not one animation"
    for path in town:
        eff = catalog.effective(assets[path])
        assert eff["usage"] == "tiles" and eff["grid"]["cell"] == [48, 48]
        assert eff["tags"] == ["fantasy", "medieval", "town"]
    gym = catalog.effective(assets["Bundle/Modern Gym Pixel Art Tileset Pack/3.png"])
    assert gym["tags"] == ["gym", "modern"] and gym["grid"]["cell"] == [32, 32]
    hospital = "Bundle/Abandoned Hospital Tileset"
    cut = {o.name: o for o in cat.objects if o.name.startswith("sheet_0")}
    assert sorted(cut) == ["sheet_01_beds_001", "sheet_01_carts_001", "sheet_03_beds_001"]
    assert cut["sheet_03_beds_001"].sheet == assets[f"{hospital}/3.png"].id
    assert cut["sheet_03_beds_001"].region == [32, 64, 64, 64] and cut[
        "sheet_01_carts_001"
    ].tags == ["carts"]
    copies = [a for p, a in assets.items() if "/_organized_sprites/" in p]
    assert len(copies) == 4 and {a.status for a in copies} == {"UNUSED"}
