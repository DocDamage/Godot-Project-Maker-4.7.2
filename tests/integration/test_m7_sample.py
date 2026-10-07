"""Milestone M7: the turn-based archetype on the sample pack and on packs without an enemy."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import (
    archive,
    catalog,
    config,
    godot,
    inventory,
    mapping,
    orchestrator,
    profiles,
    requirements,
)

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
BASIC16 = REPO / "test_packs" / "synthetic" / "basic16"
M7_STEPS = [
    "encounter_start",
    "battle_victory",
    "rewards_granted",
    "returned_to_map",
    "enemy_stays_defeated",
    "defeat_policy",
]
BATTLE_COMMANDS = ["attack", "defend", "item", "run", "skill"]


def _generate(godot_exe: Path, target: Path, source: Path, pack_id: str):
    opened = archive.open_pack(source, set(), pack_id=pack_id)
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for("M7 Game", [config.pack_ref_from_source(source, pack_id)])
    cfg.starter = mapping.default_starter(cat, "turn_based")
    return orchestrator.run_in_memory(cfg, None, target, godot_exe)


@pytest.fixture(scope="module")
def sample(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        target = tmp_path_factory.mktemp("m7") / "out"
        result = _generate(godot_exe, target, SAMPLE, "sample_pack")
        assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
        yield target
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


def _smoke_names(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _no_vacuous_steps(target: Path) -> None:
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    assert "step passes" not in log, "a step passed only because nothing was there to test"


def test_the_turn_based_smoke_steps_pass_for_real_on_the_sample(sample: Path) -> None:
    names = _smoke_names(sample)
    assert names[-len(M7_STEPS) :] == M7_STEPS
    assert names.index("pause_menu") < names.index("encounter_start")
    _no_vacuous_steps(sample)


def test_the_generated_project_has_only_the_turn_based_archetype(sample: Path) -> None:
    archetypes = sample / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["turn_based"]
    assert sorted(
        p.name for p in (sample / "generated/builder/recipes").iterdir() if p.is_dir()
    ) == ["turn_based"]
    smoke = sorted(p.name for p in (sample / "generated/builder/smoke").glob("smoke_steps_*.gd"))
    assert smoke == [
        "smoke_steps_m1.gd",
        "smoke_steps_m4.gd",
        "smoke_steps_m6.gd",
        "smoke_steps_turn_based.gd",
    ]


def test_battle_data_and_scenes_exist(sample: Path) -> None:
    for rel in (
        "generated/scenes/battle/battle.tscn",
        "generated/scenes/combat/combat_mode.tscn",
        "generated/scenes/enemies/slime_idle.tscn",
        "game/data/enemies/slime_idle.tres",
    ):
        assert (sample / rel).is_file(), rel
    commands = sorted(p.stem for p in (sample / "game/data/battle_commands").glob("*.tres"))
    assert commands == BATTLE_COMMANDS
    boot = (sample / "generated/scenes/bootstrap/boot.tscn").read_text(encoding="utf-8")
    assert 'combat_scene = "res://generated/scenes/combat/combat_mode.tscn"' in boot


def test_the_battle_scene_has_the_documented_nodes(sample: Path) -> None:
    text = (sample / "generated/scenes/battle/battle.tscn").read_text(encoding="utf-8")
    names = re.findall(r'^\[node name="([^"]+)"', text, re.M)
    for expected in (
        "Battle", "Background", "EnemySlots", "PartySlots", "Controller", "UI", "CommandPanel",
        "Commands", "TargetCursor", "ItemSubmenu", "ItemList", "BattleLog", "LogLabel",
        "PartyStatus", "EnemyStatus", "Slot1", "Slot4",
    ):  # fmt: skip
        assert expected in names, expected


def test_the_enemy_is_scaled_and_placed_on_the_starter_map(sample: Path) -> None:
    definition = (sample / "game/data/enemies/slime_idle.tres").read_text(encoding="utf-8")
    assert "max_hp = 12" in definition and "attack = 4" in definition
    assert '"item_id": "potion"' in definition
    starter = (sample / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'entity_id = "starter_map_enemy_001"' in starter
    scene = (sample / "generated/scenes/enemies/slime_idle.tscn").read_text(encoding="utf-8")
    assert "Contact" in scene and "Persistent" in scene


def test_battle_text_is_in_the_translation_table(sample: Path) -> None:
    rows = (sample / "game/i18n/strings.tsv").read_text(encoding="utf-8")
    for key in ("BATTLE_ATTACK", "BATTLE_SKILLS_NONE", "BATTLE_LEVEL_UP"):
        assert key in rows, key


def test_rebuilding_leaves_the_turn_based_files_untouched(godot_exe: Path, sample: Path) -> None:
    def snapshot() -> dict[str, str]:
        out = {}
        for folder in ("game", "generated"):
            for p in sorted(q for q in (sample / folder).rglob("*") if q.is_file()):
                out[p.relative_to(sample).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    before = snapshot()
    run = godot.run_godot(
        godot.find_console_exe(godot_exe),
        sample,
        ["--script", "res://generated/builder/build.gd"],
        timeout_s=godot.BUILD_TIMEOUT_S,
        log_name="rebuild",
        log_dir=sample / "rpggen" / "logs",
    )
    assert run.returncode == 0
    assert snapshot() == before


def test_a_pack_without_an_enemy_uses_the_player_sprite(godot_exe: Path, tmp_path: Path) -> None:
    result = _generate(godot_exe, tmp_path / "b16", BASIC16, "basic16")
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert "ASSET-025" in {i.code for i in result.issues}
    names = _smoke_names(tmp_path / "b16")
    assert names[-len(M7_STEPS) :] == M7_STEPS
    assert (tmp_path / "b16/game/data/enemies/enemy_fallback.tres").is_file()


@pytest.mark.parametrize("pack_name", ["rpgmaker_like", "lpc_like"])
def test_the_gate_packs_pass_the_whole_turn_based_sequence(
    godot_exe: Path, tmp_path: Path, pack_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Like the all-packs test: required roles the pack lacks get debug placeholders."""
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    source = REPO / "test_packs" / "synthetic" / pack_name
    if not source.exists():
        source = source.with_suffix(".zip")
    opened = archive.open_pack(source, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = orchestrator.default_config_for_pack(source, "Gate " + pack_name)
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    result = orchestrator.run(cfg_path, tmp_path / "out", godot_exe, placeholders=missing)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    names = _smoke_names(tmp_path / "out")
    assert names[-len(M7_STEPS) :] == M7_STEPS
