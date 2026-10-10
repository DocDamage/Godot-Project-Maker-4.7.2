from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import adapters, archive, inventory
from rpggen.core.adapters import AdapterContext
from rpggen.core.adapters.generic_grid import GenericGridAdapter, build_pack_prior
from rpggen.core.adapters.ldtk import LdtkAdapter
from rpggen.core.adapters.lpc import LpcAdapter
from rpggen.core.adapters.strips import StripsAdapter
from rpggen.core.analyzer import analyzer_for

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _open(pack_dir: Path):
    pack = archive.open_pack(pack_dir, set())
    inv = inventory.build_inventory(pack)
    ctx = AdapterContext(pack_id=inv.pack_id, analyze=analyzer_for(inv, pack.root))
    return inv, pack.root, ctx


def _by_path(res, path: str):
    return next(f for f in res.assets if f.path == path)


# ----------------------------------------------------------------------------- LPC


def test_lpc_like_pack() -> None:
    inv, root, ctx = _open(SYNTH / "lpc_like")
    adapter = LpcAdapter()
    assert adapter.match(inv, root) == 1.0
    res = adapter.extract(inv, root, ctx)
    frag = _by_path(res, "characters/body.png")
    f = frag.facets
    assert frag.claim == "full" and f["usage"] == "sprite" and f["frame"] == [64, 64]
    assert f["origin"] == [32, 60]
    anims = f["animations"]
    # LPC rows per action are up, left, down, right: walk starts at row 8
    assert anims["walk_down"]["frames"] == [[c, 10] for c in range(1, 9)]
    assert anims["walk_down"]["fps"] == 10.0
    assert anims["walk_up"]["frames"][0] == [1, 8]
    assert anims["idle_right"]["frames"] == [[0, 11]]
    assert anims["attack_left"]["frames"] == [[c, 13] for c in range(6)]
    assert anims["attack_left"]["active_frames"] == [3, 4] and anims["attack_left"]["fps"] == 12.0
    assert anims["hurt"]["frames"] == [[c, 20] for c in range(6)]
    assert anims["hurt"]["loop"] is False and anims["death"]["loop"] is False
    assert res.pack_warnings == []


