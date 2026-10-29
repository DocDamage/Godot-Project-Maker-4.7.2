from __future__ import annotations

import copy
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from rpggen import schema
from rpggen.core import archive, catalog, inventory, metadata_reviews, profiles


@pytest.fixture
def reviewed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "pack"
    root.mkdir()
    im = Image.new("RGBA", (32, 32))
    ImageDraw.Draw(im).rectangle((8, 8, 24, 31), fill="red")
    im.save(root / "item.png")
    opened = archive.open_pack(root, set())
    inv = inventory.build_inventory(opened)
    before, _, generated = catalog.assemble([(opened, inv)], None, [])
    a = next(a for a in before.assets if a.kind == "image" and a.detected["role"] != "NONE")
    path = Path(generated[a.path]) if a.path in generated else root / "item.png"
    approved = {
        **catalog.effective(a),
        "usage": "object",
        "role": "ITEM",
        "size": list(im.size),
        "frame": list(im.size),
        "origin": [16, 31],
        "animations": {},
        "collision": {"profile": "NONE"},
    }
    record = {
        "input": catalog.effective(a),
        "approved": approved,
        "pixel_sha256": metadata_reviews.pixel_hash(path),
    }
    data = {"assets": {a.sha256: {a.id.partition("#")[2]: record}}}
    monkeypatch.setattr(metadata_reviews, "readings", lambda: data)
    return opened, inv, before, a, path, record


def test_confirmation_applies_without_inflating_confidence(reviewed) -> None:
    opened, inv, _, old, _, record = reviewed
    cat, _, _ = catalog.assemble([(opened, inv)], None, [])
    a = cat.asset(old.id)
    assert a.status == "CONFIRMED" and a.confidence == old.confidence
    assert catalog.effective(a) == record["approved"]
    schema.validate("catalog", cat.to_json())


def test_source_render_and_input_facets_all_guard_confirmation(reviewed) -> None:
    _, _, _, a, path, record = reviewed
    variant = a.id.partition("#")[2]
    assert metadata_reviews.decision("0" * 64, variant, record["input"], path) is None
    assert metadata_reviews.decision(a.sha256, "unknown", record["input"], path) is None
    changed = {**record["input"], "origin": [0, 0]}
    assert metadata_reviews.decision(a.sha256, variant, changed, path) is None
    im = Image.open(path).convert("RGBA")
    im.putpixel((0, 0), (0, 0, 255, 255))
    im.save(path)
    assert metadata_reviews.decision(a.sha256, variant, record["input"], path) is None


def test_partial_or_invalid_metadata_never_confirms(reviewed) -> None:
    _, _, _, a, path, record = reviewed
    for key in ("role", "usage", "frame", "size", "animations", "origin", "collision"):
        saved = record["approved"]
        record["approved"] = {k: v for k, v in saved.items() if k != key}
        assert (
            metadata_reviews.decision(a.sha256, a.id.partition("#")[2], record["input"], path)
            is None
        )
        record["approved"] = saved


def test_user_override_has_priority(reviewed) -> None:
    opened, inv, before, a, _, _ = reviewed
    before.asset(a.id).overrides = {"origin": [3, 5]}
    cat, _, _ = catalog.assemble([(opened, inv)], before, [])
    assert catalog.effective(cat.asset(a.id))["origin"] == [3, 5]
    assert cat.asset(a.id).detected == a.detected


def test_packaged_confirmations_are_complete_valid_and_independent() -> None:
    data = metadata_reviews.readings()
    assert data["review_version"] == 1
    for sha, variants in data["assets"].items():
        assert len(sha) == 64
        for record in variants.values():
            assert metadata_reviews.complete_static(record["approved"])
            a = catalog.Asset(
                "test.picture",
                "test",
                "assets/packs/test/picture.png",
                sha,
                "image",
                "CONFIRMED",
                copy.deepcopy(record["approved"]),
            )
            schema.validate("catalog", catalog.Catalog(assets=[a]).to_json())


def test_profile_keys_refer_to_original_source_and_recreate_helpers(reviewed) -> None:
    opened, inv, before, a, _, _ = reviewed
    a.status = "CONFIRMED"
    a.path = "generated/sheet_parts/crop.png"
    data = profiles.export_profile(before, opened.pack_id, inv, {"title": "reviewed"})
    key = "item.png" + ("#" + a.id.partition("#")[2] if "#" in a.id else "")
    assert key in data["assets"]
    assert data["rendered_assets"] == [key]
    assert data["asset_hashes"]["item.png"] == a.sha256


def test_profile_reimport_regenerates_a_real_sheet_crop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "Furniture Tileset"
    root.mkdir()
    im = Image.new("RGBA", (512, 512))
    draw = ImageDraw.Draw(im)
    draw.rectangle((64, 64, 90, 108), fill="red")
    draw.rectangle((256, 256, 284, 300), fill="blue")
    im.save(root / "furniture.png")
    opened = archive.open_pack(root, set())
    inv = inventory.build_inventory(opened)
    before, _, gen = catalog.assemble([(opened, inv)], None, [])
    crops = [a for a in before.assets if "#" in a.id and a.path in gen]
    assert crops, "fixture must exercise the real sheet cutter"
    crop = crops[0]
    crop.status = "CONFIRMED"
    crop.overrides = {"origin": [4, 7], "collision": {"profile": "NONE"}}
    profile = profiles.export_profile(before, opened.pack_id, inv, {"title": "crops"})
    monkeypatch.setattr(profiles, "best_match", lambda _inv: (1.0, profile))
    fresh, _, files = catalog.assemble([(opened, inv)], None, [])
    got = fresh.asset(crop.id)
    assert got is not None and got.detected_by == "profile"
    assert catalog.effective(got)["origin"] == [4, 7]
    assert got.path in files and Path(files[got.path]).is_file()
    assert metadata_reviews.pixel_hash(Path(files[got.path])) == metadata_reviews.pixel_hash(
        Path(gen[crop.path])
    )


def test_fire_review_preserves_columns_styles_and_authored_timing() -> None:
    from rpggen.core import pack_readings

    first = pack_readings.region_facts(
        "16eff4750364b9da6163d5a13b678cb61fb3501378e68f0e8feb0dae169ff15b", ""
    )
    assert first["frame"] == [48, 48]
    assert [a["rects"][0] for a in first["animations"].values()] == [
        [0, 0, 32, 48],
        [32, 0, 48, 48],
        [80, 0, 48, 48],
        [128, 0, 48, 48],
    ]
    assert first["animations"]["fire_0"]["offsets"] == [[8, 0]] * 6
    second = pack_readings.region_facts(
        "6ce070d52b7766d48499339619e56117447a6c4be244a02536c12fba8229d27b", ""
    )
    assert len(second["animations"]) == 6
    for name, animation in second["animations"].items():
        col, style = map(int, name.split("_")[1:])
        assert animation["frames"] == [[col, style + phase * 2] for phase in range(3)]
        assert animation["fps"] == pytest.approx(1000 / 150)
