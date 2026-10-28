"""T17.15: the isometric race, the Python side. The view is made (the config no longer refuses
it), a race gets a car and no drawn people, a top-down car is used on diamonds while the
isometric one is not used from above, and the numbers the track recipe shares with the plan."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rpggen.core import (
    arcade_kit,
    archive,
    catalog,
    config,
    inventory,
    iso_atlas,
    orchestrator,
    requirements,
    track_plan,
)

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
RACING = REPO / "godot_templates/builder/recipes/racing"
RUNTIME = REPO / "godot_templates/addons/rpg_runtime/archetypes/racing"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(sources: list[Path]) -> catalog.Catalog:
    packs = []
    for source in sources:
        opened = archive.open_pack(source, {p[0].pack_id for p in packs})
        packs.append((opened, inventory.build_inventory(opened)))
    cat, _issues, _generated = catalog.assemble(packs, None, [], use_cache=False)
    return cat


def _cfg(archetype: str, projection: str = "isometric") -> config.GeneratorConfig:
    pack = config.PackRef("iso_tiles", str(SYNTH / "iso_tiles"), "0" * 64, "folder")
    cfg = config.default_for("x", [pack], archetype=archetype)
    cfg.projection = projection
    return cfg


def test_the_isometric_race_is_made(tmp_path: Path) -> None:
    assert "racing" in config.ISOMETRIC_KINDS and "racing" not in config.ISOMETRIC_NOT_YET
    cfg = _cfg("racing")
    config.save(cfg, tmp_path / "cfg.json")
    loaded = config.load(tmp_path / "cfg.json")
    assert (loaded.archetype, loaded.projection) == ("racing", "isometric")
    # the options of a race are those of a race seen from above: the plan knows no view
    assert loaded.starter_map_options() == _cfg("racing", "top_down").starter_map_options()
    assert track_plan.plan(loaded.starter_map_options(), 7) == track_plan.plan(
        _cfg("racing", "top_down").starter_map_options(), 7
    )


def test_an_isometric_race_has_a_car_and_no_drawn_people(tmp_path: Path) -> None:
    from rpggen.core import iso_kit

    # the car of the one pack on the ground of the other: nothing is drawn
    cat = _assemble([SYNTH / "iso_tiles", SYNTH / "iso_miniature"])
    car = next(a for a in cat.assets if catalog.effective(a).get("role") == "VEHICLE")
    facets = catalog.effective(car)
    assert (facets["headings"], facets["heading_order"]) == (8, "up_cw")
    assert [Path(f).stem for f in facets["heading_files"]] == [
        f"car_{letter}" for letter in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    ], "N is up on the screen, then clockwise: the order RpgHeadingSprite counts in"
    cfg = _cfg("racing")
    notes = requirements.check(cat, cfg)
    assert not [i for i in notes if i.code == "ASSET-031"], "neither a car nor people"
    assert not [i for i in notes if i.severity.value == "error"]
    orchestrator.add_run_made_assets(cat, cfg, [], tmp_path)
    assert not [a for a in cat.assets if a.pack_id in (iso_kit.KIT_PACK, arcade_kit.KIT_PACK)]
    assert not (tmp_path / iso_kit.KIT_DIR).exists()
    assert iso_atlas.existing_def(cat) is not None, "the ground is the tile set of diamonds"
    # ... while a game with people on the same packs gets them drawn, as before
    people = requirements.check(_assemble([SYNTH / "iso_tiles"]), _cfg("turn_based"))
    assert sorted(i.detail["thing"] for i in people if i.code == "ASSET-031") == [
        "enemy",
        "hero",
        "villager",
    ]


def test_a_pack_without_a_car_races_the_drawn_one_on_diamonds(tmp_path: Path) -> None:
    cat = _assemble([SYNTH / "iso_tiles"])
    cfg = _cfg("racing")
    assert [s.name for s in arcade_kit.lacking(cat, "racing", "isometric")] == ["car"], (
        "the car is drawn; the ground is the pack's, and no road is drawn for this view"
    )
    notes = requirements.check(cat, cfg)
    assert [i.detail["thing"] for i in notes if i.code == "ASSET-031"] == [
        "car in sixteen headings"
    ]
    orchestrator.add_run_made_assets(cat, cfg, [], tmp_path)
    drawn = cat.asset("rpggen_arcade_kit.car")
    assert drawn is not None and cat.asset("rpggen_arcade_kit.road") is None
    # the car is drawn at the view's angle since T18.19, and as a picture of the isometric view
    # it is not used from above (catalog.fits_projection)
    assert catalog.fits_projection(drawn, "isometric") and not catalog.fits_projection(drawn)
    assert catalog.effective(drawn)["projection"] == "isometric"
    assert catalog.effective(drawn)["headings"] == 16


def _const(text: str, name: str) -> str:
    found = re.search(rf"^const {name} := (.+)$", text, re.M)
    assert found, name
    return found.group(1).strip()


def test_the_recipe_counts_the_plan_as_the_planner_does() -> None:
    build = (RACING / "racing_build.gd").read_text(encoding="utf-8")
    assert int(_const(build, "BLOCK")) == track_plan.BLOCK
    assert int(_const(build, "BORDER")) == track_plan.BORDER
    # a car of the plan is at most CAR tiles wide: its picture is to be about that long
    assert track_plan.CAR <= float(_const(build, "CAR_TILES")) <= track_plan.ROAD / 2
    # the view is a node of the runtime the recipe names by its path
    assert _const(build, "VIEW_SCRIPT") == 'DIR + "race_view.gd"'
    assert (RUNTIME / "race_view.gd").is_file()
    view = (RUNTIME / "race_view.gd").read_text(encoding="utf-8")
    assert "class_name RpgRaceView" in view and 'const NODE := "View"' in view


def test_the_physics_does_not_name_the_view() -> None:
    # the arithmetic of a car and what a race counts with are the plan's: neither file knows
    # that a track can be seen at an angle (the car's picture and the camera do)
    for name in ("car_physics.gd", "race.gd", "rival.gd", "checkpoint.gd", "track_surfaces.gd"):
        text = (RUNTIME / name).read_text(encoding="utf-8")
        assert "RpgRaceView" not in text and "RpgIso" not in text, name
    for name in ("car.gd", "race_camera.gd", "pickup.gd", "weapon.gd"):
        assert "RpgRaceView" in (RUNTIME / name).read_text(encoding="utf-8"), name
    from rpggen.core import car_math

    source = Path(car_math.__file__).read_text(encoding="utf-8")
    assert "iso" not in source.lower().replace("isolat", ""), "car_math knows no view"
