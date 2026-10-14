"""T17.29: a farm of packs in the shapes of the real farming packs. The synthetic `farm_crops`
(crops a strip each that grow in their pictures, food icons, a hen in a sheet of rows) and
`farm_layered` (a player drawn in pieces, a file an action) make a farm whose crops, hen and
player are the packs' own, and it passes the farm's smoke run."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import config, orchestrator

pytestmark = [pytest.mark.integration, pytest.mark.farm]

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(scope="module")
def farm(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        refs = [
            config.pack_ref_from_source(SYNTH / "farm_crops", "farm_crops"),
            config.pack_ref_from_source(SYNTH / "farm_layered", "farm_layered"),
        ]
        cfg = config.default_for("Real Shapes", refs, archetype="farm")
        cfg.starter_map["animals"] = "coop"
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


def test_the_farm_of_the_real_shapes_passes_its_smoke_run(farm: Path) -> None:
    smoke = jsonio.read(farm / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    names = [i["name"] for i in smoke["items"]]
    assert "crop_ripens" in names and "harvest" in names


def test_its_crops_grow_in_the_packs_pictures(farm: Path) -> None:
    crops = jsonio.read(farm / "generated/data/crops.json")["crops"]
    assert sorted(c["id"] for c in crops) == ["cabbage", "carrot"]
    assert {c["stages"] for c in crops} == {5, 6}
    for crop in crops:
        scene = (farm / crop["scene"].removeprefix("res://")).read_text(encoding="utf-8")
        assert "generated/farm_crops/farm_crops__crops_spring_" in scene


def test_its_hen_and_its_player_are_the_packs(farm: Path) -> None:
    animals = jsonio.read(farm / "generated/data/animals.json")
    assert "farm_crops" in str(animals)
    player = (farm / "generated/scenes/actors/player.tscn").read_text(encoding="utf-8")
    assert "farm_layered.lpc_character.character" in player
    sheet = farm / "generated/lpc_characters/farm_layered__lpc_character__character.png"
    assert sheet.is_file()
