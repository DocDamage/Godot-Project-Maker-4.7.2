"""Recolour variants (T13.18): the renderer, the definitions and the catalog's effective assets."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import archive, catalog, inventory, variants
from rpggen.errors import IssueList

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _pixels(image: Image.Image) -> list[tuple[int, ...]]:
    rgba = image.convert("RGBA")
    return [rgba.getpixel((x, y)) for y in range(rgba.height) for x in range(rgba.width)]  # type: ignore[misc]


def _strip(colours: list[tuple[int, int, int, int]]) -> Image.Image:
    image = Image.new("RGBA", (len(colours), 1))
    for x, colour in enumerate(colours):
        image.putpixel((x, 0), colour)
    return image


# ------------------------------------------------------------------------ rendering


def test_a_hue_shift_of_120_degrees_turns_red_to_green_and_keeps_alpha() -> None:
    image = _strip([(255, 0, 0, 255), (255, 0, 0, 128), (10, 200, 30, 0), (128, 128, 128, 255)])
    out = _pixels(variants.render(image, "hue", {"shift": 120, "saturation": 1.0, "value": 1.0}))
    assert out[0] == (0, 255, 0, 255), "pure red becomes pure green"
    assert out[1] == (0, 255, 0, 128), "alpha is kept"
    assert out[2] == (10, 200, 30, 0), "a transparent pixel is not touched"
    assert out[3] == (128, 128, 128, 255), "grey has no hue to turn"
    again = _pixels(variants.render(image, "hue", {"shift": 240}))
    assert again[0] == (0, 0, 255, 255)
    assert _pixels(variants.render(image, "hue", {"shift": 0})) == _pixels(image), "no change"
    assert _pixels(variants.render(image, "hue", {"shift": 360})) == _pixels(image)


def test_saturation_and_value_multiply() -> None:
    image = _strip([(200, 100, 100, 255)])
    grey = _pixels(variants.render(image, "hue", {"shift": 0, "saturation": 0.0}))[0]
    assert grey[0] == grey[1] == grey[2] == 200, "no saturation: a grey of the same value"
    dark = _pixels(variants.render(image, "hue", {"shift": 0, "value": 0.5}))[0]
    assert dark == (100, 50, 50, 255)
    bright = _pixels(variants.render(image, "hue", {"shift": 0, "value": 4.0}))[0]
    assert bright[0] == 255, "the value stops at white"


def test_a_palette_map_changes_only_the_listed_colours() -> None:
    image = _strip([(255, 0, 0, 255), (254, 0, 0, 255), (0, 0, 255, 200), (255, 0, 0, 0)])
    out = _pixels(
        variants.render(
            image, "palette", {"map": [[[255, 0, 0], [1, 2, 3]], [[0, 0, 255], [9, 9, 9]]]}
        )
    )
    assert out == [(1, 2, 3, 255), (254, 0, 0, 255), (9, 9, 9, 200), (255, 0, 0, 0)]
    with pytest.raises(variants.VariantError):
        variants.render(image, "blur", {})


def test_the_render_is_byte_identical_across_runs() -> None:
    with Image.open(SAMPLE / "enemies" / "slime_idle.png") as opened:
        image = opened.convert("RGBA")
    params = {"shift": 77, "saturation": 1.3, "value": 0.9}
    first = variants.render_bytes(image, "hue", params)
    assert first == variants.render_bytes(image, "hue", params)
    assert first != variants.render_bytes(image, "hue", {**params, "shift": 78})
    out = Image.open(__import__("io").BytesIO(first))
    assert out.size == image.size and out.mode == "RGBA"
    assert [p[3] for p in _pixels(out)] == [p[3] for p in _pixels(image)], "alpha, pixel for pixel"


def test_the_palette_of_a_picture_is_its_visible_colours_most_used_first() -> None:
    image = _strip([(5, 5, 5, 255)] * 3 + [(9, 9, 9, 255)] + [(1, 1, 1, 0)] * 5)
    assert variants.palette_of(image) == [(5, 5, 5), (9, 9, 9)]
    assert variants.palette_of(image, limit=1) == [(5, 5, 5)]


# ------------------------------------------------------------------------ definitions


def test_ids_slugs_and_paths() -> None:
    assert variants.slug("Fire slime!") == "fire_slime"
    assert variants.slug("  ") == "variant"
    first = variants.new_id(set(), "pack", "Fire slime")
    assert first == "pack.variants.fire_slime"
    assert variants.new_id({first}, "pack", "Fire slime") == "pack.variants.fire_slime_2"
    assert variants.path_of(first) == "generated/variants/pack_variants_fire_slime.png"


def test_a_definition_is_checked_and_put_into_its_canonical_form() -> None:
    raw = {
        "id": "p.variants.a",
        "source": "p.x",
        "name": "A",
        "op": "hue",
        "params": {"shift": 480.4, "saturation": 9, "junk": 1},
        "stats": {"hp": 2, "attack": 1.0, "gold": "1.5", "speed": 3},
    }
    clean = variants.normalized(raw)
    assert clean["params"] == {"shift": 120, "saturation": 4.0, "value": 1.0}
    assert clean["stats"] == {"hp": 2.0, "gold": 1.5}, "a multiplier of 1 is not stored"
    schema.validate(
        "catalog",
        {**catalog.Catalog().to_json(), "variants": [clean]},
    )
    palette = variants.normalized(
        {**raw, "op": "palette", "params": {"map": [[(1, 2, 3), (4, 5, 6)]]}, "stats": {}}
    )
    assert palette["params"] == {"map": [[[1, 2, 3], [4, 5, 6]]]} and "stats" not in palette
    for bad in (
        {**raw, "op": "blur"},
        {**raw, "name": ""},
        {**raw, "params": {"shift": "red"}},
        {**raw, "op": "palette", "params": {"map": [[[1, 2, 300], [0, 0, 0]]]}},
        {**raw, "op": "palette", "params": {}},
        {**raw, "stats": {"hp": "many"}},
    ):
        with pytest.raises(variants.VariantError):
            variants.normalized(bad)


# ------------------------------------------------------------------------ the catalog


def _assemble(pack: Path, previous: catalog.Catalog | None = None):
    opened = archive.open_pack(pack, set(), pack_id="sample_pack")
    return catalog.assemble([(opened, inventory.build_inventory(opened))], previous, [])


def _fire_slime(cat: catalog.Catalog) -> dict:
    slime = next(a for a in cat.assets if a.path.endswith("slime_idle.png"))
    return {
        "id": variants.new_id({a.id for a in cat.assets}, slime.pack_id, "Fire slime"),
        "source": slime.id,
        "name": "Fire slime",
        "op": "hue",
        "params": {"shift": 120, "saturation": 1.0, "value": 1.0},
        "stats": {"hp": 2.0, "gold": 3.0},
    }


def test_a_variant_is_an_effective_asset_with_its_sources_facets(tmp_path: Path) -> None:
    pack = tmp_path / "sample_pack"
    shutil.copytree(SAMPLE, pack)
    cat, _issues, _generated = _assemble(pack)
    slime = next(a for a in cat.assets if a.path.endswith("slime_idle.png"))
    cat.variants = [_fire_slime(cat)]
    again, issues, generated = _assemble(pack, cat)
    assert not [i for i in issues if i.code == "ASSET-029"]
    variant = again.asset("sample_pack.variants.fire_slime")
    assert (
        variant is not None
        and variant.path == "generated/variants/sample_pack_variants_fire_slime.png"
    )
    facets, source_facets = catalog.effective(variant), catalog.effective(again.asset(slime.id))
    assert facets["derived_from"] == slime.id
    for key in ("usage", "role", "grid", "animations", "collision", "size"):
        assert facets.get(key) == source_facets.get(key), key
    assert variant.pack_id == slime.pack_id and variant.status == "CONFIRMED"
    assert variants.is_variant(variant) and not variants.is_variant(slime)
    # the picture is rendered into the cache and handed to the installer
    rendered = Path(generated[variant.path])
    assert rendered == variants.cached_file(variant.sha256) and rendered.is_file()
    with Image.open(rendered) as out, Image.open(pack / "enemies" / "slime_idle.png") as src:
        assert out.size == src.size
        assert out.convert("RGBA").tobytes() != src.convert("RGBA").tobytes()
    # the catalog with a variant is valid and round-trips; analysing again changes nothing
    data = again.to_json()
    schema.validate("catalog", data)
    assert catalog.Catalog.from_json(data).variants == again.variants
    third, issues3, _g = _assemble(pack, again)
    assert third.to_json() == data
    assert not [i for i in issues3 if i.code in ("ASSET-029", "CAT-004")]
    # what the user changed on the variant itself is kept
    third.asset(variant.id).overrides = {"role": "BOSS"}
    fourth, _i, _g = _assemble(pack, third)
    assert catalog.effective(fourth.asset(variant.id))["role"] == "BOSS"


def test_a_variant_never_takes_a_role_from_the_packs_own_asset(tmp_path: Path) -> None:
    from rpggen.core import mapping

    pack = tmp_path / "sample_pack"
    shutil.copytree(SAMPLE, pack)
    cat, _issues, _generated = _assemble(pack)
    slime = next(a for a in cat.assets if a.path.endswith("slime_idle.png"))
    cat.variants = [_fire_slime(cat)]
    again, _i, _g = _assemble(pack, cat)
    assert mapping.best_for(again, "ENEMY") == slime.id
    assert mapping.default_starter(again, "turn_based")["enemy"] == slime.id
    offered = [a.id for a in mapping.candidates(again, "ENEMY")]
    assert offered.index(slime.id) < offered.index("sample_pack.variants.fire_slime")
    # ... but the user may choose it
    assert mapping.valid_selection(again, "ENEMY", "sample_pack.variants.fire_slime")


def test_a_variant_follows_its_source(tmp_path: Path) -> None:
    pack = tmp_path / "sample_pack"
    shutil.copytree(SAMPLE, pack)
    cat, _issues, _generated = _assemble(pack)
    cat.variants = [_fire_slime(cat)]
    first, _i, _g = _assemble(pack, cat)
    before = first.asset("sample_pack.variants.fire_slime").sha256
    # the pack's picture changes: the variant is rendered again from it
    file = pack / "enemies" / "slime_idle.png"
    with Image.open(file) as opened:
        changed = opened.convert("RGBA")
    changed.putpixel((0, 0), (255, 0, 0, 255))
    changed.save(file)
    second, _i, _g = _assemble(pack, first)
    assert second.asset("sample_pack.variants.fire_slime").sha256 != before


def test_a_removed_source_gives_asset_029_and_no_asset(tmp_path: Path) -> None:
    pack = tmp_path / "sample_pack"
    shutil.copytree(SAMPLE, pack)
    cat, _issues, _generated = _assemble(pack)
    cat.variants = [_fire_slime(cat)]
    with_variant, _i, _g = _assemble(pack, cat)
    (pack / "enemies" / "slime_idle.png").unlink()
    after, issues, generated = _assemble(pack, with_variant)
    found = [i for i in issues if i.code == "ASSET-029"]
    assert len(found) == 1 and "sample_pack.variants.fire_slime" in found[0].message
    assert found[0].severity.value == "warning"
    assert after.asset("sample_pack.variants.fire_slime") is None, "dropped from the assets"
    assert not [p for p in generated if p.startswith("generated/variants/")]
    assert [v["id"] for v in after.variants] == ["sample_pack.variants.fire_slime"]
    schema.validate("catalog", after.to_json())
    # the definition is still there: the variant is back when the file is
    shutil.copy(SAMPLE / "enemies" / "slime_idle.png", pack / "enemies" / "slime_idle.png")
    back, issues_back, _g = _assemble(pack, after)
    assert back.asset("sample_pack.variants.fire_slime") is not None
    assert not [i for i in issues_back if i.code == "ASSET-029"]


def test_apply_reports_a_definition_it_cannot_use(tmp_path: Path) -> None:
    cat, _issues, _generated = _assemble(SAMPLE)
    issues = IssueList()
    bad = {"id": "x.variants.a", "source": "nope", "name": "A", "op": "blur", "params": {}}
    assert variants.apply(cat, [bad], {}, issues) == {}
    assert [i.code for i in issues] == ["ASSET-029"]
    assert cat.variants == []
