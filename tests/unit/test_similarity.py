"""Picture hashes and what they find (T13.04)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from rpggen.core import analyzer, archive, cache, catalog, explain, inventory
from rpggen.core.analyzer import image_facts, similarity

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _tree(trunk=(110, 70, 30, 255), leaves=(30, 140, 50, 255)) -> Image.Image:
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 18, 17, 30], fill=trunk)
    d.ellipse([4, 2, 27, 20], fill=leaves)
    d.ellipse([9, 5, 15, 10], fill=(min(255, leaves[0] + 60), 200, 90, 255))
    return img


def _house() -> Image.Image:
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([3, 14, 28, 30], fill=(200, 170, 120, 255))
    d.polygon([(1, 14), (16, 2), (30, 14)], fill=(170, 40, 40, 255))
    d.rectangle([13, 21, 18, 30], fill=(90, 60, 30, 255))
    d.rectangle([5, 17, 10, 21], fill=(120, 190, 230, 255))
    return img


def _hash(img: Image.Image) -> str:
    return image_facts.dhash(np.asarray(img.convert("RGBA"), dtype=np.uint8))


def test_a_copy_a_pixel_edit_and_a_recolour_are_near_and_another_sprite_is_not() -> None:
    tree = _tree()
    edited = tree.copy()
    edited.putpixel((16, 25), (255, 255, 255, 255))
    recoloured = _tree(trunk=(90, 60, 80, 255), leaves=(170, 60, 40, 255))
    base = _hash(tree)
    assert len(base) == 16 and similarity.informative(base)
    assert similarity.distance(base, _hash(tree.copy())) == 0
    assert similarity.distance(base, _hash(edited)) <= 2
    assert similarity.distance(base, _hash(recoloured)) <= similarity.MAX_DISTANCE
    assert similarity.distance(base, _hash(_house())) > similarity.MAX_DISTANCE


def test_the_distance_is_symmetric_and_deterministic() -> None:
    a, b = _hash(_tree()), _hash(_house())
    assert similarity.distance(a, b) == similarity.distance(b, a) > 0
    assert _hash(_tree()) == a and _hash(_house()) == b
    assert similarity.distance(a, a) == 0
    # a flat picture says nothing, whatever its colour
    flat = _hash(Image.new("RGBA", (16, 16), (40, 200, 90, 255)))
    assert flat == "0" * 16 and not similarity.informative(flat)


def _pack(root: Path, name: str, files: dict[str, Image.Image]) -> Path:
    folder = root / name
    for rel, img in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
    (folder / "LICENSE.txt").write_text("CC0-1.0\n", encoding="utf-8")
    return folder


def _assemble(*folders: Path) -> catalog.Catalog:
    opened = [archive.open_pack(folder, set()) for folder in folders]
    return catalog.assemble([(o, inventory.build_inventory(o)) for o in opened], None, [])[0]


def test_near_lists_the_similar_assets_nearest_first(tmp_path: Path) -> None:
    edited = _tree()
    edited.putpixel((16, 25), (255, 255, 255, 255))
    folder = _pack(
        tmp_path,
        "woods",
        {
            "objects/tree.png": _tree(),
            "objects/tree_edit.png": edited,
            "objects/tree_autumn.png": _tree(leaves=(170, 60, 40, 255)),
            "objects/house.png": _house(),
        },
    )
    cat = _assemble(folder)
    found = similarity.near(cat, "woods.objects.tree")
    ids = [i for i, _d in found]
    assert set(ids) == {"woods.objects.tree_edit", "woods.objects.tree_autumn"}
    assert [d for _i, d in found] == sorted(d for _i, d in found)
    assert similarity.near(cat, "woods.objects.house") == []
    exact = similarity.near(cat, "woods.objects.tree", max_distance=0)
    assert all(d == 0 for _i, d in exact) and len(exact) <= len(found)
    assert similarity.near(cat, "no.such.asset") == []


def test_the_same_picture_in_two_packs_is_tagged_on_the_later_one(tmp_path: Path) -> None:
    almost = _tree()
    almost.putpixel((16, 25), (255, 255, 255, 255))
    a = _pack(tmp_path, "pack_a", {"forest/tree.png": _tree(), "forest/house.png": _house()})
    b = _pack(
        tmp_path,
        "pack_b",
        {
            "props/oak.png": almost,  # one pixel apart from pack_a's tree
            "props/big_oak.png": _tree().resize((64, 64), Image.Resampling.NEAREST),
            "props/flat.png": Image.new("RGBA", (32, 32), (9, 9, 9, 255)),
            "props/flat2.png": Image.new("RGBA", (32, 32), (200, 0, 0, 255)),
        },
    )
    cat = _assemble(a, b)
    oak = cat.asset("pack_b.props.oak")
    assert oak is not None and "duplicate_of:pack_a.forest.tree" in oak.detected["tags"]
    assert similarity.duplicate_of(oak) == "pack_a.forest.tree"
    assert "Looks like forest/tree from pack_a" in explain.why(oak)
    # not the original, not another size, not a flat picture
    for other in ("pack_a.forest.tree", "pack_b.props.big_oak", "pack_b.props.flat2"):
        asset = cat.asset(other)
        assert asset is not None and similarity.duplicate_of(asset) is None, other
    # nothing but the tag changed
    alone = _assemble(b).asset("pack_b.props.oak")
    assert alone is not None and similarity.duplicate_of(alone) is None
    assert {k: v for k, v in oak.detected.items() if k != "tags"} == {
        k: v for k, v in alone.detected.items() if k != "tags"
    }


def test_the_mixed_pack_has_a_repeated_file_and_it_is_tagged() -> None:
    cat = _assemble(SYNTH / "mixed")
    copy = cat.asset("mixed.items.spare.item_01")
    assert copy is not None and similarity.duplicate_of(copy) == "mixed.items.item_01"
    first = cat.asset("mixed.items.item_01")
    assert first is not None and similarity.duplicate_of(first) is None
    # in one pack only a byte-identical file counts: the other icons are not tagged
    tagged = [a.id for a in cat.assets if similarity.duplicate_of(a)]
    assert tagged == ["mixed.items.spare.item_01"]


def test_an_entry_cached_by_1_0_is_extended_without_a_new_analysis(tmp_path, monkeypatch) -> None:
    path = tmp_path / "tree.png"
    _tree().save(path)
    sha = "ab" * 32
    fresh = analyzer.analyze_file(path, sha, use_cache=False)
    assert fresh["dhash"] == _hash(_tree()) and fresh["region_dhashes"] is not None
    old = {k: v for k, v in fresh.items() if k not in ("dhash", "region_dhashes")}
    old["dominant_colors"] = ["#123456"]  # a marker: the other facts must not be made again
    cache.put(sha, analyzer.ANALYZER_VERSION, old)

    def no_analysis(*_args, **_kwargs):
        raise AssertionError("the image was analysed again")

    monkeypatch.setattr(analyzer, "analyze_array", no_analysis)
    extended = analyzer.analyze_file(path, sha)
    assert extended["dhash"] == fresh["dhash"]
    assert extended["dominant_colors"] == ["#123456"]
    stored = cache.get(sha, analyzer.ANALYZER_VERSION)
    assert stored is not None and stored["dhash"] == fresh["dhash"]
    assert stored["dominant_colors"] == ["#123456"]
    monkeypatch.setattr(image_facts, "load_rgba", no_analysis)
    assert analyzer.analyze_file(path, sha)["dhash"] == fresh["dhash"], "now a plain cache hit"


def test_region_hashes_follow_the_regions() -> None:
    sheet = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    sheet.paste(_tree(), (0, 0))
    sheet.paste(_house(), (32, 0))
    a = np.asarray(sheet, dtype=np.uint8)
    facts = image_facts.hashes(a, [[0, 0, 32, 32], [32, 0, 32, 32]])
    assert facts["region_dhashes"] == [_hash(_tree()), _hash(_house())]
    assert image_facts.hashes(a, None)["region_dhashes"] == []


@pytest.mark.parametrize("kind", ["audio", "font"])
def test_sounds_and_fonts_have_no_hash(kind: str) -> None:
    asset = catalog.Asset("p.x", "p", "assets/packs/p/x", "cd" * 32, kind, "AUTO_DETECTED", {})
    assert similarity.hash_of(asset) is None
