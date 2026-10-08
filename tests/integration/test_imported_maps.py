"""T12.49: packs with Tiled and LDtk maps generate with those maps and pass the smoke test."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, orchestrator, requirements

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _generate(
    pack: Path,
    selection: dict[str, object],
    godot_exe: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> orchestrator.RunResult:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "analysis_cache"))
    opened = archive.open_pack(pack, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = orchestrator.default_config_for_pack(pack, "Maps " + pack.name)
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    cfg.imported_maps = selection
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    return orchestrator.run(cfg_path, tmp_path / "out", godot_exe, placeholders=missing)


def _checks(result: orchestrator.RunResult) -> dict[str, bool]:
    validation = jsonio.read(result.target / "rpggen/results/validation_results.json")
    return {i["target"]: i["ok"] for i in validation["items"] if i.get("check") == "map_round_trip"}


def test_tiled_maps_are_built(godot_exe: Path, tmp_path: Path, monkeypatch) -> None:
    selection = {
        "include": ["tiled_map.maps.town", "tiled_map.maps.cave", "tiled_map.maps.infinite"],
        "starter": "tiled_map.maps.town",
    }
    result = _generate(SYNTH / "tiled_map", selection, godot_exe, tmp_path, monkeypatch)
    errors = [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]
    assert result.ok, errors
    target = result.target
    starter = (target / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'name="StarterMap"' in starter
    assert "Solid_" not in starter  # a Tiled map has no IntGrid
    assert "Door_to_cave" in starter  # the door found the cave, which is built too
    assert "res://game/maps/imported/tiled_map/maps_cave.tscn" in starter
    assert "Sign_notice" in starter and 'name="start"' in starter
    assert (target / "game/maps/imported/tiled_map/maps_cave.tscn").is_file()
    assert (target / "game/maps/imported/tiled_map/maps_infinite.tscn").is_file()
    assert not (target / "game/maps/imported/tiled_map/maps_town.tscn").exists()  # the starter
    assert not (target / "game/maps/imported/tiled_map/maps_zstd_layer.tscn").exists()
    # no demo content in an imported starter map, so no east exit and no field
    assert not (target / "game/maps/field_1.tscn").exists()
    checks = _checks(result)
    assert checks["game/maps/starter_map.tscn"] is True
    assert checks["game/maps/imported/tiled_map/maps_cave.tscn"] is True
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True and all(i["ok"] for i in smoke["items"])
    ledger = jsonio.read(target / "rpggen/ownership_ledger.json")
    owner = ledger["files"]["game/maps/imported/tiled_map/maps_cave.tscn"]["owner"]
    assert owner == "user_seed"


def test_an_ldtk_level_is_the_starter_map_with_collision(
    godot_exe: Path, tmp_path: Path, monkeypatch
) -> None:
    selection = {"starter": "ldtk_level.world.level_0"}
    result = _generate(SYNTH / "ldtk_level", selection, godot_exe, tmp_path, monkeypatch)
    errors = [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]
    assert result.ok, errors
    starter = (result.target / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'name="Solid_Collisions"' in starter
    # the wall value is one rectangle per merged area: a frame of 4 sides around the room
    assert starter.count("CollisionShape2D") >= 4
    smoke = jsonio.read(result.target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True and all(i["ok"] for i in smoke["items"])
    assert _checks(result)["game/maps/starter_map.tscn"] is True


def test_without_a_selection_no_map_is_imported(
    godot_exe: Path, tmp_path: Path, monkeypatch
) -> None:
    result = _generate(SYNTH / "tiled_map", {}, godot_exe, tmp_path, monkeypatch)
    assert result.ok
    assert not (result.target / "game/maps/imported").exists()
    starter = (result.target / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert "Door_" not in starter
