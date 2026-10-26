"""T17.30: games of packs in the shapes of Screaming Brain's, *Lords Of Pain*'s, SakPix's and
CuteSCKR's. The synthetic `iso_named` (sheets named by their cell: floors, wall faces, doorways)
makes an isometric village with walls along its edge and a house of pieces; `facings` (a knight
in sixteen facings, a villager in eight), `object_sheet` (animals and barns cut from sheets) and
`mixed_sheet` (grass sorted out of a mixed tile sheet) make a farm. Both pass their smoke runs."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, orchestrator, staging

pytestmark = [pytest.mark.integration]

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _run(
    cfg: config.GeneratorConfig,
    godot_exe: Path,
    tmp: pytest.TempPathFactory,
    ai_marked: str = "",
) -> Iterator[Path]:
    cache = tmp.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        target = tmp.mktemp("g") / "o"
        cat = None
        if ai_marked:
            # the audit's mark of AI-generated art on one of the packs (T17.30)
            opened = [
                archive.open_pack(Path(p.source), set(), pack_id=p.pack_id) for p in cfg.packs
            ]
            cat, _issues, _generated = catalog.assemble(
                [(o, inventory.build_inventory(o)) for o in opened], None, []
            )
            for pack in cat.packs:
                if pack.pack_id == ai_marked:
                    pack.license_overrides = {"ai_generated": True}
        result = orchestrator.run_in_memory(cfg, cat, target, godot_exe)
        errors = [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]
        assert result.ok, errors
        yield target
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


@pytest.fixture(scope="module")
def village(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    refs = [config.pack_ref_from_source(SYNTH / "iso_named", "iso_named")]
    cfg = config.default_for("Named Village", refs, archetype="turn_based")
    cfg.projection = "isometric"
    yield from _run(cfg, godot_exe, tmp_path_factory)


@pytest.fixture(scope="module")
def farm(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    refs = [
        config.pack_ref_from_source(SYNTH / name, name)
        for name in ("mixed_sheet", "object_sheet", "facings")
    ]
    cfg = config.default_for("Sheet Farm", refs, archetype="farm", base_tile_size=48)
    cfg.starter_map["animals"] = "coop_and_barn"
    yield from _run(cfg, godot_exe, tmp_path_factory, ai_marked="mixed_sheet")


@pytest.mark.isometric
def test_the_village_of_named_sheets_passes_its_smoke_run(village: Path) -> None:
    smoke = jsonio.read(village / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]


@pytest.mark.isometric
def test_its_edge_and_its_house_are_of_the_cut_wall_pieces(village: Path) -> None:
    starter = (village / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'name="Props"' in starter, "the wall along the edge is painted as pieces"
    house = village / "generated/scenes/objects/rpggen__iso_house.tscn"
    assert house.is_file(), "the house is put together from the pieces"
    tileset = next((village / "generated/tilesets").glob("iso*.tres")).read_text(encoding="utf-8")
    assert "rpggen_iso" in tileset or "iso_" in tileset


@pytest.mark.farm
def test_the_farm_of_sheets_and_facings_passes_its_smoke_run(farm: Path) -> None:
    smoke = jsonio.read(farm / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    names = [i["name"] for i in smoke["items"]]
    assert "harvest" in names and "go_to_the_village" in names


@pytest.mark.farm
def test_its_player_animals_and_ground_are_the_packs(farm: Path) -> None:
    player = (farm / "generated/scenes/actors/player.tscn").read_text(encoding="utf-8")
    assert "knight" in player, "the knight drawn in sixteen facings is the player"
    animals = jsonio.read(farm / "generated/data/animals.json")
    assert "n1_farm_animals" in str(animals), "an animal cut from the sheet of farm animals"
    data = jsonio.read(farm / "rpggen/asset_catalog.json")
    grounds = [a for a in data["assets"] if a["id"].endswith("farm.n1#g0_96")]
    assert grounds and grounds[0]["detected"]["role"] == "GROUND"


@pytest.mark.farm
def test_its_crop_is_the_row_of_growth_stages_of_the_mixed_sheet(farm: Path) -> None:
    """After T17.30: the row of stages on `mixed_sheet`'s sheet is a crop the farm grows (named
    by what it looks like since T17.33, as the others are)."""
    data = jsonio.read(farm / "rpggen/asset_catalog.json")
    crop = next(a for a in data["assets"] if a["id"].endswith("farm.n1#crop48_432"))
    assert crop["detected"]["role"] == "CROP" and crop["detected"]["stages"] == 4
    planned = jsonio.read(farm / "rpggen/world_plan.json")["farm"]["crops"]
    grown = [c["id"] for c in planned if c.get("asset") == crop["id"]]
    assert len(grown) == 1
    crops = jsonio.read(farm / "generated/data/crops.json")["crops"]
    assert grown[0] in [c["id"] for c in crops]


@pytest.mark.farm
def test_the_readme_names_the_pack_marked_as_ai_generated(farm: Path, village: Path) -> None:
    """T17.30: the farm uses `mixed_sheet`, marked as AI-generated art in the audit, and its
    README says so with the clean-up advice; the village, whose pack nobody marked, has no such
    section."""
    readme = (farm / "README.md").read_text(encoding="utf-8")
    assert "### AI-generated content" in readme and "**mixed_sheet**" in readme
    assert staging.AI_NOTE_STILL_DECLARED in readme
    assert "AI-generated content" not in (village / "README.md").read_text(encoding="utf-8")
