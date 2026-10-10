"""T14.02: side-view detection: the tags, the two collision values, parallax depth, the pack's
point of view and the roles of the metroidvania."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, classifier, config, inventory, mapping, requirements
from rpggen.core.catalog import Asset, Catalog, CatalogPack

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
GOLDEN = REPO / "tests" / "golden"

TAG_CASES = [
    ("tiles/platforms/stone.png", ["platform"]),
    ("tiles/ledge_left.png", ["platform"]),
    ("tiles/platforms/oneway_planks.png", ["one_way"]),
    ("tiles/one_way_bridge.png", ["one_way"]),
    ("tiles/semi_solid.png", ["one_way"]),
    ("tiles/thin platform.png", ["one_way"]),
    ("tiles/ladders/wood.png", ["ladder"]),
    ("Tiles/Rope.png", ["ladder"]),
    ("props/vine_long.png", ["ladder"]),
    ("tiles/hazards/spikes.png", ["hazard"]),
    ("tiles/lava.png", ["hazard"]),
    ("traps/saw.png", ["hazard"]),
    ("tiles/thorn_bush.png", ["hazard"]),
    ("objects/save_bench.png", ["save_point"]),
    ("objects/checkpoint.png", ["save_point"]),
    ("items/powerup_orb_1.png", ["ability"]),
    ("items/power_up.png", ["ability"]),
    ("pickups/upgrade.png", ["ability"]),
    ("items/AbilityOrb.png", ["ability"]),
    ("backgrounds/bg_far.png", ["parallax:1"]),
    ("backgrounds/bg_mid.png", ["parallax:2"]),
    ("backgrounds/bg_near.png", ["parallax:3"]),
    ("backgrounds/background_1.png", ["parallax:1"]),
    ("art/layer2.png", ["parallax:2"]),
    ("parallax/Layer 4.png", ["parallax:4"]),
    # names that say nothing about a side view
    ("backgrounds/sky.png", []),
    ("backgrounds/title.png", []),
    ("tiles/terrain.png", []),
    ("characters/hero.png", []),
    ("tiles/sawmill_far_away.png", []),
    ("items/item_01.png", []),
    ("near/far/tree.png", []),
]


@pytest.mark.parametrize(("path", "tags"), TAG_CASES, ids=[c[0] for c in TAG_CASES])
def test_side_view_tags(path: str, tags: list[str]) -> None:
    assert classifier.side_view_tags(path) == tags


def test_an_object_name_gets_the_tags_too() -> None:
    assert classifier.side_view_tags("Save Bench") == ["save_point"]
    assert classifier.side_view_tags("House (red)") == []


def test_parallax_depth() -> None:
    assert classifier.parallax_depth("backgrounds/bg_far.png") == 1
    assert classifier.parallax_depth("bg/mountains_mid.png") == 2
    assert classifier.parallax_depth("background_3.png") == 3
    assert classifier.parallax_depth("layer12.png") is None, "more than nine layers is not a depth"
    assert classifier.parallax_depth("far.png") is None, "not named as a background"


def _inv(*paths: str) -> SimpleNamespace:
    return SimpleNamespace(files=[SimpleNamespace(path=p) for p in paths])


SIDE_HERO = {"animations": {"idle_down": {}, "walk_down": {}, "jump_down": {}, "fall_down": {}}}
TOP_HERO = {"animations": {"walk_down": {}, "walk_up": {}, "walk_left": {}, "walk_right": {}}}


def test_pack_view_from_words() -> None:
    assert classifier.pack_view(_inv("Platformer Pack/tiles/ground.png")) == "side"
    assert classifier.pack_view(_inv("sidescroller/hero.png")) == "side"
    assert classifier.pack_view(_inv("Metroidvania_Tileset/cave.png")) == "side"
    assert classifier.pack_view(_inv("side_scroller/a.png")) == "side"
    assert classifier.pack_view(_inv("sprites/hero_jump.png")) == "side"
    assert classifier.pack_view(_inv("RPG/overworld.png")) == "top"
    assert classifier.pack_view(_inv("top-down/tiles.png")) == "top"
    assert classifier.pack_view(_inv("tiles/terrain.png", "characters/hero.png")) == "top"


def test_pack_view_counts_a_word_once_and_weighs_both_sides() -> None:
    files = [f"platformer/tile_{i}.png" for i in range(20)]
    assert classifier.pack_view(_inv(*files, "rpg/a.png", "topdown/b.png")) == "top"
    assert classifier.pack_view(_inv("platformer/a.png", "rpg/b.png")) == "top", "a tie is top-down"


def test_pack_view_from_character_sheets() -> None:
    assert classifier.pack_view(_inv("hero.png"), [SIDE_HERO]) == "side"
    assert classifier.pack_view(_inv("hero.png"), [TOP_HERO]) == "top"
    jumps_and_walks_up = {"animations": {**SIDE_HERO["animations"], "walk_up": {}}}
    assert classifier.pack_view(_inv("hero.png"), [jumps_and_walks_up]) == "top"
    assert classifier.pack_view(_inv("rpg/hero.png"), [SIDE_HERO]) == "side", "a sheet weighs 2"
    assert classifier.pack_view(_inv("hero.png"), [{"usage": "tiles"}, {}]) == "top"


# --------------------------------------------------------------------------- the catalog


@pytest.fixture(scope="module")
def platformer(tmp_path_factory: pytest.TempPathFactory) -> Catalog:
    import os

    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(tmp_path_factory.mktemp("cache"))
    try:
        opened = archive.open_pack(SYNTH / "platformer", set(), pack_id="platformer")
        cat, _issues, _generated = catalog.assemble(
            [(opened, inventory.build_inventory(opened))], None, []
        )
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old
    return cat


def _asset(cat: Catalog, name: str) -> Asset:
    found = cat.asset(f"platformer.{name}")
    assert found is not None, name
    return found


def test_the_platformer_pack_is_side_view(platformer: Catalog) -> None:
    pack = platformer.packs[0]
    assert catalog.VIEW_SIDE in pack.warnings
    assert catalog.pack_view(pack) == "side"
    assert catalog.pack_view(CatalogPack("p", "0" * 64, "assets/packs/p")) == "top"


def test_platforms_ladders_and_spikes_are_tile_sheets(platformer: Catalog) -> None:
    planks = _asset(platformer, "tiles.platforms.oneway_planks").detected
    ladder = _asset(platformer, "tiles.ladders.ladder").detected
    spikes = _asset(platformer, "tiles.hazards.spikes").detected
    for facets, tag in ((planks, "one_way"), (ladder, "ladder"), (spikes, "hazard")):
        assert facets["usage"] == "tiles" and facets["grid"]["cell"] == [16, 16]
        assert facets["role"] == "DECORATION", "never the ground of a map"
        assert tag in facets["tags"] and "frame" not in facets
        assert facets["tileset"] == "overworld"
    assert planks["collision"] == {"profile": "ONE_WAY"}
    assert ladder["collision"] == {"profile": "LADDER"}
    assert "collision" not in spikes
    assert mapping.best_for(platformer, "GROUND") == "platformer.tiles.ground"


def test_parallax_layers_are_backgrounds(platformer: Catalog) -> None:
    for depth, name in ((1, "far"), (2, "mid"), (3, "near")):
        facets = _asset(platformer, f"backgrounds.bg_{name}").detected
        assert facets["usage"] == "background" and facets["role"] == "BACKGROUND"
        assert facets["tags"] == [f"parallax:{depth}"]
        assert "frame" not in facets and "origin" not in facets


def test_the_hero_is_one_side_view_sheet(platformer: Catalog) -> None:
    hero = _asset(platformer, "characters.hero_attack").detected
    assert hero["role"] == "PLAYER" and hero["frame"] == [24, 24]
    assert sorted(hero["animations"]) == [
        "attack_down", "climb_down", "dash_down", "fall_down", "idle_down", "jump_down",
        "walk_down",
    ]  # fmt: skip
    assert _asset(platformer, "boss.guardian_attack").detected["role"] == "BOSS"
    assert _asset(platformer, "objects.save_bench").detected["tags"] == ["save_point"]
    assert _asset(platformer, "items.powerup_orb_1").detected["tags"] == ["ability"]


def test_the_platformer_golden(platformer: Catalog) -> None:
    golden = json.loads((GOLDEN / "platformer.catalog.json").read_text(encoding="utf-8"))
    assert platformer.to_json()["assets"] == golden["assets"]
    assert platformer.to_json()["packs"][0]["warnings"] == golden["packs"][0]["warnings"]


def test_no_top_down_golden_has_a_side_view_tag_or_view() -> None:
    names = {"platform", "one_way", "ladder", "hazard", "save_point", "ability"}
    for path in sorted(GOLDEN.glob("*.catalog.json")):
        # the side-view packs, and the shooter, whose backgrounds are layers that scroll (M16)
        if path.stem.split(".")[0] in ("platformer", "sample_pack_side", "gunner", "shooter"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for pack in data["packs"]:
            assert catalog.VIEW_SIDE not in pack["warnings"], path.name
        for asset in data["assets"]:
            tags = set(asset["detected"].get("tags") or [])
            assert not tags & names, (path.name, asset["id"])
            assert not any(t.startswith("parallax:") for t in tags), (path.name, asset["id"])


def test_side_view_usage_leaves_other_assets_alone() -> None:
    def make(ident: str, by: str, **facets: object) -> Asset:
        return Asset(ident, "p", f"assets/packs/p/{ident}.png", "0" * 64, "image", "AUTO_DETECTED",
                     dict(facets), {}, by, 0.5)  # fmt: skip

    grid = {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}
    ground = make("tiles/ground", "generic_grid", usage="tiles", grid=grid, role="GROUND")
    adapter_ladder = make(
        "tiles/ladder_a", "tiled", usage="sprite", tags=["ladder"], size=[16, 48], role="GROUND"
    )
    odd_size = make(
        "tiles/ladder_b", "generic_grid", usage="sprite", tags=["ladder"], size=[20, 48], role="GROUND"
    )  # fmt: skip
    not_in_tiles = make(
        "props/ladder_c", "generic_grid", usage="sprite", tags=["ladder"], size=[16, 48], role="DECORATION"
    )  # fmt: skip
    animated = make(
        "tiles/spikes", "generic_grid", usage="sprite", tags=["hazard"], size=[32, 16],
        animations={"idle_down": {}}, role="GROUND",
    )  # fmt: skip
    title = make("bg/title", "generic_grid", usage="sprite", role="BACKGROUND", size=[320, 180])
    assets = [ground, adapter_ladder, odd_size, not_in_tiles, animated, title]
    before = copy.deepcopy([a.detected for a in assets])
    catalog._side_view_usage(assets)
    assert [a.detected for a in assets] == before


def test_side_view_usage_needs_a_tile_size() -> None:
    ladder = Asset("tiles/ladder", "p", "assets/packs/p/tiles/ladder.png", "0" * 64, "image",
                   "AUTO_DETECTED", {"usage": "sprite", "tags": ["ladder"], "size": [16, 48]}, {},
                   "generic_grid", 0.5)  # fmt: skip
    catalog._side_view_usage([ladder])
    assert ladder.detected["usage"] == "sprite"


# --------------------------------------------------------------------------- schema


@pytest.mark.parametrize("profile", ["ONE_WAY", "LADDER"])
def test_the_side_view_collision_values_validate_and_round_trip(
    platformer: Catalog, profile: str, tmp_path: Path
) -> None:
    cat = Catalog.from_json(platformer.to_json())
    ground = cat.asset("platformer.tiles.ground")
    assert ground is not None
    ground.overrides["collision"] = {"profile": profile}
    ground.overrides["tile_overrides"] = {"1,0": {"collision": {"profile": profile}}}
    path = tmp_path / "asset_catalog.json"
    catalog.save(cat, path)
    again = catalog.load(path)
    kept = again.asset("platformer.tiles.ground")
    assert kept is not None
    assert catalog.effective(kept)["collision"] == {"profile": profile}
    assert kept.overrides["tile_overrides"]["1,0"]["collision"] == {"profile": profile}


def test_the_profile_schemas_know_the_values() -> None:
    for path in (
        REPO / "rpggen/schema/profile.schema.json",
        REPO / "registry/scripts/profile.schema.json",
        REPO / "rpggen/schema/catalog.schema.json",
    ):
        profiles = jsonio.read(path)["$defs"]["CollisionSpec"]["properties"]["profile"]["enum"]
        assert profiles[-2:] == ["ONE_WAY", "LADDER"], path
        assert profiles.index("CUSTOM") == 8, "the 1.1 values keep their order"


# --------------------------------------------------------------------------- roles


def test_the_metroidvania_roles() -> None:
    assert requirements.REQUIRED["metroidvania"] == ["PLAYER", "GROUND"]
    assert requirements.recommended("metroidvania") == [
        "BACKGROUND", "DECORATION", "ENEMY", "BOSS", "ITEM", "NPC", "UI", "PORTRAIT",
    ]  # fmt: skip
    assert requirements.recommended("turn_based") is requirements.RECOMMENDED
    assert requirements.recommended("arpg") is requirements.RECOMMENDED
    assert requirements.recommended("something else") is requirements.RECOMMENDED
    assert requirements.required_by("GROUND", "metroidvania") == (
        "the floors and walls of every room"
    )
    assert requirements.required_by("GROUND", "arpg") == "the starter map"
    assert requirements.required_by("GROUND") == "the starter map"
    assert requirements.required_by("UI", "metroidvania") == "menus"
    assert mapping.used_for("BOSS", "metroidvania") == "the guardian"
    assert mapping.used_for("PLAYER") == "the player actor"


def test_the_mapping_rows_of_each_archetype() -> None:
    top = [(r.role, r.required, r.key) for r in mapping.rows("turn_based")]
    assert top == [(r.role, r.required, r.key) for r in mapping.rows("arpg")]
    assert [r[0] for r in top] == [
        "PLAYER", "GROUND", "NPC", "ENEMY", "BUILDING", "WALL", "ITEM", "UI", "PORTRAIT",
    ]  # fmt: skip
    side = {r.role: (r.required, r.key) for r in mapping.rows("metroidvania")}
    assert list(side) == [
        "PLAYER", "GROUND", "BACKGROUND", "DECORATION", "ENEMY", "BOSS", "ITEM", "NPC", "UI",
        "PORTRAIT",
    ]  # fmt: skip
    assert side["PLAYER"] == (True, "player") and side["GROUND"] == (True, "ground")
    assert side["BOSS"] == (False, "boss") and side["BACKGROUND"] == (False, None)


def test_the_platformer_fills_the_metroidvania_and_its_starter(platformer: Catalog) -> None:
    cfg = config.default_for("Side", [], archetype="metroidvania")
    errors = [i for i in requirements.check(platformer, cfg) if i.severity.value == "error"]
    assert errors == []
    missing = [
        i.detail["role"] for i in requirements.check(platformer, cfg) if i.code == "ASSET-010"
    ]
    assert missing == ["UI", "PORTRAIT"], "the synthetic pack has no panel and no face"
    starter = mapping.default_starter(platformer, "metroidvania")
    assert starter == {
        "player": "platformer.characters.hero_attack",
        "ground": "platformer.tiles.ground",
        "enemy": "platformer.enemies.bat_idle",
        "boss": "platformer.boss.guardian_attack",
        "chest": "platformer.items.powerup_orb_1",
        "npc": "platformer.npc.villager_idle",
    }
    assert "boss" not in mapping.default_starter(platformer, "turn_based")


# --------------------------------------------------------------------------- T14.03


def test_a_player_without_jump_or_fall_is_reported_for_a_metroidvania_only(
    platformer: Catalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    opened = archive.open_pack(SYNTH / "basic16", set(), pack_id="basic16")
    top_down, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    side = config.default_for("Side", [], archetype="metroidvania")
    found = [i for i in requirements.check(top_down, side) if i.code == "ASSET-030"]
    assert len(found) == 1 and found[0].severity.value == "info"
    assert found[0].detail == {"asset": "basic16.characters.hero", "missing": "jump or fall"}
    for archetype in ("turn_based", "arpg"):
        cfg = config.default_for("Top", [], archetype=archetype)
        assert "ASSET-030" not in [i.code for i in requirements.check(top_down, cfg)]
    assert "ASSET-030" not in [i.code for i in requirements.check(platformer, side)]
    hero = platformer.asset("platformer.characters.hero_attack")
    assert requirements.missing_air_animations(hero) == []
    assert requirements.missing_air_animations(None) == []


def test_the_metroidvania_input_adds_four_actions_and_moves_interact_off_space() -> None:
    top = config.default_input("turn_based")
    side = config.default_input("metroidvania")
    assert set(side) - set(top) == {"jump", "dash", "attack", "down"}
    assert "Space" in side["jump"]["keys"] and "Space" not in side["interact"]["keys"]
    assert side["confirm"] == top["confirm"] and side["move_left"] == top["move_left"]
    assert config.default_input("turn_based") == top, "the top-down bindings are those of 1.1"
    assert "jump" not in config.default_input("arpg")
    cfg = config.default_for("Side", [], archetype="metroidvania")
    assert config.GeneratorConfig.from_json(cfg.to_json()).input == side
