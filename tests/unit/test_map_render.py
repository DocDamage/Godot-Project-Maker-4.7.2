from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, config, inventory, map_preview, profiles

SAMPLE = Path(__file__).resolve().parents[2] / "sample_pack"


@pytest.fixture(scope="module")
def sample(tmp_path_factory: pytest.TempPathFactory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("RPGGEN_CACHE_DIR", str(tmp_path_factory.mktemp("cache")))
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
        built = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cat = built[0]

    def resolver(asset):  # generated assets (composed terrain atlases) have no file here
        parts = asset.path.split("/", 3)
        return SAMPLE / parts[3] if parts[:2] == ["assets", "packs"] else None

    return cat, resolver


def test_the_default_plan_draws_the_house_and_the_markers(sample) -> None:
    cat, resolver = sample
    art = map_preview.load_art(cat, resolver)
    assert art.building is not None and art.ground is not None and art.wall is not None
    plan = map_preview.plan(config.starter_map_defaults(), 12345, map_preview.building_info(art))
    assert plan["is_default"] and plan["buildings"] == [[8, 6]]
    scale = 2
    image = map_preview.render(plan, art, scale, legend=False)
    tile = art.tile_px
    assert image.size == (40 * tile * scale, 24 * tile * scale)
    flat = map_preview.render(plan, map_preview.Art(tile_px=tile), scale, legend=False)
    house = image.getpixel((8 * tile * scale + 20, 6 * tile * scale + 20))
    assert house != flat.getpixel((8 * tile * scale + 20, 6 * tile * scale + 20))
    # the spawn marker is a white dot with a black outline in the middle of its tile
    sx, sy = plan["spawn"]
    centre = (sx * tile * scale + tile * scale // 2, sy * tile * scale + tile * scale // 2)
    assert image.getpixel(centre)[:3] == map_preview.MARKER_COLORS["spawn"]
    nx, ny = plan["npcs"][0]
    assert image.getpixel((nx * tile * scale + tile, ny * tile * scale + tile))[:3] == (
        66,
        165,
        245,
    )


def test_the_legend_adds_two_rows_and_says_the_map_may_differ(sample) -> None:
    cat, resolver = sample
    art = map_preview.load_art(cat, resolver)
    plan = map_preview.plan(config.starter_map_defaults(), 1, map_preview.building_info(art))
    with_legend = map_preview.render(plan, art, 1, legend=True)
    without = map_preview.render(plan, art, 1, legend=False)
    assert with_legend.size == (without.width, without.height + 32)
    assert "can differ" in map_preview.LEGEND_NOTE


def test_a_larger_map_with_more_of_everything_still_renders(sample) -> None:
    cat, resolver = sample
    art = map_preview.load_art(cat, resolver)
    options = {
        **config.starter_map_defaults(),
        "size": [64, 40],
        "buildings": 3,
        "npcs": 4,
        "decorations": 30,
    }
    plan = map_preview.plan(options, 7, map_preview.building_info(art))
    image = map_preview.render(plan, art, 1, legend=True)
    assert image.width == 64 * art.tile_px
    assert plan["exit_gap"][0] == 63


def test_without_any_art_flat_colours_are_used() -> None:
    plan = map_preview.plan(config.starter_map_defaults(), 1, {})
    image = map_preview.render(plan, map_preview.Art(), 1, legend=False)
    assert image.getpixel((20 * 16 + 4, 5 * 16)) != (0, 0, 0, 0)
