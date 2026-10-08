from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import orchestrator

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "test_packs" / "synthetic" / "basic16"


def _generate(godot_exe: Path, tmp_path: Path, name: str = "out") -> orchestrator.RunResult:
    cfg = orchestrator.default_config_for_pack(PACK, "Basic16 Test")
    from rpggen.core import config

    cfg_path = tmp_path / f"{name}_cfg.json"
    config.save(cfg, cfg_path)
    return orchestrator.run(cfg_path, tmp_path / name, godot_exe)


def test_generate_basic16(godot_exe: Path, tmp_path: Path) -> None:
    result = _generate(godot_exe, tmp_path)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    target = result.target
    for rel in (
        "generated/tilesets/overworld.tres",
        "generated/sprite_frames/basic16.characters.hero.tres",
        "generated/scenes/actors/player.tscn",
        "generated/scenes/bootstrap/boot.tscn",
        "game/maps/starter_map.tscn",
        "project.godot",
        "rpggen/asset_catalog.json",
        "rpggen/generator_config.json",
        "rpggen/results/build_results.json",
        "rpggen/results/validation_results.json",
        "rpggen/results/smoke_results.json",
        "assets/packs/basic16/tiles/terrain.png",
    ):
        assert (target / rel).exists(), rel
    assert not (target / ".rpggen_staging").exists()
    assert not (target / ".rpggen_failed").exists()
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True
    assert [i["name"] for i in smoke["items"]][:21] == [
        "title_new_game",
        "map_music",
        "boot",
        "player_exists",
        "player_moves",
        "collision_blocks",
        "npc_dialogue",
        "chest_open",
        "enter_building",
        "exit_building",
        "decor_blocks",
        "walk_to_field",
        "return_from_field",
        "autosave",
        "save_slot_1",
        "save_overwrite_confirm",
        "equip_raises_attack",
        "shop_buy_sell",
        "quest_journal",
        "mutate_then_load",
        "pause_menu",
    ]
    assert all(i["ok"] for i in smoke["items"])
    assert not any(i.severity.value == "error" for i in result.issues)


def test_sabotaged_player_script_fails_generation(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_DEV", "1")
    monkeypatch.setenv("RPGGEN_TEST_SABOTAGE", "broken_player")
    result = _generate(godot_exe, tmp_path, "sabotaged")
    assert not result.ok
    codes = {i.code for i in result.issues}
    assert codes & {"VAL-001", "SMOKE-001"}, codes
    assert result.failed_staging is not None and result.failed_staging.exists()
    assert result.report_path is not None and result.report_path.exists()
    # nothing was promoted into the target
    assert not (result.target / "project.godot").exists()
    # T12.20: the kept copy has the logs and no copy of the art
    failed = result.failed_staging
    assert not list(failed.rglob("*.png")), "a failed run must not keep the pack art"
    assert not (failed / "assets" / "packs").exists()
    assert (failed / "rpggen" / "logs").is_dir() and (failed / "project.godot").is_file()
    note = (failed / "FAILED_RUN.md").read_text(encoding="utf-8")
    assert "assets/packs/" in note


def test_sabotage_hook_is_inert_without_dev_flag(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RPGGEN_DEV", raising=False)
    monkeypatch.setenv("RPGGEN_TEST_SABOTAGE", "broken_player")
    result = _generate(godot_exe, tmp_path, "inert")
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
