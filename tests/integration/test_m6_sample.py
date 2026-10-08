"""Milestone M6: the shared runtime systems on the sample pack and on basic16."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, mapping, orchestrator, profiles

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
BASIC16 = REPO / "test_packs" / "synthetic" / "basic16"
M6_STEPS = [
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
    "mutate_then_load",
    "pause_menu",
]
UI_SCENES = [
    "dialogue_box", "title_screen", "pause_menu", "inventory_menu", "status_menu",
    "save_load_menu", "settings_menu", "notification", "hud_basic", "game_over",
]  # fmt: skip


def _generate(godot_exe: Path, target: Path, source: Path, pack_id: str):
    opened = archive.open_pack(source, set(), pack_id=pack_id)
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for("M6 Game", [config.pack_ref_from_source(source, pack_id)])
    cfg.starter = mapping.default_starter(cat, "turn_based")
    return orchestrator.run_in_memory(cfg, None, target, godot_exe)


@pytest.fixture(scope="module")
def sample(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        target = tmp_path_factory.mktemp("m6") / "out"
        result = _generate(godot_exe, target, SAMPLE, "sample_pack")
        assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
        yield target
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


def _smoke(target: Path) -> dict:
    return jsonio.read(target / "rpggen/results/smoke_results.json")


def test_the_m6_smoke_sequence_passes_for_real_on_the_sample(sample: Path) -> None:
    smoke = _smoke(sample)
    assert smoke["ok"] is True
    names = [i["name"] for i in smoke["items"]]
    assert names[: len(M6_STEPS)] == M6_STEPS  # the archetype's own steps follow (see M7)
    assert all(i["ok"] for i in smoke["items"])
    log = (sample / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    assert "step passes" not in log, "a step passed only because nothing was there to test"


def test_basic16_runs_the_sequence_with_the_player_sprite_as_npc(
    godot_exe: Path, tmp_path: Path
) -> None:
    result = _generate(godot_exe, tmp_path / "b16", BASIC16, "basic16")
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    smoke = _smoke(tmp_path / "b16")
    assert [i["name"] for i in smoke["items"]][: len(M6_STEPS)] == M6_STEPS and smoke["ok"]
    assert "ASSET-022" in {i.code for i in result.issues}
    log = (tmp_path / "b16/rpggen/logs/godot_smoke.log").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "npc_dialogue: the starter map has no NPC" not in log


def test_no_menu_has_focus_problems(sample: Path) -> None:
    results = jsonio.read(sample / "rpggen/results/validation_results.json")
    assert "VAL-011" not in [i["code"] for i in results["issues"]]
    walked = {i["target"] for i in results["items"] if i["check"] == "ui_focus"}
    assert len(walked) == 7, walked


def test_generated_files_exist(sample: Path) -> None:
    for scene in UI_SCENES:
        assert (sample / f"generated/scenes/ui/{scene}.tscn").is_file(), scene
    for rel in (
        "generated/theme/main_theme.tres",
        "generated/audio/default_bus_layout.tres",
        "generated/i18n/strings_en.tres",
        "generated/scenes/actors/actor_base.tscn",
        "generated/scenes/actors/player.tscn",
        "generated/scenes/actors/npc.tscn",
        "game/data/actors/hero.tres",
        "game/data/new_game.tres",
        "game/data/items/potion.tres",
        "game/data/dialogue/npc_greeting.tres",
        "game/i18n/strings.tsv",
        "addons/rpg_runtime/VERSION",
        "addons/rpg_runtime/LICENSE",
        "rpggen/audio_index.json",
        "README.md",
    ):
        assert (sample / rel).is_file(), rel


def test_project_settings_register_the_runtime(sample: Path) -> None:
    text = (sample / "project.godot").read_text(encoding="utf-8")
    autoloads = re.findall(r"^(\w+)=\"\*res://addons/rpg_runtime/", text, re.M)
    assert autoloads == [
        "Events", "GameState", "SaveManager", "SceneRouter", "RpgSettings", "RpgSmoke",
    ]  # fmt: skip
    assert 'theme/custom="res://generated/theme/main_theme.tres"' in text
    assert 'main_scene="res://generated/scenes/bootstrap/boot.tscn"' in text
    assert "debug_toggle" in text
    boot = (sample / "generated/scenes/bootstrap/boot.tscn").read_text(encoding="utf-8")
    assert boot.count("title_screen") == 1


def test_the_starter_map_has_an_npc_and_a_chest(sample: Path) -> None:
    text = (sample / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'entity_id = "starter_map_npc_001"' in text
    assert 'entity_id = "starter_map_chest_001"' in text
    assert "npc_greeting.tres" in text


def test_dialogue_and_translations_are_seeded(sample: Path) -> None:
    csv = (sample / "game/i18n/strings.tsv").read_text(encoding="utf-8").splitlines()
    assert csv[0] == "keys	en"
    assert any(row.startswith("UI_NEW_GAME	New Game") for row in csv)
    assert any(row.startswith("ITEM_POTION_NAME	Potion") for row in csv)
    greeting = (sample / "game/data/dialogue/npc_greeting.tres").read_text(encoding="utf-8")
    assert "not flag:starter_npc.talked" in greeting and "give_item:potion:1" in greeting


def test_a_rebuild_changes_nothing(sample: Path, godot_exe: Path) -> None:
    csv = sample / "game/i18n/strings.tsv"
    index = sample / "rpggen/audio_index.json"
    before = (csv.read_bytes(), index.read_bytes())
    run = subprocess.run(  # noqa: S603
        [str(godot_exe), "--headless", "--path", str(sample), "--script",
         "res://generated/builder/build.gd"],
        capture_output=True, text=True, timeout=300, check=False,
    )  # fmt: skip
    assert run.returncode == 0, run.stdout[-500:]
    assert (csv.read_bytes(), index.read_bytes()) == before


def test_runtime_scripts_do_not_depend_on_game_content_paths() -> None:
    allowed = {
        "game_state.gd",
        "new_game_data.gd",
        "debug_overlay.gd",
        "battle_controller.gd",
    }  # registries, new-game data, test enemy, the user's battle commands and hero
    offenders = []
    for path in sorted((REPO / "godot_templates/addons/rpg_runtime").rglob("*.gd")):
        if path.name in allowed:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "res://game/" in line.split("##")[0]:
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert offenders == [], offenders
