from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import jsonio, schema
from rpggen.core import archive, catalog, inventory
from rpggen.core.catalog import Asset, Catalog, FolderRule

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
GOLDEN = REPO / "tests" / "golden"
PACKS = sorted(p for p in SYNTH.iterdir() if p.is_dir() or p.suffix == ".zip")


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(source: Path, previous: Catalog | None = None, profiles=None):
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened)
    return catalog.assemble([(opened, inv)], previous, profiles or [], use_cache=False)


@pytest.mark.parametrize("pack", PACKS, ids=[p.stem for p in PACKS])
def test_matches_golden_catalog(pack: Path) -> None:
    cat, _issues, _generated = _assemble(pack)
    data = cat.to_json()
    schema.validate("catalog", data)
    assert jsonio.dumps(data) == (GOLDEN / f"{pack.stem}.catalog.json").read_text(encoding="utf-8")


def test_assembly_is_deterministic() -> None:
    a = _assemble(SYNTH / "rpgmaker_like")[0]
    b = _assemble(SYNTH / "rpgmaker_like")[0]
    assert jsonio.dumps(a.to_json()) == jsonio.dumps(b.to_json())


def test_zipped_equals_basic16_apart_from_pack_fields() -> None:
    def normalized(source: Path) -> str:
        cat, _, _ = _assemble(source)
        text = jsonio.dumps(cat.to_json())
        pack_id = cat.packs[0].pack_id
        sha = cat.packs[0].source_sha256
        return text.replace(pack_id, "PACK").replace(sha, "SHA")

    assert normalized(SYNTH / "basic16") == normalized(SYNTH / "zipped.zip")


def test_roles_and_expected_facts_of_basic16() -> None:
    cat, _, _ = _assemble(SYNTH / "basic16")
    hero = catalog.effective(cat.asset("basic16.characters.hero"))
    terrain = catalog.effective(cat.asset("basic16.tiles.terrain"))
    assert hero["role"] == "PLAYER" and hero["frame"] == [16, 24]
    assert terrain["role"] == "GROUND" and terrain["grid"]["cell"] == [16, 16]
    assert [t.name for t in cat.tilesets] == ["overworld"]
    assert cat.tilesets[0].sources == [{"asset": "basic16.tiles.terrain", "source_id": 0}]
    assert cat.id_allocations["tilesets"]["overworld"] == {"next_source_id": 1, "retired": []}


def test_pack_level_information() -> None:
    cat, issues, _ = _assemble(SYNTH / "rpgmaker_like")
    pack = cat.packs[0]
    assert pack.root == "assets/packs/rpgmaker_like"
    assert pack.license_files == ["assets/packs/rpgmaker_like/LICENSE.txt"]
    assert "rpgmaker_rtp_detected" in pack.warnings
    assert pack.adapters_matched == ["rpgmaker"]
    assert [i.code for i in issues if i.code == "ASSET-020"]