def test_lpc_expanded_sheet_and_non_lpc(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    Image.new("RGBA", (832, 1408), (200, 0, 0, 255)).save(tmp_path / "pk" / "tall.png")
    inv, root, ctx = _open(tmp_path / "pk")
    res = LpcAdapter().extract(inv, root, ctx)
    # the rows under the classic 21 are read since M16 (they were ignored, with a warning);
    # tests/unit/test_lpc_collection.py has a sheet with something drawn in them
    assert res.pack_warnings == []
    assert _by_path(res, "tall.png").facets["frame"] == [64, 64]
    inv2, root2, _ = _open(SYNTH / "basic16")
    assert LpcAdapter().match(inv2, root2) == 0.0


# ----------------------------------------------------------------------------- strips


def test_strips_pack_groups_files_into_one_asset() -> None:
    inv, root, ctx = _open(SYNTH / "strips")
    adapter = StripsAdapter()
    assert adapter.match(inv, root) == 1.0
    res = adapter.extract(inv, root, ctx)
    assert [f.path for f in res.assets] == ["hero_attack_down.png", "slime_idle.png"]
    hero = _by_path(res, "hero_attack_down.png").facets
    assert sorted(hero["animations"]) == [
        "attack_down",
        "walk_down",
        "walk_left",
        "walk_right",
        "walk_up",
    ]
    assert hero["animations"]["attack_down"] == {
        "frames": [[0, 0], [1, 0], [2, 0]],
        "fps": 12.0,
        "loop": False,
        "source": "assets/packs/strips/hero_attack_down.png",
    }
    assert hero["animations"]["walk_left"]["source"] == "assets/packs/strips/hero_walk_left.png"
    assert hero["animations"]["walk_down"]["frames"] == [[0, 0], [1, 0], [2, 0], [3, 0]]
    assert hero["frame"] == [16, 16] and hero["origin"] == [8, 15]
    assert res.consumed == [
        "hero_walk_down.png",
        "hero_walk_left.png",
        "hero_walk_right.png",
        "hero_walk_up.png",
    ]
    slime = _by_path(res, "slime_idle.png").facets
    assert list(slime["animations"]) == ["idle_down"]  # a missing direction is assumed
    assert any(w.startswith("strips_direction_assumed") for w in res.pack_warnings)


def test_side_strip_gets_a_mirrored_left(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    strip = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for i in range(4):
        strip.paste(Image.new("RGBA", (6, 10), (200, 0, 0, 255)), (i * 16 + 5, 3))
    strip.save(tmp_path / "pk" / "orc_walk_side.png")
    inv, root, ctx = _open(tmp_path / "pk")
    res = StripsAdapter().extract(inv, root, ctx)
    anims = res.assets[0].facets["animations"]
    assert sorted(anims) == ["walk_left", "walk_right"]
    assert anims["walk_left"]["flip_h"] is True and "flip_h" not in anims["walk_right"]
    assert [i.code for i in res.issues] == ["ANIM-002"]


def test_non_strip_with_a_strip_like_name_is_left_alone(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    Image.new("RGBA", (64, 64), (10, 200, 10, 255)).save(tmp_path / "pk" / "grass_walk.png")
    inv, root, ctx = _open(tmp_path / "pk")
    res = StripsAdapter().extract(inv, root, ctx)
    assert res.assets == [] and res.consumed == []


def test_animated_gif_becomes_a_generated_strip(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    frames = []
    for i in range(3):
        fr = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        fr.paste(Image.new("RGBA", (3, 3), (255, 0, 0, 255)), (i, i))
        frames.append(fr)
    frames[0].save(
        tmp_path / "pk" / "slime_idle.gif",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    inv, root, ctx = _open(tmp_path / "pk")
    ctx.work_dir = tmp_path / "work"
    adapter = StripsAdapter()
    assert adapter.match(inv, root) == 1.0
    res = adapter.extract(inv, root, ctx)
    frag = _by_path(res, "slime_idle.gif")
    sha = inv.files[0].sha256
    target = f"generated/gif_strips/{sha}.png"
    assert res.generated == {target: str(tmp_path / "work" / "gif_strips" / f"{sha}.png")}
    anim = frag.facets["animations"]["idle_down"]
    assert anim["source"] == target
    assert anim["frames"] == [[0, 0], [1, 0], [2, 0]] and anim["fps"] == 10.0
    with Image.open(res.generated[target]) as strip:
        assert strip.size == (24, 8)


# ----------------------------------------------------------------------------- LDtk


def _ldtk(tmp_path: Path, doc: dict, files: dict[str, tuple[int, int]]) -> tuple:
    pk = tmp_path / "pk"
    pk.mkdir()
    for rel, size in files.items():
        (pk / rel).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", size, (255, 0, 0, 255)).save(pk / rel)
    (pk / "world.ldtk").write_text(json.dumps(doc), encoding="utf-8")
    return _open(pk)


def test_ldtk_tilesets_and_intgrid(tmp_path: Path) -> None:
    doc = {
        "defs": {
            "tilesets": [
                {"relPath": "art/tiles.png", "tileGridSize": 16, "spacing": 1, "padding": 2},
                {"relPath": None, "tileGridSize": 8},
                {"relPath": "missing.png", "tileGridSize": 16},
            ],
            "layers": [{"intGridValues": [{"identifier": "Wall"}, {"identifier": "floor"}]}],
        }
    }
    inv, root, ctx = _ldtk(tmp_path, doc, {"art/tiles.png": (80, 80)})
    adapter = LdtkAdapter()
    assert adapter.match(inv, root) == 1.0
    res = adapter.extract(inv, root, ctx)
    assert [(f.path, f.claim) for f in res.assets] == [("art/tiles.png", "full")]
    grid = res.assets[0].facets["grid"]
    assert grid == {"cell": [16, 16], "margin": [2, 2], "separation": [1, 1]}
    assert res.pack_warnings == ["ldtk_intgrid_collision_available"]
    assert [i.code for i in res.issues] == ["ADAPT-002"]


# ----------------------------------------------------------------------------- generic grid


def test_generic_decisions_on_synthetic_packs() -> None:
    inv, root, ctx = _open(SYNTH / "mixed")
    res = GenericGridAdapter().extract(inv, root, ctx)
    kinds = {f.path: f.facets["usage"] for f in res.assets}
    assert kinds["backgrounds/sky.png"] == "background"
    assert kinds["tiles/ground16.png"] == "tiles" and kinds["tiles/ground32.png"] == "tiles"
    assert all(kinds[f"items/item_{i:02d}.png"] == "sprite" for i in range(1, 13))
    icon = _by_path(res, "items/item_01.png")
    assert icon.facets == {"usage": "sprite", "frame": [16, 16], "origin": [8, 15]}
    assert icon.confidence == 0.6
    assert _by_path(res, "tiles/ground32.png").facets["grid"]["cell"] == [32, 32]
    assert all(f.claim == "partial" for f in res.assets)


def test_generic_directional_sheet_and_tiles_with_objects() -> None:
    inv, root, ctx = _open(SYNTH / "basic16")
    res = GenericGridAdapter().extract(inv, root, ctx)
    hero = _by_path(res, "characters/hero.png")
    assert hero.facets["usage"] == "sprite" and hero.facets["frame"] == [16, 24]
    assert hero.facets["directions"] == 4 and hero.confidence < 0.75  # directions are inferred
    assert hero.facets["animations"]["walk_left"]["frames"] == [[0, 1], [1, 1], [2, 1], [3, 1]]
    assert hero.facets["animations"]["idle_up"]["frames"] == [[0, 3]]
    inv, root, ctx = _open(SYNTH / "objects_in_sheet")
    res = GenericGridAdapter().extract(inv, root, ctx)
    assert _by_path(res, "town.png").facets["usage"] == "tiles"
    assert [(o["region"], o["role"]) for o in res.objects] == [
        ([112, 0, 32, 48], "DECORATION"),
        ([16, 16, 80, 64], "BUILDING"),
    ]
    house = res.objects[1]
    assert house["footprint"] == [0, 45, 80, 19] and house["origin"] == [40, 63]
    assert house["source"] == "auto" and house["sheet_path"] == "town.png"


def test_generic_strip_and_claimed_paths() -> None:
    inv, root, ctx = _open(SYNTH / "strips")
    ctx.claimed = {
        "hero_walk_down.png",
        "hero_walk_up.png",
        "hero_walk_left.png",
        "hero_walk_right.png",
        "hero_attack_down.png",
    }
    res = GenericGridAdapter().extract(inv, root, ctx)
    assert [f.path for f in res.assets] == ["slime_idle.png"]
    anims = res.assets[0].facets["animations"]
    assert list(anims) == ["idle_down"]
    assert anims["idle_down"]["frames"] == [[0, 0], [1, 0], [2, 0], [3, 0]]
    assert res.assets[0].confidence == 0.7


def test_generic_fallback_and_no_analysis(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(tmp_path / "pk" / "blob.png")
    inv, root, ctx = _open(tmp_path / "pk")
    res = GenericGridAdapter().extract(inv, root, ctx)
    assert res.assets[0].confidence == 0.3 and res.assets[0].facets["usage"] == "sprite"
    ctx.analyze = None
    assert GenericGridAdapter().extract(inv, root, ctx).assets == []


def test_pack_prior_from_earlier_results() -> None:
    inv, root, ctx = _open(SYNTH / "rpgmaker_like")
    adapters.register_defaults()
    results = adapters.run_adapters(inv, root, ctx)
    prior = build_pack_prior(results)
    assert prior == {48: 1.0}
    assert build_pack_prior([]) == {}


def test_all_default_adapters_run_over_every_synthetic_pack() -> None:
    adapters.register_defaults()
    for pack in sorted(p for p in SYNTH.iterdir() if p.is_dir() or p.suffix == ".zip"):
        inv, root, ctx = _open(pack)
        results = adapters.run_adapters(inv, root, ctx)
        failures = [i for r in results for i in r.issues if i.code == "ADAPT-001"]
        assert failures == [], (pack.name, failures)
        assert results and results[-1].adapter == "generic_grid"
        claimed_assets = {f.path for r in results for f in r.assets}
        images = {f.path for f in inv.files if f.kind == "image" and f.image}
        assert images <= claimed_assets | set(ctx.claimed), (pack.name, images - claimed_assets)
