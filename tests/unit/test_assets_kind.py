"""The kind `assets` (T17.33): a project of the packs' assets and no game, for levels built by
hand. Its config, the view decided from the packs, what it requires, what it installs and its
README; the build itself is tests/integration/test_t17_33_assets_only.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import paths, schema
from rpggen.core import archive, catalog, config, inventory, orchestrator, requirements, staging

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(pack: Path) -> catalog.Catalog:
    opened = archive.open_pack(pack, set())
    cat, _issues, _gen = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    return cat


def _cfg(pack: Path) -> config.GeneratorConfig:
    return orchestrator.default_config_for_pack(pack, "Assets", archetype="assets")


def test_its_config_has_the_editor_tools_and_nothing_of_a_game() -> None:
    cfg = _cfg(SYNTH / "basic16")
    assert cfg.features["editor_tools"] and cfg.features["tilesets"]
    assert not cfg.features["combat"] and not cfg.features["demo"]
    assert cfg.starter_map_options() == {}, "no maps"
    assert cfg.view == "" and "view" not in cfg.to_json(), "decided from the packs"
    cfg.view = "side"
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["view"] == "side" and config.GeneratorConfig.from_json(data).view == "side"
    assert config.side_view("assets", "side") and not config.side_view("assets", "top")
    assert config.side_view("metroidvania") and not config.side_view("farm", "side")


def test_its_view_is_what_the_packs_are_drawn_as() -> None:
    side = _cfg(SYNTH / "side_named_platformer")
    orchestrator.decide_view(side, _catalog(SYNTH / "side_named_platformer"))
    assert side.view == "side" and "jump" in side.input, "the side-view body's input"
    top = _cfg(SYNTH / "basic16")
    orchestrator.decide_view(top, _catalog(SYNTH / "basic16"))
    assert top.view == "top" and "jump" not in top.input
    iso = _cfg(SYNTH / "iso_tiles")
    orchestrator.decide_view(iso, _catalog(SYNTH / "iso_tiles"))
    assert iso.projection == "isometric" and orchestrator.assets_view(iso) == "isometric"


def test_nothing_is_missing_from_a_project_of_what_the_packs_hold() -> None:
    cat = _catalog(SYNTH / "sheet_things")  # no player, no music
    issues = requirements.check(cat, _cfg(SYNTH / "sheet_things"))
    codes = {i.code for i in issues}
    assert not codes & {"ASSET-010", "ASSET-026", "ASSET-027", "ASSET-014"}, codes
    assert requirements.REQUIRED["assets"] == [] and requirements.recommended("assets") == []


def test_it_installs_the_enemies_and_bodies_of_both_views_and_no_game(tmp_path: Path) -> None:
    stg = staging.create_staging(tmp_path / "out")
    written = staging.install_templates(stg, paths.templates_root(), "assets")
    for wanted in (
        "generated/builder/recipes/arpg/enemy_recipes.gd",
        "generated/builder/recipes/metroidvania/enemy_recipes.gd",
        "generated/builder/recipes/metroidvania/player_recipe.gd",
    ):
        assert wanted in written, wanted
    assert any(w.startswith("addons/rpg_runtime/archetypes/metroidvania/") for w in written)
    assert not [w for w in written if "/recipes/farm/" in w or "smoke_steps_farm" in w]


def test_its_readme_says_how_to_build_a_level() -> None:
    cfg = _cfg(SYNTH / "basic16")
    files = paths.templates_root() / "project_files"
    text = staging.render_readme(
        (files / staging.README_ASSETS_TEMPLATE).read_text(encoding="utf-8"), cfg, "1.0"
    )
    assert "There is no game in it" in text
    for said in ("## 2. A level", "Terrains", "RPG Project Tools", "YSorted"):
        assert said in text, said
    assert "{" not in text.replace("{{", ""), "every placeholder filled"