def test_pack_without_license_gets_asset021(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(tmp_path / "pk" / "a.png")
    _, issues, _ = _assemble(tmp_path / "pk")
    assert "ASSET-021" in [i.code for i in issues]


def test_audio_and_font_files_become_assets(tmp_path: Path) -> None:
    import wave

    pk = tmp_path / "pk"
    (pk / "music").mkdir(parents=True)
    with wave.open(str(pk / "music" / "town_theme.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 800)
    with wave.open(str(pk / "hit.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 800)
    (pk / "pixel.ttf").write_bytes(b"\0" * 16)
    (pk / "LICENSE.txt").write_text("CC0", encoding="utf-8")
    (pk / "notes.txt").write_text("doc", encoding="utf-8")
    cat, _, _ = _assemble(pk)
    by = {a.id: a for a in cat.assets}
    assert sorted(by) == ["pk.hit", "pk.music.town_theme", "pk.pixel"]
    assert by["pk.music.town_theme"].detected["role"] == "AUDIO_MUSIC"
    assert by["pk.music.town_theme"].detected["audio"] == {"type": "music", "loop": True}
    assert by["pk.hit"].detected["audio"] == {"type": "sfx", "loop": False}
    assert by["pk.pixel"].detected["role"] == "FONT" and by["pk.pixel"].kind == "font"
    assert cat.packs[0].license_files == ["assets/packs/pk/LICENSE.txt"]


def test_second_run_keeps_overrides_and_source_ids() -> None:
    first, _, _ = _assemble(SYNTH / "mixed")
    ids_before = {t.name: {s["asset"]: s["source_id"] for s in t.sources} for t in first.tilesets}
    target = first.asset("mixed.tiles.ground32")
    assert target is not None
    target.overrides = {"role": "WALL", "collision": {"profile": "FULL"}}
    again, _, _ = _assemble(SYNTH / "mixed", previous=first)
    kept = again.asset("mixed.tiles.ground32")
    assert kept.overrides == {"role": "WALL", "collision": {"profile": "FULL"}}
    assert kept.status == "CONFIRMED"
    assert catalog.effective(kept)["role"] == "WALL"
    ids_after = {t.name: {s["asset"]: s["source_id"] for s in t.sources} for t in again.tilesets}
    assert ids_after == ids_before
    assert again.id_allocations == first.id_allocations


def test_removed_file_becomes_missing_and_keeps_its_source_id(tmp_path: Path) -> None:
    pk = tmp_path / "mixed"
    shutil.copytree(SYNTH / "mixed", pk)
    first, _, _ = _assemble(pk)
    before = {s["asset"]: s["source_id"] for t in first.tilesets for s in t.sources}
    (pk / "tiles" / "ground16.png").unlink()
    again, issues, _ = _assemble(pk, previous=first)
    missing = again.asset("mixed.tiles.ground16")
    assert missing is not None and missing.status == "MISSING"
    assert ("CAT-004", "assets/packs/mixed/tiles/ground16.png") in [
        (i.code, i.file) for i in issues
    ]
    after = {s["asset"]: s["source_id"] for t in again.tilesets for s in t.sources}
    assert after["mixed.tiles.ground16"] == before["mixed.tiles.ground16"]
    schema.validate("catalog", again.to_json())


def test_changed_tile_sheet_size_raises_a_conflict(tmp_path: Path) -> None:
    pk = tmp_path / "gutter32"
    shutil.copytree(SYNTH / "gutter32", pk)
    first, _, _ = _assemble(pk)
    sheet = Image.open(pk / "tiles" / "world.png").convert("RGBA")
    wider = Image.new("RGBA", (sheet.width + 33, sheet.height), (0, 0, 0, 0))
    wider.paste(sheet, (0, 0))
    wider.paste(sheet.crop((1, 1, 33, 33)), (sheet.width - 1 + 1, 1))  # one more column of tiles
    wider.save(pk / "tiles" / "world.png")
    again, issues, _ = _assemble(pk, previous=first)
    asset = again.asset("gutter32.tiles.world")
    assert asset.status == "CONFLICT"
    assert "TILE-004" in [i.code for i in issues]
    # a conflict is sticky until the user resolves it
    third, _, _ = _assemble(pk, previous=again)
    assert third.asset("gutter32.tiles.world").status == "CONFLICT"


def test_same_size_sheet_edit_is_not_a_conflict(tmp_path: Path) -> None:
    pk = tmp_path / "gutter32"
    shutil.copytree(SYNTH / "gutter32", pk)
    first, _, _ = _assemble(pk)
    sheet = Image.open(pk / "tiles" / "world.png").convert("RGBA")
    sheet.putpixel((10, 10), (1, 2, 3, 255))  # content changes, geometry does not
    sheet.save(pk / "tiles" / "world.png")
    again, issues, _ = _assemble(pk, previous=first)
    assert again.asset("gutter32.tiles.world").status != "CONFLICT"
    assert "TILE-004" not in [i.code for i in issues]


def test_tileset_naming_by_size_and_interior(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for rel, size in (
        ("tiles/a16.png", (64, 64)),
        ("tiles/b16.png", (64, 64)),
        ("tiles/c32.png", (128, 64)),
        ("interior/rooms16.png", (64, 64)),
        ("interior/rooms32.png", (128, 64)),
    ):
        (pk / rel).parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        cell = 32 if "32" in rel else 16
        for x in range(0, size[0], cell):
            for y in range(0, size[1], cell):
                tile = Image.new(
                    "RGBA",
                    (cell, cell),
                    (30 + x * 3 % 200, 60 + y * 5 % 150, 90 + (x + y) % 100, 255),
                )
                img.paste(tile, (x, y))
        img.save(pk / rel)
    cat, _, _ = _assemble(pk)
    names = {a.id: a.detected["tileset"] for a in cat.assets if a.detected["usage"] == "tiles"}
    assert {t.name for t in cat.tilesets} == set(names.values())
    assert names["pk.tiles.a16"] == names["pk.tiles.b16"]
    assert names["pk.tiles.c32"] != names["pk.tiles.a16"]
    assert names["pk.interior.rooms16"].startswith("interior")
    assert names["pk.interior.rooms16"] != names["pk.interior.rooms32"]
    sizes = {t.name: t.tile_size for t in cat.tilesets}
    assert all(sizes[names[a]][0] in (16, 32) for a in names)


def test_user_tileset_override_groups_assets() -> None:
    first, _, _ = _assemble(SYNTH / "mixed")
    first.asset("mixed.tiles.ground16").overrides = {"tileset": "custom"}
    first.asset("mixed.tiles.ground32").overrides = {"tileset": "custom"}
    again, _, _ = _assemble(SYNTH / "mixed", previous=first)
    custom = next(t for t in again.tilesets if t.name == "custom_32" or t.name == "custom")
    assert {
        s["asset"] for t in again.tilesets for s in t.sources if t.name.startswith("custom")
    } == {
        "mixed.tiles.ground16",
        "mixed.tiles.ground32",
    }
    assert custom.tile_size[0] in (16, 32)


def test_tiled_terrain_sets_join_the_tileset() -> None:
    cat, _, _ = _assemble(SYNTH / "tiled_meta")
    tdef = cat.tilesets[0]
    assert [t["name"] for t in tdef.terrain_sets] == ["ground"]
    assert tdef.terrain_sets[0]["mode"] == "corners"


def test_objects_become_sheet_objects() -> None:
    cat, _, _ = _assemble(SYNTH / "objects_in_sheet")
    assert [o.id for o in cat.objects] == [
        "objects_in_sheet.town#object_1",
        "objects_in_sheet.town#object_2",
    ]
    assert cat.objects[1].region == [16, 16, 80, 64] and cat.objects[1].role == "BUILDING"
    assert cat.objects[1].sheet == "objects_in_sheet.town" and cat.objects[1].source == "auto"


def test_folder_rules_write_the_rule_layer() -> None:
    first, _, _ = _assemble(SYNTH / "mixed")
    first.folder_rules = [
        FolderRule("mixed", "items/**", {"role": "WEAPON"}),
        FolderRule("mixed", "items/item_01.png", {"tags": ["special"]}),
        FolderRule("other_pack", "**", {"role": "NPC"}),
    ]
    again, _, _ = _assemble(SYNTH / "mixed", previous=first)
    icon = again.asset("mixed.items.item_01")
    assert icon.rule == {"role": "WEAPON", "tags": ["special"]}
    assert catalog.effective(icon)["role"] == "WEAPON"
    assert again.asset("mixed.items.item_02").rule == {"role": "WEAPON"}
    assert again.asset("mixed.tiles.ground16").rule == {}
    # an override beats a rule
    again.asset("mixed.items.item_02").overrides = {"role": "ITEM"}
    assert catalog.effective(again.asset("mixed.items.item_02"))["role"] == "ITEM"
    schema.validate("catalog", again.to_json())
    # rules are re-applied from scratch
    again.folder_rules = []
    catalog.apply_folder_rules(again)
    assert again.asset("mixed.items.item_01").rule == {}


def test_profile_rules_are_added_once() -> None:
    class Profile:
        folder_rules = [FolderRule("mixed", "backgrounds/**", {"tags": ["bg"]})]

    cat, _, _ = _assemble(SYNTH / "mixed", profiles=[Profile()])
    assert cat.asset("mixed.backgrounds.sky").rule == {"tags": ["bg"]}
    catalog.apply_folder_rules(cat, Profile.folder_rules)
    assert len(cat.folder_rules) == 1


@pytest.mark.parametrize(
    ("kwargs", "overrides", "confidence", "expected"),
    [
        ({}, {}, 0.5, "NEEDS_REVIEW"),
        ({}, {}, 0.75, "AUTO_DETECTED"),
        ({}, {}, 0.999, "CONFIRMED"),
        ({}, {"role": "WALL"}, 0.1, "CONFIRMED"),
        ({"user_confirmed": True}, {}, 0.1, "CONFIRMED"),
        ({"file_missing": True}, {"role": "WALL"}, 1.0, "MISSING"),
        ({}, {"role": "NONE"}, 0.9, "UNUSED"),
    ],
)
def test_recompute_status(kwargs: dict, overrides: dict, confidence: float, expected: str) -> None:
    asset = Asset(
        "a",
        "p",
        "p/a.png",
        "0" * 64,
        "image",
        "AUTO_DETECTED",
        {"role": "GROUND", "usage": "tiles"},
        overrides,
        "x",
        confidence,
    )
    assert catalog.recompute_status(asset, **kwargs) == expected


def test_conflict_status_is_sticky() -> None:
    asset = Asset(
        "a",
        "p",
        "p/a.png",
        "0" * 64,
        "image",
        "CONFLICT",
        {"role": "GROUND", "usage": "tiles"},
        {"role": "WALL"},
        "x",
        1.0,
    )
    assert catalog.recompute_status(asset) == "CONFLICT"
    assert catalog.recompute_status(asset, file_missing=True) == "MISSING"


def test_catalog_roundtrip_with_rule_layer(tmp_path: Path) -> None:
    cat, _, _ = _assemble(SYNTH / "mixed")
    cat.folder_rules = [FolderRule("mixed", "items/**", {"role": "WEAPON"})]
    catalog.apply_folder_rules(cat)
    path = tmp_path / "asset_catalog.json"
    catalog.save(cat, path)
    loaded = catalog.load(path)
    assert loaded.to_json() == cat.to_json()
    assert copy.deepcopy(loaded.asset("mixed.items.item_01").rule) == {"role": "WEAPON"}
