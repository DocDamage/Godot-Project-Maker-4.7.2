"""Milestone M9: the action-RPG archetype on the sample pack, on a pack without an enemy (generic swing)
and on a pack with attack animations."""

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
M9_STEPS = [
    "enemy_detects",
    "player_attack_hits",
    "no_damage_outside_active_frames",
    "heavy_attack_hits",
    "enemy_dies",
    "player_hurt_invuln",
    "dodge",
    "ranged_enemy_shoots",
    "charger_charges",
    "player_bow_shoots",
    "persist",
    "death_policy",
    "game_over_screen",
]


def _generate(godot_exe: Path, target: Path, source: Path, pack_id: str):
    opened = archive.open_pack(source, set(), pack_id=pack_id)
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for(
        "M9 Game", [config.pack_ref_from_source(source, pack_id)], archetype="arpg"
    )
    cfg.starter = mapping.default_starter(cat, "arpg")
    return orchestrator.run_in_memory(cfg, None, target, godot_exe)


@pytest.fixture(scope="module")
def sample(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        target = tmp_path_factory.mktemp("m9") / "out"
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


def test_the_arpg_smoke_steps_pass_for_real_on_the_sample(sample: Path) -> None:
    names = _smoke_names(sample)
    assert names[-len(M9_STEPS) :] == M9_STEPS
    assert names.index("pause_menu") < names.index("enemy_detects")
    _no_vacuous_steps(sample)


def test_the_generated_project_has_only_the_arpg_archetype(sample: Path) -> None:
    archetypes = sample / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arpg"]
    assert sorted(
        p.name for p in (sample / "generated/builder/recipes").iterdir() if p.is_dir()
    ) == ["arpg"]
    smoke = sorted(p.name for p in (sample / "generated/builder/smoke").glob("smoke_steps_*.gd"))
    assert smoke == [
        "smoke_steps_arpg.gd",
        "smoke_steps_m1.gd",
        "smoke_steps_m4.gd",
        "smoke_steps_m6.gd",
    ]
    assert not (sample / "game/data/battle_commands").exists()


def test_scenes_and_data_exist(sample: Path) -> None:
    for rel in (
        "generated/scenes/combat/combat_mode.tscn",
        "generated/scenes/ui/hud_arpg.tscn",
        "generated/scenes/enemies/slime_idle.tscn",
        "generated/effects/swing_frames.tres",
        "game/data/enemies/slime_idle.tres",
    ):
        assert (sample / rel).is_file(), rel
    boot = (sample / "generated/scenes/bootstrap/boot.tscn").read_text(encoding="utf-8")
    assert 'combat_scene = "res://generated/scenes/combat/combat_mode.tscn"' in boot
    assert 'hud_scene = "hud_arpg"' in boot


def test_the_player_and_the_enemy_have_the_combat_parts(sample: Path) -> None:
    player = (sample / "generated/scenes/actors/player.tscn").read_text(encoding="utf-8")
    names = re.findall(r'^\[node name="([^"]+)"', player, re.M)
    for expected in ("Health", "Hurtbox", "AttackHitbox", "SwingEffect", "PlayerCombat"):
        assert expected in names, expected
    enemy = (sample / "generated/scenes/enemies/slime_idle.tscn").read_text(encoding="utf-8")
    names = re.findall(r'^\[node name="([^"]+)"', enemy, re.M)
    for expected in (
        "Detection", "Chase", "Wander", "EnemyAttack", "LootDrop", "Health", "Hurtbox",
        "AttackHitbox", "Sight", "Navigation", "Alert", "Persistent",
    ):  # fmt: skip
        assert expected in names, expected
    definition = (sample / "game/data/enemies/slime_idle.tres").read_text(encoding="utf-8")
    assert '"vision_px": 96' in definition and '"nav_mode": "direct"' in definition


def test_the_starter_map_places_two_enemies(sample: Path) -> None:
    starter = (sample / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'entity_id = "starter_map_enemy_001"' in starter
    assert 'entity_id = "starter_map_enemy_002"' in starter
    entities = jsonio.read(sample / "rpggen/demo_entities.json")["entities"]
    assert "starter_map_enemy_002" in entities


def test_arpg_text_is_in_the_translation_table(sample: Path) -> None:
    rows = (sample / "game/i18n/strings.tsv").read_text(encoding="utf-8")
    for key in ("ARPG_SET_QUICK", "ARPG_GOLD_GAINED"):
        assert key in rows, key
    assert "BATTLE_ATTACK" not in rows


def test_rebuilding_leaves_the_arpg_files_untouched(godot_exe: Path, sample: Path) -> None:
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
    assert names[-len(M9_STEPS) :] == M9_STEPS
    assert (tmp_path / "b16/game/data/enemies/enemy_fallback.tres").is_file()
    # No attack animation: the generic swing is used.
    frames = tmp_path / "b16/generated/sprite_frames"
    assert not any("attack_" in p.read_text(encoding="utf-8") for p in frames.rglob("*.tres"))


@pytest.mark.parametrize("pack_name", ["rpgmaker_like", "lpc_like"])
def test_the_gate_packs_pass_the_whole_arpg_sequence(
    godot_exe: Path, tmp_path: Path, pack_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Like the all-packs test: required roles the pack lacks get debug placeholders."""
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    source = REPO / "test_packs" / "synthetic" / pack_name
    if not source.exists():
        source = source.with_suffix(".zip")
    opened = archive.open_pack(source, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = orchestrator.default_config_for_pack(source, "Gate " + pack_name, archetype="arpg")
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    result = orchestrator.run(cfg_path, tmp_path / "out", godot_exe, placeholders=missing)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    names = _smoke_names(tmp_path / "out")
    assert names[-len(M9_STEPS) :] == M9_STEPS
    if pack_name == "lpc_like":
        # The character has attack animations: their active frames are stored with the frames.
        frames = tmp_path / "out/generated/sprite_frames"
        assert any(
            "active_frames_attack_" in p.read_text(encoding="utf-8") for p in frames.rglob("*.tres")
        )
