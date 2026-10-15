"""A farm of the synthetic `farm_cave` pack (a ground sheet whose first tile is no ground, a cave's
sheet of rock, a picture of water and a sheet of fish icons) with `farm_layered`'s player and
*Combat* on: its maps are laid with the plain tile, its cave with the pack's rock, its pond with
the picture of water, and it passes the farm's smoke run (after T17.24 and T17.29)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import config, orchestrator, world_plan

pytestmark = [pytest.mark.integration, pytest.mark.farm]

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(scope="module")
def farm(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        refs = [
            config.pack_ref_from_source(SYNTH / "farm_cave", "farm_cave"),
            config.pack_ref_from_source(SYNTH / "farm_layered", "farm_layered"),
        ]
        cfg = config.default_for("Cave Ground", refs, archetype="farm")
        cfg.features["combat"] = True
        target = tmp_path_factory.mktemp("f") / "o"
        result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
        errors = [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]
        assert result.ok, errors
        yield target
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


def _text(target: Path, rel: str) -> str:
    return (target / rel.removeprefix("res://")).read_text(encoding="utf-8")


def test_the_farm_passes_its_smoke_run_with_its_cave(farm: Path) -> None:
    smoke = jsonio.read(farm / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    names = [i["name"] for i in smoke["items"]]
    assert "enter_the_cave" in names and "defeat_an_enemy" in names


def test_the_ground_is_the_plain_tile_of_the_sheet(farm: Path) -> None:
    ground = world_plan.load(farm)["farm"]["ground"]
    assert ground["asset"] == "farm_cave.farm_cave_pack.tileset.tileset_grass_meadow"
    assert ground["base"] == [1, 0], "not the edge of the bed the sheet begins with"


def test_the_cave_is_laid_with_the_packs_rock_and_is_dark(farm: Path) -> None:
    plan = world_plan.load(farm)["farm"]["map"]
    cave = next(e for e in plan["added"] if e["kind"] == "cave")
    scene = _text(farm, cave["map"])
    assert "Rock Caves.png" in scene, "the cave's sheet of rock is used"
    assert "region = Rect2(16, 0, 16, 16)" in scene, "its textured face, not the dark floor"
    assert scene.count('[node name="Cell_') > len(cave["walls"])
    assert "ambient_override = Color(0.5, 0.48, 0.6, 1)" in scene


def test_the_pond_is_the_picture_of_water_not_the_fish_icons(farm: Path) -> None:
    data = jsonio.read(farm / "rpggen/asset_catalog.json")
    by_id = {a["id"]: a for a in data["assets"]}
    assert by_id["farm_cave.farm_cave_pack.icons.fish.sea.dolphin"]["detected"]["role"] == "ITEM"
    sources = {s["asset"] for t in data["tilesets"] for s in t["sources"]}
    assert "farm_cave.farm_cave_pack.tileset.water_tile" in sources
    assert "farm_cave.farm_cave_pack.icons.fish.sea.dolphin" not in sources
