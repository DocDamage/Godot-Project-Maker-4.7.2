"""T17.14: isometric maps and actors, the Python side. The option that says how the pad moves
the player on diamonds, the kinds whose isometric maps are not made yet, the people drawn for a
project whose packs have none (``iso_kit``), and the pictures of a planned map and of a built
one, drawn as diamonds."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import (
    archive,
    catalog,
    config,
    dry_run,
    inventory,
    iso_kit,
    iso_math,
    map_preview,
    orchestrator,
    requirements,
)
from rpggen.errors import RpgGenError

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
PACK = config.PackRef("iso_tiles", str(SYNTH / "iso_tiles"), "0" * 64, "folder")
FOOT = (60, 34)
BACKGROUND = (24, 24, 30, 255)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(sources: list[Path], root: Path | None = None) -> catalog.Catalog:
    packs = []
    for source in sources:
        opened = archive.open_pack(source, {p[0].pack_id for p in packs})
        packs.append((opened, inventory.build_inventory(opened)))
        if root is not None:
            dest = root / "assets" / "packs" / opened.pack_id
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(opened.root, dest)
    cat, _issues, _generated = catalog.assemble(packs, None, [], use_cache=False)
    return cat


def _cfg(archetype: str = "turn_based", projection: str = "isometric") -> config.GeneratorConfig:
    cfg = config.default_for("x", [PACK], archetype=archetype)
    cfg.projection = projection
    return cfg


@pytest.fixture(scope="module")
def iso_catalog() -> catalog.Catalog:
    return _assemble([SYNTH / "iso_tiles"])


def _resolver(cat: catalog.Catalog):  # noqa: ANN202
    """The file of an asset of the synthetic packs, as the wizard's resolver gives it."""
    roots = {p.pack_id: p.root for p in cat.packs}

    def resolve(asset: catalog.Asset) -> Path | None:
        if asset.pack_id not in roots:
            return None
        return SYNTH / asset.pack_id / Path(asset.path).relative_to(roots[asset.pack_id])

    return resolve


