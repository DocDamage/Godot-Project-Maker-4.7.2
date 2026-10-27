"""T16.08: what the Python side knows of the run and gun: its config, its controls, the
side-view kit, its smoke steps, and what is installed for it (the metroidvania's platform code
is borrowed)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen import features, paths, schema
from rpggen.core import (
    archive,
    catalog,
    config,
    inventory,
    options,
    orchestrator,
    requirements,
    side_kit,
    staging,
)

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _cfg(**changes) -> config.GeneratorConfig:
    ref = config.PackRef("platformer", "platformer", "0" * 64, "folder")
    cfg = config.default_for("Hard Corps", [ref], archetype="run_and_gun")
    for key, value in changes.items():
        setattr(cfg, key, value)
    return cfg


def _catalog(source: Path) -> catalog.Catalog:
    opened = archive.open_pack(source, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def test_the_config_of_a_run_and_gun_is_valid_and_keeps_its_options() -> None:
    cfg = _cfg()
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["archetype"] == "run_and_gun" and "starter_map" not in data
    rules = config.starter_map_defaults("run_and_gun")
    assert (rules["health"], rules["lives"], rules["left_edge_kills"], rules["keep_weapon"]) == (
        1,
        3,
        True,
        False,
    ), "one hit is a death, and the left edge kills: the rules of the genre"
    forgiving = _cfg(starter_map={"health": 3, "left_edge_kills": False})
    data = forgiving.to_json()
    schema.validate("config", data)
    # an option that differs writes the whole set, with the defaults of the others (T16.10)
    assert data["starter_map"] == {**rules, "health": 3, "left_edge_kills": False}
    assert config.GeneratorConfig.from_json(data).to_json() == data
    for bad in ({"health": 0}, {"health": 6}, {"left_edge_kills": "no"}):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": bad})
    with pytest.raises(Exception):  # noqa: B017, PT011
        schema.validate("config", {**data, "archetype": "pinball"})
    assert features.RUN_AND_GUN_AVAILABLE is True, "the wizard offers it since the gate of 1.4"
    assert [k for k, on in cfg.features.items() if not on] == [
        "dialogue",
        "navigation",
        "progression",
        "crafting",
    ]
    assert options.stages_text("run_and_gun", {}) == "3 stages, seen from the side"


def test_the_controls_start_from_the_metroidvanias() -> None:
    bindings = config.default_input("run_and_gun")
    side = config.default_input("metroidvania")
    assert bindings["jump"] == side["jump"] and bindings["down"] == side["down"]
    assert bindings["shoot"]["keys"] == ["J", "X"] and bindings["shoot"]["joy_buttons"] == [2]
    assert bindings["grenade"]["keys"] == ["K", "C"] and bindings["grenade"]["joy_buttons"] == [3]
    assert bindings["aim_lock"]["keys"] == ["Shift"]
    assert bindings["aim_lock"]["joy_axes"] == [[4, 1.0]], "the left trigger"
    assert "Space" not in bindings["interact"]["keys"], "Space jumps"
    for action in ("move_up", "move_down", "move_left", "move_right", "menu"):
        assert action in bindings, action
    assert bindings["grapple"]["keys"] == ["L", "V"], "the arm (T16.11)"
    assert not {"dash", "attack", "bomb", "focus"} & set(bindings)
    assert _cfg().input == bindings


def test_a_run_and_gun_is_seen_from_the_side(tmp_path: Path) -> None:
    assert config.SIDE_VIEW_KINDS == ("metroidvania", "run_and_gun")
    # a pack with ground and nothing else of a side view gets the kit's tiles, as a metroidvania does
    pack = tmp_path / "plain"
    (pack / "tiles").mkdir(parents=True)
    Image.new("RGBA", (64, 64), (90, 120, 70, 255)).save(pack / "tiles" / "ground.png")
    cat = _catalog(pack)
    cfg = _cfg()
    _issues, stand_ins = orchestrator.add_run_made_assets(cat, cfg, [], tmp_path / "staging")
    assert stand_ins, "the side-view kit was drawn"
    assert [a for a in cat.assets if a.pack_id == side_kit.KIT_PACK]
    assert [a for a in cat.assets if a.pack_id == "rpggen_arcade_kit"], "and the arcade stand-ins"
    schema.validate("catalog", cat.to_json())
    # what it needs of the packs: a player and ground; a hero without a jump is a note
    side = _catalog(SYNTH / "platformer")
    issues = requirements.check(side, _cfg())
    assert not [i for i in issues if i.severity.value == "error"]
    assert {i.detail["role"] for i in issues if i.code == "ASSET-031"} == {
        "PROJECTILE",
        "EXPLOSION",
        "POWERUP",
    }
    top_down = _catalog(SYNTH / "basic16")
    notes = [i for i in requirements.check(top_down, _cfg()) if i.code == "ASSET-030"]
    assert len(notes) == 1, "a top-down hero has no jump animation: the idle frame is shown"


def test_the_smoke_steps_and_the_installed_files_of_a_run_and_gun(tmp_path: Path) -> None:
    own = orchestrator.smoke_steps_for("run_and_gun")
    assert own.endswith("smoke_steps_run_and_gun.gd") and "," not in own
    templates = paths.templates_root()
    written = staging.install_templates(
        staging.create_staging(tmp_path / "s"), templates, "run_and_gun"
    )
    folders = {w.split("/")[3] for w in written if w.startswith("addons/rpg_runtime/archetypes/")}
    assert folders == {"arcade", "metroidvania", "run_and_gun"}, "the platform actor is borrowed"
    recipes = {
        w.split("/")[3]
        for w in written
        if w.startswith("generated/builder/recipes/") and w.count("/") > 3
    }
    assert recipes == {"arcade", "metroidvania", "run_and_gun"}
    assert "addons/rpg_runtime/archetypes/metroidvania/platform_actor.gd" in written
    assert "addons/rpg_runtime/archetypes/arcade/bullet_pool.gd" in written
    smoke = {w.rsplit("/", 1)[-1] for w in written if "/smoke/smoke_steps_" in w}
    assert "smoke_steps_run_and_gun.gd" in smoke
    assert not {"smoke_steps_metroidvania.gd", "smoke_steps_shmup.gd"} & smoke
    for other in ("turn_based", "arpg", "metroidvania", "shmup"):
        got = staging.install_templates(staging.create_staging(tmp_path / other), templates, other)
        assert not [w for w in got if "run_and_gun" in w], other
    # the bullet pool and the explosion are the arcade kinds' now, not the shoot 'em up's
    shmup = staging.install_templates(staging.create_staging(tmp_path / "s2"), templates, "shmup")
    assert "addons/rpg_runtime/archetypes/arcade/bullet_pool.gd" in shmup
    assert not [w for w in shmup if w.endswith("shmup/bullet_pool.gd")]
    assert not [w for w in shmup if "archetypes/metroidvania/" in w]


def test_the_soldier_of_a_side_view_pack_is_its_player_and_a_tag_is_no_bullet() -> None:
    """T16.09: the `gunner` pack calls its hero a soldier, which made it an NPC and left the
    pack without a player; and its weapon pickups are tagged `bullet` and `powerup`, which made
    the arcade kit think the pack had bullets while no asset had the role."""
    from rpggen.core import arcade_kit

    cat = _catalog(SYNTH / "gunner")
    roles = {a.id: catalog.effective(a)["role"] for a in cat.assets}
    assert roles["gunner.soldier.soldier_idle"] == "PLAYER"
    assert [r for r in roles.values() if r == "PLAYER"] == ["PLAYER"], "one player"
    assert roles["gunner.enemies.trooper_walk"] == "ENEMY", "the other soldiers stay enemies"
    lacking = {s.role for s in arcade_kit.lacking(cat, "run_and_gun")}
    assert {"PROJECTILE", "POWERUP", "EXPLOSION"} <= lacking, "a tag alone is not the role"
    issues = requirements.check(cat, _cfg())
    assert not [i for i in issues if i.severity.value == "error"]
    assert not [i for i in issues if i.code == "ASSET-010" and i.detail["role"] == "PROJECTILE"], (
        "what the kit draws is a note, not a missing role"
    )
    # a pack that has a player keeps it: nobody is promoted beside it
    side = _catalog(SYNTH / "platformer")
    assert sum(1 for a in side.assets if catalog.effective(a).get("role") == "PLAYER") == 1
    assert config.starter_map_defaults("run_and_gun")["keep_weapon"] is False
