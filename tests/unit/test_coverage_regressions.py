"""Portable reproductions of the 2026-10-28 real-pack findings. No third-party art."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from rpggen.core import archive, catalog, inventory, licenses, pack_forms, pack_readings
from rpggen.core.adapters import base, iso_sheets, pack_layouts, sheet_parts
from rpggen.errors import RpgGenError


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "runtime"))


def picture(root: Path, name: str, size: tuple[int, int]) -> inventory.InventoryFile:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", size)
    ImageDraw.Draw(im).rectangle((2, 2, min(10, size[0] - 1), min(10, size[1] - 1)), fill="red")
    im.save(path)
    return inventory.InventoryFile(
        name,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
        ".png",
        "image",
        {"w": size[0], "h": size[1], "frames": 1, "has_alpha": True},
    )


def test_named_furniture_is_not_promoted_to_a_house(monkeypatch: pytest.MonkeyPatch) -> None:
    from rpggen.core import figures

    monkeypatch.setattr(figures, "is_house", lambda _a: True)
    rgba = np.full((160, 160, 4), 255, dtype=np.uint8)
    facts, _ = sheet_parts._thing(rgba, "DECORATION", "", True)
    assert facts["role"] == "DECORATION"
    assert sheet_parts._role({"furniture"}, sheet_parts.ROLE_WORDS)[0] == "DECORATION"
    assert sheet_parts._role({"keys"}, sheet_parts.ROLE_WORDS)[0] == "ITEM"


def test_reviewed_regions_are_bound_to_the_entire_source_hash() -> None:
    sha, regions = next(iter(pack_readings.readings().items()))
    variant, expected = next(iter(regions.items()))
    assert pack_readings.region_facts(sha, variant) == expected
    assert pack_readings.region_facts("0" * 64, variant) == {}
    assert pack_readings.region_facts(sha, "o99999_99999") == {}
    found = pack_readings.region_facts(sha, variant)
    found["role"] = "BOSS"
    assert pack_readings.region_facts(sha, variant) == expected


@pytest.mark.parametrize(
    "name", ["COUPON.png", "2. How To.png", "Animation name.png", "FREE/0_Template_Tileset1_A.png"]
)
def test_guides_never_seed_objects_or_terrains(tmp_path: Path, name: str) -> None:
    picture(tmp_path, name, (768, 768))
    opened = archive.open_pack(tmp_path, set())
    cat, issues, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    assert not [i for i in issues if i.severity.value == "error"]
    assert len([a for a in cat.assets if a.kind == "image"]) == 1
    asset = next(a for a in cat.assets if a.kind == "image")
    assert asset.status == "UNUSED" and asset.detected["role"] == "NONE"
    assert not cat.objects and not cat.tilesets


def test_battler_with_detached_effects_stays_one_enemy(tmp_path: Path) -> None:
    f = picture(tmp_path, "rtdragon3.png", (674, 616))
    inv = inventory.Inventory("dragon_evolutions", "0" * 64, [f])
    result = pack_layouts.PackLayoutsAdapter().extract(inv, tmp_path, base.AdapterContext())
    assert len(result.assets) == 1
    assert result.assets[0].facets["role"] == "ENEMY"
    assert result.assets[0].facets["frame"] == [674, 616]
    assert result.assets[0].facets["animations"]["idle_down"]["frames"] == [[0, 0]]
    assert not result.assets[0].variant


def test_known_monster_layout_has_animations_not_cut_frame_objects(tmp_path: Path) -> None:
    f = picture(tmp_path, "00.png", (640, 1440))
    legend = inventory.InventoryFile(
        "Animation name.png", pack_layouts.MONSTER_LEGEND, 10, ".png", "image"
    )
    inv = inventory.Inventory("monsters", "0" * 64, [f, legend])
    result = pack_layouts.PackLayoutsAdapter().extract(inv, tmp_path, base.AdapterContext())
    assert len(result.assets) == 1
    facts = result.assets[0].facets
    assert facts["role"] == "ENEMY" and facts["frame"] == [80, 80]
    assert facts["animations"]["idle_down"]["frames"] == [[0, 0]]


def test_modern_direction_runs_are_not_a_single_384px_frame(tmp_path: Path) -> None:
    files = [
        picture(tmp_path, "Characters/Hero" + suffix, size)
        for suffix, size in (
            ("_16x16.png", (384, 224)),
            ("_idle_anim_16x16.png", (384, 32)),
            ("_run_16x16.png", (384, 32)),
        )
    ]
    inv = inventory.Inventory("modern", "0" * 64, files)
    result = pack_layouts.PackLayoutsAdapter().extract(
        inv, tmp_path, base.AdapterContext(pack_id="modern")
    )
    main = next(f for f in result.assets if f.facets.get("role") == "NPC")
    assert main.facets["frame"] == [16, 32]
    assert main.facets["animations"]["idle_up"]["frames"] == [[c, 0] for c in range(6, 12)]
    assert main.facets["animations"]["walk_right"]["source"].endswith("Hero_run_16x16.png")
    assert main.facets["animations"]["walk_right"]["frames"] == [[c, 0] for c in range(6)]
    assert main.facets["animations"]["idle_left"]["frames"] == [[c, 0] for c in range(12, 18)]


def test_full_folder_name_keeps_layout_clues_when_the_pack_id_is_truncated() -> None:
    inv = inventory.Inventory("medieval_fantasy_dungeon_prison_pixel", "0" * 64)
    assert not sheet_parts.is_tileset_pack(inv)
    assert sheet_parts.is_tileset_pack(inv, "Medieval Fantasy Dungeon Pixel Art Tileset Pack")


def test_verified_top_down_characters_can_have_a_jump() -> None:
    from rpggen.core import classifier

    inv = inventory.Inventory("topdown_monsters", "0" * 64)
    sheets = [{"tags": ["view:top"], "animations": {"jump_down": {}}} for _ in range(11)]
    assert classifier.made_for(inv, sheets) == "top"


def test_metadata_atlas_cannot_be_discarded_as_a_rearranged_copy() -> None:
    asset = catalog.Asset(
        "pack.sheet",
        "pack",
        "assets/packs/pack/sheet.png",
        "0" * 64,
        "image",
        "AUTO_DETECTED",
        {"usage": "tiles", "role": "GROUND"},
        detected_by="tiled",
    )
    assert pack_forms._protected(asset)


def test_vendor_named_parent_license_is_read(tmp_path: Path) -> None:
    (tmp_path / "Vendor License.txt").write_text(
        "Public Domain Dedication (CC0 1.0)", encoding="utf-8"
    )
    child = tmp_path / "Trees"
    child.mkdir()
    found = licenses.licence_above(child)
    assert found and found[1].license_id == "CC0-1.0"


def test_parent_license_survives_opening_a_wrappers_only_archive(tmp_path: Path) -> None:
    wrapper = tmp_path / "Trees"
    wrapper.mkdir()
    (tmp_path / "Vendor License.txt").write_text("CC0 1.0", encoding="utf-8")
    with zipfile.ZipFile(wrapper / "trees.zip", "w") as zf:
        zf.writestr("notes.txt", "tree pack")
    opened = archive.open_pack(wrapper, set())
    assert opened.licence_root == wrapper
    cat, _issues, _files = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    assert cat.packs[0].license["license_id"] == "CC0-1.0"


def test_archive_only_wrapper_names_choices_instead_of_reading_zero_assets(tmp_path: Path) -> None:
    tmp_path = tmp_path / "input"
    tmp_path.mkdir()
    for name in ("floor_large.rar", "floor_small.rar"):
        (tmp_path / name).write_bytes(b"unopened placeholder")
    with pytest.raises(RpgGenError) as caught:
        archive.open_pack(tmp_path, set())
    assert "select a pack archive" in caught.value.issue.message
    assert "floor_large.rar" in caught.value.issue.message


def test_magenta_key_preserves_the_packs_textured_pink_floor() -> None:
    rgba = np.array([[[255, 0, 255, 255], [236, 41, 137, 255]]], dtype=np.uint8)
    keyed = iso_sheets.keyed(rgba, (255, 0, 255))
    assert keyed[0, 0, 3] == 0
    assert keyed[0, 1, 3] == 255


def test_reviewed_caption_is_unused_and_user_edit_still_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = picture(tmp_path, "mixed.png", (32, 32))
    monkeypatch.setattr(pack_readings, "readings", lambda: {f.sha256: {"": {"role": "NONE"}}})
    opened = archive.open_pack(tmp_path, set())
    inv = inventory.build_inventory(opened)
    cat, _, _ = catalog.assemble([(opened, inv)], None, [])
    asset = next(a for a in cat.assets if a.sha256 == f.sha256)
    assert asset.status == "UNUSED" and not cat.objects and not cat.tilesets
    asset.overrides["role"] = "ITEM"
    edited, _, _ = catalog.assemble([(opened, inv)], cat, [])
    assert (
        catalog.effective(next(a for a in edited.assets if a.sha256 == f.sha256))["role"] == "ITEM"
    )


def test_checked_atlas_keeps_coordinates_and_does_not_invent_terrain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = picture(tmp_path, "furniture_16x16.png", (512, 1024))
    checked = {
        "usage": "tiles",
        "role": "DECORATION",
        "tags": ["terrain:manual", "objects:manual"],
        "grid": {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]},
    }
    monkeypatch.setattr(pack_readings, "readings", lambda: {f.sha256: {"": checked}})
    opened = archive.open_pack(tmp_path, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    images = [a for a in cat.assets if a.kind == "image"]
    assert len(images) == 1 and "#" not in images[0].id
    assert images[0].detected["grid"]["cell"] == [16, 16]
    assert images[0].status == "NEEDS_REVIEW"  # checked fields are not full certification
    assert not cat.objects
    assert not [t for t in cat.tilesets if t.terrain_sets]


def test_reviewed_semantics_cannot_regrid_a_tiled_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = picture(tmp_path, "fire.png", (176, 288))
    (tmp_path / "fire.tsx").write_text(
        '<tileset name="fire" tilewidth="16" tileheight="16" tilecount="198" columns="11">'
        '<image source="fire.png" width="176" height="288"/></tileset>',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        pack_readings,
        "readings",
        lambda: {
            f.sha256: {
                "": {
                    "role": "EFFECT",
                    "usage": "sprite",
                    "frame": [44, 48],
                    "grid": {"cell": [44, 48], "margin": [0, 0], "separation": [0, 0]},
                    "tags": ["terrain:manual"],
                    "animations": {"fire_0": {"frames": [[0, 5]], "fps": 8.0, "loop": True}},
                }
            }
        },
    )
    opened = archive.open_pack(tmp_path, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    asset = next(a for a in cat.assets if a.sha256 == f.sha256)
    assert asset.detected_by == "tiled" and asset.detected["role"] == "EFFECT"
    assert asset.detected["usage"] == "tiles"
    assert asset.detected["grid"]["cell"] == [16, 16]
    assert "fire_0" not in asset.detected.get("animations", {})


def test_optional_modern_actions_use_their_own_frame_width(tmp_path: Path) -> None:
    files = [
        picture(tmp_path, "Characters/Hero" + suffix, size)
        for suffix, size in (
            ("_16x16.png", (384, 224)),
            ("_idle_anim_16x16.png", (384, 32)),
            ("_phone_16x16.png", (144, 32)),
            ("_sit_16x16.png", (384, 32)),
            ("_sit2_16x16.png", (384, 32)),
            ("_sit3_16x16.png", (192, 32)),
        )
    ]
    result = pack_layouts.PackLayoutsAdapter().extract(
        inventory.Inventory("modern", "0" * 64, files), tmp_path, base.AdapterContext()
    )
    actions = {Path(a.path).name: a.facets for a in result.assets if a.facets.get("role") == "NPC"}
    assert actions["Hero_phone_16x16.png"]["frame"] == [16, 32]
    assert len(actions["Hero_phone_16x16.png"]["animations"]["phone_down"]["frames"]) == 9
    assert actions["Hero_sit_16x16.png"]["frame"] == [32, 32]
    assert actions["Hero_sit2_16x16.png"]["animations"]["sit2_right"]["frames"][-1] == [5, 0]
    assert actions["Hero_sit3_16x16.png"]["frame"] == [16, 32]
    assert set(actions["Hero_sit3_16x16.png"]["animations"]) == {"sit3_down", "sit3_up"}
    assert actions["Hero_sit3_16x16.png"]["animations"]["sit3_up"]["frames"] == [
        [i, 0] for i in range(6, 12)
    ]


def test_review_facts_do_not_alias_or_discard_unchecked_tags() -> None:
    facts = {"role": "BUILDING", "tags": ["house", "season:winter"]}
    checked = {"role": "ANIMAL", "tags": ["chicken"]}
    pack_readings.apply_facts(facts, checked)
    assert facts == {"role": "ANIMAL", "tags": ["chicken", "season:winter"]}
    facts["tags"].append("edited")
    assert checked["tags"] == ["chicken"]