def godot_stub(folder: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A file that passes for Godot 4.7.2: enough for the first phase of a run."""
    from rpggen.core import godot

    monkeypatch.setattr(godot, "detect_version", lambda exe: (4, 7, 2, "stable"))
    exe = folder / "godot.exe"
    exe.write_text("x")
    return exe


# ------------------------------------------------------------------------------ the config


def test_the_pad_follows_the_screen_unless_the_config_says_grid(tmp_path: Path) -> None:
    cfg = _cfg()
    assert cfg.iso_controls == "screen" == iso_math.CONTROLS_DEFAULT
    assert config.ISO_CONTROLS == iso_math.CONTROLS
    assert "iso_controls" not in cfg.to_json(), "the default is not written"
    assert "iso_controls" not in config.default_for("x", [PACK]).to_json()
    cfg.iso_controls = "grid"
    assert cfg.to_json()["iso_controls"] == "grid"
    config.save(cfg, tmp_path / "cfg.json")
    loaded = config.load(tmp_path / "cfg.json")
    assert loaded.iso_controls == "grid" and loaded.to_json() == cfg.to_json()
    data = cfg.to_json()
    data["iso_controls"] = "tank"
    with pytest.raises(RpgGenError) as bad:
        schema.validate("config", data)
    assert bad.value.issue.code == "CAT-002"
    # the builder writes it where the runtime reads it, for an isometric project only
    recipe = REPO / "godot_templates/builder/recipes/project_settings_recipe.gd"
    text = recipe.read_text(encoding="utf-8")
    assert "ProjectSettings.set_setting(RpgIso.CONTROLS_SETTING, _iso_controls(cfg))" in text
    runtime = REPO / "godot_templates/addons/rpg_runtime/world/iso.gd"
    assert 'const CONTROLS_SETTING := "rpg/iso_controls"' in runtime.read_text(encoding="utf-8")


@pytest.mark.parametrize("archetype", ["farm", "racing"])
def test_the_isometric_view_of_a_farm_and_of_a_race_is_not_made_yet(
    archetype: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert archetype in config.ISOMETRIC_KINDS, "the kind has the view: it is only not made"
    assert archetype in config.ISOMETRIC_NOT_YET
    cfg = _cfg(archetype)
    with pytest.raises(RpgGenError) as saved:
        config.save(cfg, tmp_path / "cfg.json")
    assert saved.value.issue.code == "CAT-002"
    assert "not made yet" in saved.value.issue.message and archetype in saved.value.issue.message
    assert "turn_based, arpg" in saved.value.issue.message, "it says what is made"
    (tmp_path / "hand.json").write_text(json.dumps(cfg.to_json()), encoding="utf-8")
    with pytest.raises(RpgGenError) as loaded:
        config.load(tmp_path / "hand.json")
    assert loaded.value.issue.code == "CAT-002"
    # nothing is built: a run with such a config made in memory (the wizard's) stops in its
    # first phase, before a file of the project is written
    result = orchestrator.run_in_memory(
        cfg, None, tmp_path / "out", godot_stub(tmp_path, monkeypatch)
    )
    assert not result.ok and result.failed_phase == "preflight"
    assert "CAT-002" in [i.code for i in result.issues if i.severity.value == "error"]
    assert not (tmp_path / "out" / "project.godot").exists()
    config.save(_cfg(archetype, "top_down"), tmp_path / "cfg.json")  # from above it is made


# -------------------------------------------------------------------------- the drawn people


def test_the_people_an_isometric_project_lacks_are_drawn(
    iso_catalog: catalog.Catalog, tmp_path: Path
) -> None:
    cat = catalog.Catalog.from_json(iso_catalog.to_json())
    assert [s.name for s in iso_kit.lacking(cat)] == ["hero", "villager", "enemy"]
    assert iso_kit.lacking(cat, "top_down") == [], "a project seen from above gets none of it"
    assert iso_kit.drawn_roles(cat) == {"PLAYER", "NPC", "ENEMY"}
    added, notes = iso_kit.add(cat, FOOT, tmp_path)
    assert added == ["hero", "villager", "enemy"]
    assert [(i.code, i.detail["role"]) for i in notes] == [
        ("ASSET-031", "PLAYER"),
        ("ASSET-031", "NPC"),
        ("ASSET-031", "ENEMY"),
    ]
    unit = iso_math.unit(*FOOT)
    assert iso_kit.frame_size(FOOT) == (unit, unit * 3 // 2) == (34, 51)
    assert iso_kit.frame_size((180, 104)) == (104, 156)
    assert iso_kit.frame_size((8, 4)) == (12, 18), "never smaller than twelve px"
    for name, role in (("hero", "PLAYER"), ("villager", "NPC"), ("enemy", "ENEMY")):
        asset = cat.asset(f"rpggen_iso_kit.{name}")
        assert asset is not None and asset.pack_id == iso_kit.KIT_PACK == "rpggen_iso_kit"
        facets = catalog.effective(asset)
        assert facets["role"] == role and facets["usage"] == "sprite"
        assert facets["frame"] == [34, 51] and facets["origin"] == [17, 50]
        assert "projection" not in facets, "a figure is drawn from the front: it fits any view"
        assert catalog.fits_projection(asset, "isometric")
        # a walk in four directions, and the figure standing
        for direction in ("down", "left", "right", "up"):
            assert len(facets["animations"][f"walk_{direction}"]["frames"]) == 4
            assert facets["animations"][f"idle_{direction}"]["frames"] == [
                [0, iso_kit.DIRECTIONS.index(direction)]
            ]
        with Image.open(tmp_path / asset.path) as sheet:
            assert sheet.size == (34 * 4, 51 * 4) == tuple(facets["size"])
            pixels = sheet.convert("RGBA")
            for row in range(4):
                for column in range(4):
                    cell = pixels.crop((column * 34, row * 51, column * 34 + 34, row * 51 + 51))
                    box = cell.getchannel("A").getbbox()
                    assert box is not None and box[3] == 51, "every frame stands on its feet"
            frames = [pixels.crop((c * 34, 0, c * 34 + 34, 51)).tobytes() for c in range(4)]
            assert frames[0] != frames[1] and frames[1] != frames[3], "the walk moves"
            rows = [pixels.crop((0, r * 51, 34, r * 51 + 51)).tobytes() for r in range(4)]
            assert len(set(rows)) == 4, "the four directions differ"
    assert any(p.pack_id == iso_kit.KIT_PACK for p in cat.packs)
    assert iso_kit.KIT_PACK in catalog.RUN_MADE_PACKS
    schema.validate("catalog", cat.to_json())
    # the same again: the kit of the last run is replaced, byte for byte
    before = {a.id: a.sha256 for a in cat.assets if a.pack_id == iso_kit.KIT_PACK}
    again, _notes = iso_kit.add(cat, FOOT, tmp_path / "second")
    assert again == added
    assert {a.id: a.sha256 for a in cat.assets if a.pack_id == iso_kit.KIT_PACK} == before
    assert len([a for a in cat.assets if a.pack_id == iso_kit.KIT_PACK]) == 3
    # a project that turned top-down is rid of it (it could not: but a catalog can be reused)
    iso_kit.add(cat, FOOT, tmp_path / "third", "top_down")
    assert not [a for a in cat.assets if a.pack_id == iso_kit.KIT_PACK]
    assert not [p for p in cat.packs if p.pack_id == iso_kit.KIT_PACK]


def test_a_packs_own_people_win(tmp_path: Path) -> None:
    cat = _assemble([SYNTH / "iso_tiles", SYNTH / "basic16"])
    own = {
        role
        for role in ("PLAYER", "NPC", "ENEMY")
        if any(
            catalog.effective(a).get("role") == role and a.status not in ("UNUSED", "MISSING")
            for a in cat.assets
        )
    }
    assert "PLAYER" in own, "basic16 has a hero drawn for a top-down game"
    lacking = {s.role for s in iso_kit.lacking(cat)}
    assert lacking == {"PLAYER", "NPC", "ENEMY"} - own
    added, _notes = iso_kit.add(cat, FOOT, tmp_path)
    assert cat.asset("rpggen_iso_kit.hero") is None, "a hero of any pack stands on the diamonds"
    assert len(added) == len(lacking)
    # a debug placeholder that was asked for is an asset with the role: it wins too
    bare = _assemble([SYNTH / "iso_tiles"])
    orchestrator.add_run_made_assets(bare, _cfg(), ["PLAYER"], tmp_path / "bare")
    assert bare.asset("debug_placeholders.player") is not None
    assert bare.asset("rpggen_iso_kit.hero") is None
    assert bare.asset("rpggen_iso_kit.villager") is not None


def test_an_isometric_project_is_not_refused_for_the_lack_of_a_hero(
    iso_catalog: catalog.Catalog, tmp_path: Path
) -> None:
    cat = catalog.Catalog.from_json(iso_catalog.to_json())
    for archetype in ("turn_based", "arpg"):
        found = requirements.check(cat, _cfg(archetype))
        assert not [i for i in found if i.severity.value == "error"], archetype
        notes = sorted(i.detail["thing"] for i in found if i.code == "ASSET-031")
        assert notes == ["enemy", "hero", "villager"]
        missing = {i.detail["role"] for i in found if i.code == "ASSET-010"}
        assert not missing & {"PLAYER", "NPC", "ENEMY"}, "what is drawn is not also missing"
    # seen from above the same pack has no hero and no ground
    top = requirements.check(cat, _cfg(projection="top_down"))
    assert {i.detail["role"] for i in top if i.severity.value == "error"} == {"PLAYER", "GROUND"}
    assert not [i for i in top if i.code == "ASSET-031"]
    # a run adds them, and says the same when it is asked again (the kit of the last run fills
    # nothing: the check goes by what the packs have)
    root = tmp_path / "root"
    installed = _assemble([SYNTH / "iso_tiles"], root)
    orchestrator.add_run_made_assets(installed, _cfg(), [], root)
    assert (root / "generated/iso_kit/hero.png").is_file()
    assert installed.asset("rpggen_iso_kit.hero") is not None
    again = requirements.check(installed, _cfg())
    assert sorted(i.detail["thing"] for i in again if i.code == "ASSET-031") == notes
    assert not [i for i in again if i.code == "ASSET-014"], "one hero, and it is drawn"
    orchestrator.add_run_made_assets(installed, _cfg(projection="top_down"), [], root)
    assert installed.asset("rpggen_iso_kit.hero") is not None, "a top-down run does not look"


def test_the_dry_run_of_an_isometric_project_needs_no_placeholder(tmp_path: Path) -> None:
    cfg = orchestrator.default_config_for_pack(SYNTH / "iso_tiles", "x")
    cfg.projection = "isometric"
    config.save(cfg, tmp_path / "cfg.json")
    result = dry_run.run(tmp_path / "cfg.json", tmp_path / "out")
    assert [i for i in result.issues if i.severity.value == "error"] == []
    assert result.ok


# ------------------------------------------------------------------------------ the previews


def test_the_plan_does_not_change_with_the_view(iso_catalog: catalog.Catalog) -> None:
    info = map_preview.building_info_for(iso_catalog, "", "isometric")
    assert info == {"size": [1, 1], "door": [0, 1]}, "the house of the pack stands on one cell"
    assert map_preview.building_info_for(iso_catalog) == {}, "no house of it in a top-down plan"
    assert map_preview.iso_building_geometry([3, 2]) == ((3, 2), (1, 2))
    assert map_preview.iso_building_geometry([2, 1]) == ((2, 1), (0, 1))
    assert map_preview.iso_building_geometry(None) == ((1, 1), (0, 1))
    first = map_preview.iso_buildings(iso_catalog)[0].id
    assert first == "iso_tiles.png.house_01_0"
    assert map_preview.iso_buildings(iso_catalog, "iso_tiles.png.house_01_2")[0].id.endswith("_2")
    # the same options and the same house give the same cells whatever draws them
    options = {"size": [28, 24], "buildings": 2, "npcs": 2, "decorations": 6}
    plan = map_preview.plan(options, 7, info, "turn_based")
    assert plan == map_preview.plan(options, 7, {"size": [1, 1], "door": [0, 1]}, "turn_based")
    assert plan["doors"][0] == [plan["buildings"][0][0], plan["buildings"][0][1] + 1] or tuple(
        plan["doors"][0]
    ) == (plan["buildings"][0][0], plan["buildings"][0][1] + 1), "the door cell is south of it"


def _pixel(image: Image.Image, cell: tuple[int, int], origin: tuple[float, float]) -> tuple:
    x, y = iso_math.cell_to_screen(cell[0], cell[1], *FOOT)
    return image.getpixel((round(origin[0] + x), round(origin[1] + y)))


def test_the_preview_of_an_isometric_plan_is_drawn_as_diamonds(
    iso_catalog: catalog.Catalog,
) -> None:
    art = map_preview.load_art(iso_catalog, _resolver(iso_catalog), projection="isometric")
    assert art.footprint == FOOT and art.tile_px == iso_math.unit(*FOOT)
    assert art.ground is not None and len(art.patches) == 3
    assert art.building is not None and art.building_size == (1, 1) and art.building_door == (0, 1)
    assert len(art.decorations) == 4, "the tree in its four turns"
    assert art.wall is None and art.road is None, "the pack names neither"
    assert map_preview.building_info(art) == {"size": [1, 1], "door": [0, 1]}
    plan = map_preview.plan({}, 12345, map_preview.building_info(art), "turn_based")
    image = map_preview.render(plan, art, 1)
    w, h = plan["size"]
    x0, y0, width, height = iso_math.bounds(w, h, *FOOT)
    assert image.width == width, "as wide as the diamonds of the plan"
    assert height <= image.height <= height + 80, "... and as high, with room for what rises"
    doubled = map_preview.render(plan, art, 2)
    assert doubled.size == (image.width * 2, image.height * 2)
    # where the map is: its corners are empty, the middle of every cell is painted
    top_margin = (
        image.height
        - height
        - 2
        - (art.ground.height - art.origins[id(art.ground)][1] - FOOT[1] // 2)
    )
    origin = (-x0, top_margin)
    assert (
        image.getpixel((2, 2)) == BACKGROUND and image.getpixel((image.width - 3, 2)) == BACKGROUND
    )
    assert image.getpixel((2, image.height - 3)) == BACKGROUND
    for cell in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2), (w // 2, h // 2)):
        assert _pixel(image, cell, origin) != BACKGROUND, f"the cell {cell} is on the picture"
    # the cell under a pixel of it, for a click on the preview
    for cell in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (12, 12), (5, 20)):
        x, y = iso_math.cell_to_screen(*cell, *FOOT)
        assert map_preview.iso_cell_at(plan, art, origin[0] + x, origin[1] + y, 1) == cell
        assert (
            map_preview.iso_cell_at(plan, art, 2 * (origin[0] + x), 2 * (origin[1] + y), 2) == cell
        )
    # the markers of the legend lie on their cells: the start is white, an enemy red
    assert _pixel(image, tuple(plan["spawn"]), origin) == map_preview.MARKER_COLORS["spawn"] + (
        255,
    )
    assert _pixel(image, tuple(plan["enemies"][0]), origin) == map_preview.MARKER_COLORS[
        "enemy"
    ] + (255,)
    # the east exit is a gap in the edge of the map: the right-hand side, half way down
    assert plan["exit_gap"][0] == w - 1
    # a top-down art is drawn as it always was: squares
    square = map_preview.render(plan, map_preview.Art(), 2)
    assert square.size == (w * 32, h * 32)


def test_a_preview_without_pictures_is_diamonds_too() -> None:
    art = map_preview.Art(footprint=(64, 32))
    plan = map_preview.plan({"size": [24, 24], "buildings": 0}, 3, {}, "arpg")
    image = map_preview.render(plan, art, 1)
    assert image.size[0] == 24 * 64
    origin = (iso_math.bounds(24, 24, 64, 32)[0] * -1, 4)
    # the flat colours of the legend: ground inside, the wall on the edge, nothing outside
    assert _flat(image, (12, 12), origin, (64, 32)) in (
        map_preview.FLAT_GROUND,
        *map_preview.FLAT_PATCHES,
        map_preview.FLAT_ROAD,
    )
    assert _flat(image, (0, 5), origin, (64, 32)) == map_preview.FLAT_WALL
    assert _flat(image, (23, 23), origin, (64, 32)) == map_preview.FLAT_WALL
    assert image.getpixel((3, 3)) == BACKGROUND
    # a diamond, not a square: the corner of a cell's box belongs to its neighbour or to nobody
    x, y = iso_math.cell_to_screen(0, 0, 64, 32)
    assert image.getpixel((round(origin[0] + x - 30), round(origin[1] + y - 14))) == BACKGROUND


def _flat(image: Image.Image, cell: tuple[int, int], origin: tuple[float, float], foot) -> tuple:  # noqa: ANN001
    x, y = iso_math.cell_to_screen(cell[0], cell[1], *foot)
    # beside the middle: a marker of the legend may lie on it
    return image.getpixel((round(origin[0] + x + foot[0] // 3), round(origin[1] + y)))[:3]


def test_the_picture_of_a_built_isometric_map(tmp_path: Path) -> None:
    """``render_view`` for the dump of an isometric map: a tile where Godot draws it, what stands
    on the map over it, a house cut in two for sorting whole again."""
    atlas = Image.new("RGBA", (120, 64), (0, 0, 0, 0))
    for column, colour in enumerate(((200, 40, 40, 255), (40, 40, 200, 255))):
        tile = Image.new("RGBA", (60, 64), (0, 0, 0, 0))
        from PIL import ImageDraw

        ImageDraw.Draw(tile).polygon([(30, 22), (59, 39), (30, 56), (0, 39)], fill=colour)
        atlas.paste(tile, (column * 60, 0))
    (tmp_path / "generated").mkdir()
    atlas.save(tmp_path / "generated/atlas.png")
    Image.new("RGBA", (20, 30), (250, 250, 0, 255)).save(tmp_path / "generated/hero.png")
    view = {
        "map": "res://game/maps/starter_map.tscn",
        "projection": "isometric",
        "tile_size": [60, 34],
        "sources": {
            "0": {
                "path": "res://generated/atlas.png",
                "region_size": [60, 64],
                "margins": [0, 0],
                "separation": [0, 0],
                "origins": {"0,0": [0, 7], "1,0": [0, 7]},
            }
        },
        "layers": [
            {"name": "Ground", "z": 0, "cells": [[x, y, 0, (x + y) % 2, 0] for y in range(3) for x in range(4)]},
            {"name": "Props", "z": 0, "cells": []},
        ],
        "entities": [
            {
                "name": "Player", "scene": "res://generated/scenes/actors/player.tscn",
                "entity_id": "", "x": 60.0, "y": 51.0,
                "sprite": {"path": "res://generated/hero.png", "region": [0, 0, 10, 30], "offset": [-10, -29]},
                "more": [{"path": "res://generated/hero.png", "region": [10, 0, 10, 30], "offset": [0, -29]}],
            },
            {"name": "Npc1", "scene": "res://x/npc.tscn", "entity_id": "", "x": 0.0, "y": 20.0, "sprite": {}},
        ],
    }  # fmt: skip
    image = map_preview.render_view(view, tmp_path, 1)
    x0, _y0, width, height = iso_math.bounds(4, 3, 60, 34)
    assert image.width == width and image.height == height + 64 + 32
    origin = (-x0, 64)
    red, blue = (200, 40, 40, 255), (40, 40, 200, 255)
    for x in range(4):
        for y in range(3):
            cx, cy = iso_math.cell_to_screen(x, y, 60, 34)
            # beside the middle: the hero stands over one of them
            at = (round(origin[0] + cx + 16), round(origin[1] + cy + 4))
            assert image.getpixel(at) == (blue if (x + y) % 2 else red), (x, y)
    # the hero's two halves side by side, on its feet at (60, 51)
    yellow = (250, 250, 0, 255)
    assert image.getpixel((round(origin[0] + 60 - 8), origin[1] + 51 - 10)) == yellow
    assert image.getpixel((round(origin[0] + 60 + 8), origin[1] + 51 - 10)) == yellow
    assert image.getpixel((round(origin[0] + 60 - 8), origin[1] + 51 - 28)) == yellow
    # a thing without a picture is a marker of its kind
    assert image.getpixel((round(origin[0]), origin[1] + 20 - 6)) == map_preview.ENTITY_COLORS[
        "npc"
    ] + (255,)
    assert image.getpixel((1, 1)) == BACKGROUND
    assert map_preview.render_view(view, tmp_path, 2).size == (image.width * 2, image.height * 2)
    # the same dump without the key is a map of squares, as it always was
    square = dict(view, tile_size=[16, 16])
    del square["projection"]
    assert map_preview.render_view(square, tmp_path, 1).size == (4 * 16, 4 * 16), "with its hero"
