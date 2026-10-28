"""T17.14, the farm in the isometric view, the Python side: the kind is no longer refused, the
facts its planner is given are the view's (an isometric building stands on the cells its picture
says, an isometric water tile makes a pond), the plan itself is the grid of cells it always
was, and the drawn farm kit is as large as a step on the diamonds and leaves out what lies flat
on squares."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import (
    archive,
    catalog,
    config,
    farm_kit,
    farm_plan,
    inventory,
    iso_math,
    orchestrator,
    requirements,
)

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
PACK = config.PackRef("iso_tiles", str(SYNTH / "iso_tiles"), "0" * 64, "folder")
FOOT = (60, 34)
WATER_TILE = "iso_tiles.png.isotile_007_"
FLAT = ("soil", "watered", "shipping_bin", "bed")


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble() -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / "iso_tiles", set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _cfg(projection: str = "isometric") -> config.GeneratorConfig:
    cfg = config.default_for("x", [PACK], archetype="farm")
    cfg.projection = projection
    return cfg


def test_an_isometric_farm_is_not_refused(tmp_path: Path) -> None:
    assert "farm" in config.ISOMETRIC_KINDS and "farm" not in config.ISOMETRIC_NOT_YET
    cfg = _cfg()
    config.check_projection({"projection": cfg.projection, "archetype": cfg.archetype})
    config.save(cfg, tmp_path / "cfg.json")
    loaded = config.load(tmp_path / "cfg.json")
    assert loaded.projection == "isometric" and loaded.archetype == "farm"
    cfg.iso_controls = "grid"
    assert cfg.to_json()["iso_controls"] == "grid"


def test_the_facts_of_the_plan_are_the_views() -> None:
    cat = _assemble()
    facts = orchestrator.farm_facts(_cfg(), cat)
    # the pack's house is drawn on one diamond, its door before the middle of its south side
    assert facts == {
        "water": False,
        "house": {"size": [1, 1], "door": [0, 1]},
        "animal_houses": [],  # the houses of the packs' animals (T18.05): it has none
        "workbench": True,  # a new farm crafts (T18.15)
    }
    # seen from above the same pack has no building at all (its house is no sheet object):
    # the planner takes its own footprint, as it always did
    assert orchestrator.farm_facts(_cfg("top_down"), cat) == {
        "water": False,
        "animal_houses": [],
        "workbench": True,
    }
    # water: an isometric tile with the role makes a pond
    for asset in cat.assets:
        if asset.id.startswith(WATER_TILE):
            asset.overrides = {"role": "WATER"}
    assert orchestrator.farm_facts(_cfg(), cat)["water"] is True
    # a building tagged as a coop is the coop's, and no longer the house's while another is there
    houses = [a for a in cat.assets if catalog.effective(a).get("role") == "BUILDING"]
    assert len(houses) >= 2
    houses[1].overrides = {"tags": ["coop"], "stands_on": [3, 2]}
    facts = orchestrator.farm_facts(_cfg(), cat)
    assert facts["coop"] == {"size": [3, 2], "door": [1, 2]}
    assert facts["house"] == {"size": [1, 1], "door": [0, 1]}
    assert "barn" not in facts
    # and so it is when the starter names the house, which the wizard always does (T17.18: the
    # chosen building was then the only one the facts saw, and the coop was drawn)
    cfg = _cfg()
    cfg.starter = {"building": houses[0].id}
    assert orchestrator.farm_facts(cfg, cat) == facts
    cfg.starter = {"building": houses[1].id}
    chosen = orchestrator.farm_facts(cfg, cat)
    assert chosen["house"] == chosen["coop"] == {"size": [3, 2], "door": [1, 2]}


def test_the_plan_is_the_same_grid_of_cells() -> None:
    cat = _assemble()
    cfg = _cfg()
    options = {**cfg.starter_map_options(), "animals": "coop"}
    facts = orchestrator.farm_facts(cfg, cat)
    section = farm_plan.plan(options, cfg.seed, facts)
    assert farm_plan.check(section) == []
    assert section == farm_plan.plan(options, cfg.seed, facts), "the same every time"
    # nothing in it says how it is seen: cells, and only cells
    assert "projection" not in section and "footprint" not in section
    x, y, wide, high = section["house"]["rect"]
    # the planner gives no building less than two cells each way: the pack's house of one cell
    # stands in the last row of that footprint, over the door (farm_map_recipe.gd)
    assert (wide, high) == (2, 2)
    assert section["house"]["door"] == [x, y + high]
    assert section["water"]["kind"] == "well", "the pack has no water tile"
    assert len(section["tillable"]) >= farm_plan.MIN_PLOT
    assert [h["kind"] for h in section["animal_houses"]] == ["coop"]


def test_the_drawn_kit_is_as_large_as_a_step_on_the_diamonds(tmp_path: Path) -> None:
    cat = _assemble()
    cfg = _cfg()
    unit = iso_math.unit(*FOOT)
    assert orchestrator.farm_kit_tile(cat, cfg) == unit == 34
    assert orchestrator.farm_kit_tile(cat, _cfg("top_down")) == cfg.base_tile_size
    # what lies flat on squares is not drawn for diamonds: the recipes draw it on them
    assert frozenset(FLAT) == farm_kit.NOT_ISOMETRIC
    flat = [s.name for s in farm_kit.lacking(cat)]
    iso = [s.name for s in farm_kit.lacking(cat, "isometric")]
    assert set(FLAT) <= set(flat) and not set(FLAT) & set(iso)
    assert [name for name in flat if name not in FLAT] == iso, "everything else, in its order"
    names, notes = farm_kit.add(cat, unit, tmp_path, "isometric")
    assert names == iso and [n.code for n in notes] == ["ASSET-031"] * len(iso)
    kit = [a for a in cat.assets if a.pack_id == farm_kit.KIT_PACK]
    assert not [a.id for a in kit if catalog.effective(a).get("usage") == "tiles"]
    assert [t.name for t in cat.tilesets if t.name == "overworld"] == [], (
        "no tile set of squares in an isometric project"
    )
    hoe = next(a for a in kit if a.id.endswith(".hoe"))
    assert catalog.effective(hoe)["size"] == [unit, unit]
    carrot = next(a for a in kit if a.id.endswith(".carrot"))
    assert catalog.effective(carrot)["frame"] == [unit, unit * 2]
    assert all(catalog.fits_projection(a, "isometric") for a in kit)
    # the requirement check says the same as the kit draws, in either view
    wanted = {
        i.detail["thing"] for i in requirements.check(_assemble(), cfg) if i.code == "ASSET-031"
    }
    assert "tilled soil" not in wanted and "bed" not in wanted and "hoe" in wanted


def test_the_smoke_steps_of_a_farm_ask_the_map() -> None:
    steps = (REPO / "godot_templates/builder/smoke/smoke_steps_farm.gd").read_text(encoding="utf-8")
    assert 'Input.action_press("move_' not in steps, "a walk walks to a place, whatever the view"
    assert "SmokeMap.walk_toward(" in steps and "face_cell(" in steps
    assert "RpgIso.reach_dir(" in steps and "RpgIso.cell_at(" in steps
    readme = (REPO / "godot_templates/project_files/README.farm.md").read_text(encoding="utf-8")
    assert "isometric" in readme


def test_a_plant_an_isometric_pack_calls_a_crop_grows(tmp_path: Path) -> None:
    """``cornDouble_N.png`` of the miniature packs: a picture on a diamond, turned four ways. In
    an isometric farm its first turn is a crop with drawn stages that stand where it stands."""
    opened = archive.open_pack(SYNTH / "iso_miniature", set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    corn = [a for a in cat.assets if "isometric.corndouble" in a.id]
    assert len(corn) == 4 and all(catalog.effective(a)["role"] == "DECORATION" for a in corn)
    assert farm_kit.to_grow(cat) == [], "seen from above nothing isometric is taken"
    found = farm_kit.to_grow(cat, "isometric")
    assert [a.id for a in found] == ["iso_miniature.isometric.corndouble_n"], "one crop, not four"
    assert farm_kit.grown_names(found) == {found[0].id: "corndouble"}, "called by the plant"
    staging = tmp_path / "staging"
    for asset in corn:
        target = staging / asset.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_picture(opened, asset))
    names, _notes = farm_kit.add(cat, 36, staging, "isometric")
    assert "grown/corndouble" in names
    strip = next(a for a in cat.assets if a.id == "rpggen_farm_kit.grown.corndouble")
    facets = catalog.effective(strip)
    width, height = catalog.effective(found[0])["size"]
    foot = catalog.effective(found[0])["origin"][1]
    assert facets["role"] == "CROP" and facets["usage"] == "growth_strip"
    assert facets["frame"] == [width, height] and facets["stages"] == farm_kit.CROP_STAGES
    assert facets["origin"] == [width // 2, foot], "the stages stand on the middle of the diamond"
    assert f"grown_from:{found[0].id}" in facets["tags"]
    # seen from above a single crop still stands on its last row
    from PIL import Image

    plain = farm_kit.grown(Image.new("RGBA", (16, 20), (200, 180, 40, 255)), 16)
    lifted = farm_kit.grown(Image.new("RGBA", (16, 20), (200, 180, 40, 255)), 16, foot=14)
    assert plain.size == lifted.size == (16 * farm_kit.CROP_STAGES, 32)
    assert plain.getpixel((8, 31))[3] > 0 and lifted.getpixel((8, 31))[3] == 0
    assert lifted.getpixel((8, 31 - 5))[3] > 0, "five rows of the picture lie below its foot"


def _picture(opened, asset) -> bytes:  # noqa: ANN001
    """The bytes of a picture of an opened pack, by the asset's path in the project."""
    name = Path(asset.path).name
    return next(p for p in Path(opened.root).rglob(name) if "Isometric" in p.parts).read_bytes()
