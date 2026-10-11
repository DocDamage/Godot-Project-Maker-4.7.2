"""Milestone M16, the shoot 'em up (T16.04): the synthetic `shooter` pack as a game that scrolls
up, and the top-down sample pack, which has nothing made for the kind, as one that scrolls
right with drawn stand-ins."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import arcade_kit, config, ledger, orchestrator, profiles

pytestmark = [pytest.mark.integration, pytest.mark.shmup]

REPO = Path(__file__).resolve().parents[2]
SHOOTER = REPO / "test_packs" / "synthetic" / "shooter"
SAMPLE = REPO / "sample_pack"
STEPS = [
    "title_new_game",
    "stage_scrolls",
    "ship_flies",
    "ship_shoots",
    "bomb_clears_bullets",
    "ship_is_destroyed_and_returns",
    "wave_is_fought",
    "power_up_is_picked_up",
]
SCENES = [
    "generated/scenes/shmup/ship.tscn",
    "generated/scenes/shmup/explosion.tscn",
    "generated/scenes/stages/stage_01.tscn",
    "generated/scenes/combat/combat_mode.tscn",
    "generated/scenes/ui/hud_arcade.tscn",
    "generated/scenes/shmup/powerup.tscn",
    "generated/scenes/shmup/enemies/popcorn_01.tscn",
    "generated/scenes/shmup/enemies/turret.tscn",
    "generated/scenes/shmup/enemies/asteroid.tscn",
    "generated/scenes/shmup/enemies/carrier.tscn",
]


def _config(source: Path, pack_id: str, orientation: str) -> config.GeneratorConfig:
    cfg = config.default_for(
        "Star Run", [config.pack_ref_from_source(source, pack_id)], archetype="shmup"
    )
    cfg.starter_map = {"orientation": orientation}
    return cfg


def _errors(result) -> list[str]:
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value != "info"]


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(folder)
    try:
        yield folder
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


@pytest.fixture(scope="module")
def shooter(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m16_shooter") / "out"
    result = orchestrator.run_in_memory(
        _config(SHOOTER, "shooter", "vertical"), None, target, godot_exe
    )
    assert result.ok, _errors(result)
    return target, result


@pytest.fixture(scope="module")
def plain(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    target = tmp_path_factory.mktemp("m16_plain") / "out"
    result = orchestrator.run_in_memory(
        _config(SAMPLE, "sample_pack", "horizontal"), None, target, godot_exe
    )
    assert result.ok, _errors(result)
    return target, result


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _text(target: Path, rel: str) -> str:
    return (target / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------- the shooter pack


def test_the_shooter_pack_is_a_game_that_scrolls_up(shooter) -> None:
    target, result = shooter
    assert _smoke(target) == STEPS
    for rel in SCENES:
        assert (target / rel).is_file(), rel
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "shmup" and "starter_map" not in saved, "vertical is the default"
    assert {"shoot", "bomb", "focus"} <= set(saved["input"])
    # the pack has everything the kind asks for: nothing was drawn
    assert not [i for i in result.issues if i.code == "ASSET-031"]
    assert not (target / arcade_kit.KIT_DIR).exists()
    stages = jsonio.read(target / "game/data/stages.json")["stages"]
    assert len(stages) == 1
    first = stages[0]
    assert (first["axis"], first["exit"]) == ("up", "reach_end")
    assert first["scene"] == "res://generated/scenes/stages/stage_01.tscn"
    assert first["length"] == 6 * saved["resolution"][1], "six screens along the way it scrolls"


def test_the_scenes_are_made_of_the_packs_own_pictures(shooter) -> None:
    target, _result = shooter
    ship = _text(target, "generated/scenes/shmup/ship.tscn")
    assert "archetypes/shmup/ship.gd" in ship
    assert "sprite_frames/shooter.ships.player_ship.tres" in ship
    assert 'orientation = "vertical"' not in ship, "the default is not written"
    for part in ('name="Visual"', 'name="Body"', 'name="Weapon"', 'name="Bomb"', 'name="Input"'):
        assert part in ship, part
    assert "sprite_frames/shooter.fx.explosion_6frames.tres" in _text(
        target, "generated/scenes/shmup/explosion.tscn"
    )
    stage = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert "archetypes/arcade/stage.gd" in stage and "archetypes/shmup/bullet_pool.gd" in stage
    # both backgrounds of the pack loop behind the stage, and the bullets are the pack's
    assert "backgrounds/space_far.png" in stage and "backgrounds/space_near.png" in stage
    assert stage.count('type="Parallax2D"') == 3, "the backdrop and two layers"
    assert "bullets/bullet.png" in stage and "bullets/laser.png" in stage
    assert "generated/scenes/shmup/ship.tscn" in stage
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "archetypes/shmup/shmup_mode.gd" in mode
    assert 'stages_path = "res://game/data/stages.json"' in mode
    assert 'name="Lives"' not in mode, "the mode makes its lives and its score when it starts"
    assert "archetypes/shmup/ui/shmup_hud.gd" in _text(
        target, "generated/scenes/ui/hud_arcade.tscn"
    )
    new_game = _text(target, "game/data/new_game.tres")
    assert "res://generated/scenes/stages/stage_01.tscn" in new_game


def test_the_project_has_the_shmup_and_the_arcade_framework_and_no_other_kind(shooter) -> None:
    target, _result = shooter
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arcade", "shmup"]
    recipes = target / "generated/builder/recipes"
    assert (recipes / "shmup/stage_recipe.gd").is_file()
    assert (recipes / "arcade/stage_recipes.gd").is_file()
    assert not (recipes / "metroidvania").exists() and not (recipes / "arpg").exists()
    smoke = sorted(p.name for p in (target / "generated/builder/smoke").glob("smoke_steps_*.gd"))
    assert "smoke_steps_shmup.gd" in smoke and "smoke_steps_metroidvania.gd" not in smoke
    # no village and no walking character: neither their maps nor their scenes
    assert not (target / "game/maps/starter_map.tscn").exists()
    assert not (target / "generated/scenes/actors/player.tscn").exists()
    files = ledger.Ledger.load(target / paths.LEDGER).files
    assert files["game/data/stages.json"].owner == "user_seed"
    assert files["generated/scenes/stages/stage_01.tscn"].owner == "generated"
    strings = _text(target, "game/i18n/strings.tsv")
    assert "ARC_GAME_OVER\t" in strings and "SHM_BOMBS\t" in strings
    assert "MV_ABILITY_DASH_NAME" not in strings


def test_a_second_run_changes_nothing(shooter, godot_exe: Path) -> None:
    target, _result = shooter
    kept = {
        rel: (target / rel).read_bytes() for rel in [*SCENES, "game/data/stages.json", paths.LEDGER]
    }
    again = orchestrator.run_in_memory(
        _config(SHOOTER, "shooter", "vertical"), None, target, godot_exe
    )
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


# ---------------------------------------------------------------- a pack with nothing for it


def test_a_plain_rpg_pack_makes_a_game_that_scrolls_right_with_drawn_stand_ins(plain) -> None:
    target, result = plain
    assert _smoke(target) == STEPS
    drawn = {i.detail["role"]: i for i in result.issues if i.code == "ASSET-031"}
    assert sorted(drawn) == ["EXPLOSION", "POWERUP", "PROJECTILE"]
    assert all(i.severity.value == "info" for i in drawn.values())
    assert not [i for i in result.issues if i.severity.value == "error"]
    for name in ("bullet", "explosion", "capsule"):
        assert (target / arcade_kit.KIT_DIR / f"{name}.png").is_file(), name
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["starter_map"] == {"orientation": "horizontal"}
    first = jsonio.read(target / "game/data/stages.json")["stages"][0]
    assert first["axis"] == "right" and first["length"] == 6 * saved["resolution"][0]
    ship = _text(target, "generated/scenes/shmup/ship.tscn")
    assert 'orientation = "horizontal"' in ship
    assert "sprite_frames/sample_pack." in ship, "the hero of the pack is the ship"
    stage = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert "arcade_kit/bullet.png" in stage, "the drawn bullet is in the pool"
    assert "archetypes/shmup/starfield.gd" in stage, "no background in the pack: stars"
    assert "rpggen_arcade_kit.explosion" in _text(target, "generated/scenes/shmup/explosion.tscn")
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert 'orientation = "horizontal"' in mode


# ---------------------------------------------------------------- enemies and waves (T16.05)


def test_the_enemy_pictures_of_the_pack_are_shared_out_over_the_behaviours(shooter) -> None:
    target, _result = shooter
    enemies = target / "generated/scenes/shmup/enemies"
    assert sorted(p.name for p in enemies.glob("*.tscn")) == [
        "asteroid.tscn",
        "carrier.tscn",
        "popcorn_01.tscn",
        "popcorn_02.tscn",
        "popcorn_03.tscn",
        "popcorn_04.tscn",
        "turret.tscn",
    ]
    # five enemy ships of one size: four are the small ones, and none is larger than the others,
    # so the carrier is the first of them, twice as large
    for n in range(1, 5):
        scene = _text(target, f"generated/scenes/shmup/enemies/popcorn_{n:02d}.tscn")
        assert f"enemies/enemy_ship_{n}.png" in scene and "enemies/popcorn.gd" in scene
        assert "rotation" not in scene, "a pack draws its enemy ships as they come: looking down"
    carrier = _text(target, "generated/scenes/shmup/enemies/carrier.tscn")
    assert "enemies/enemy_ship_1.png" in carrier and "scale = Vector2(2, 2)" in carrier
    assert "enemies/popcorn_01.tscn" in carrier and 'drop = "weapon:spread"' in carrier
    assert "asteroids/asteroid_1.png" in _text(
        target, "generated/scenes/shmup/enemies/asteroid.tscn"
    ), "the hazard the pack calls an asteroid"
    turret = _text(target, "generated/scenes/shmup/enemies/turret.tscn")
    assert 'type="Polygon2D"' in turret, "no picture of a turret in the pack: a drawn shape"
    capsule = _text(target, "generated/scenes/shmup/powerup.tscn")
    for n in (1, 2, 3):
        assert f"powerups/capsule_{n}.png" in capsule, "the capsules of the pack, a kind each"


def test_the_first_stage_has_its_waves(shooter) -> None:
    target, _result = shooter
    waves = jsonio.read(target / "game/data/stages.json")["stages"][0]["waves"]
    assert [w["id"] for w in waves] == [f"w{n:02d}" for n in range(1, 11)]
    assert [w["enemy"] for w in waves] == [
        "popcorn", "popcorn", "turret", "popcorn", "asteroid",
        "popcorn", "carrier", "popcorn", "turret", "popcorn",
    ]  # fmt: skip
    assert [w["at"] for w in waves] == sorted(w["at"] for w in waves)
    for wave in waves:
        assert (target / wave["scene"].removeprefix("res://")).is_file(), wave["scene"]
    small = [w for w in waves if w["enemy"] == "popcorn"]
    assert [w["formation"] for w in small] == ["line", "v", "sine", "circle", "column", "v"]
    assert all(w["bonus"] == 500 for w in small)
    assert [w["id"] for w in waves if "drop" in w] == ["w08"], "the fifth formation of small ones"
    assert {w.get("anchor", "screen") for w in waves if w["enemy"] in ("turret", "asteroid")} == {
        "stage"
    }


def test_a_plain_rpg_pack_has_its_monsters_as_enemies_unturned(plain) -> None:
    target, _result = plain
    waves = jsonio.read(target / "game/data/stages.json")["stages"][0]["waves"]
    assert len(waves) == 10
    small = _text(target, "generated/scenes/shmup/enemies/popcorn_01.tscn")
    assert "sample_pack" in small and "rotation" not in small, "a monster is not laid on its side"
    assert 'orientation = "horizontal"' in small
    assert (target / "generated/scenes/shmup/enemies/carrier.tscn").is_file()
    capsule = _text(target, "generated/scenes/shmup/powerup.tscn")
    assert "arcade_kit/capsule.png" in capsule, "the drawn capsule"
