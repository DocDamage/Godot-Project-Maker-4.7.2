"""Packs that describe themselves in JSON (Gridwright's isometric kits): the tiles and things of
a manifest, what is stacked and what moves, the characters of their own JSON, their effects and
shadows, and the layers of a creator, on small packs drawn in their shape."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, catalog, inventory, lpc_compose
from rpggen.core.adapters import gridwright

DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _png(path: Path, size: tuple[int, int], colour: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    img.paste((*colour, 255), (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1]))
    img.save(path)


SPRITES = {
    "floor_grass_01": ("floors", [32, 16], [16, 0], {"height": 0}),
    "block_grass_01": ("blocks", [32, 32], [16, 16], {"height": 16}),
    "path_dirt_05": ("paths", [32, 16], [16, 0], {"height": 0, "corners": 5}),
    "fence_wood_06": ("fences", [32, 32], [16, 16], {"joins": 6}),
    "fence_wood_00": ("fences", [32, 32], [16, 16], {"joins": 0}),
    "water_floor_f1": ("liquids", [32, 16], [16, 0], {"height": 0, "frame": 1}),
    "water_floor_f2": ("liquids", [32, 16], [16, 0], {"height": 0, "frame": 2}),
    "ramp_grass_up_ne_low": ("ramps", [32, 32], [16, 16], {"height": [0, 8], "up": "ne"}),
    "foam_ne_f1": ("foam", [32, 32], [16, 16], {"height": 12, "frame": 1}),
    "foam_ne_f2": ("foam", [32, 32], [16, 16], {"height": 12, "frame": 2}),
    "tree_oak_large": ("nature", [64, 64], [32, 48], {"shadow": "tree_oak_shadow"}),
    "tree_oak_shadow": ("shadows", [64, 64], [32, 48], {}),
    "fountain_f1": ("street", [32, 48], [16, 32], {"frame": 1}),
    "fountain_f2": ("street", [32, 48], [16, 32], {"frame": 2}),
    "cottage_left": ("buildings", [96, 64], [48, 32], {"footprint": [2, 2], "door": "left"}),
    "storey_brick_ground_door_sw": (
        "storeys",
        [32, 48],
        [16, 32],
        {"height": 20, "facade": "brick", "level": "ground", "storey": "door_sw"},
    ),  # fmt: skip
    "roof_06": ("roofs", [32, 32], [16, 16], {"joins": 6, "height": 1}),
    "ac_unit": ("rooftop", [32, 32], [16, 16], {}),
    "awning_red_sw": ("facade", [64, 32], [32, 16], {"face": "sw", "on_storey": True}),
    "wall_stone_ne": ("walls", [32, 48], [16, 32], {"wall": "ne", "height": 32}),
    "wall_stone_post": ("walls", [32, 48], [16, 32], {"wall": "post", "height": 32}),
    "lantern_ne": ("decor", [32, 64], [16, 48], {"wall": "ne"}),
    "door_wood_ne_f1": (
        "doors",
        [32, 48],
        [16, 32],
        {"wall": "ne", "frame": 1, "open_degrees": 0},
    ),  # fmt: skip
    "door_wood_ne_f2": (
        "doors",
        [32, 48],
        [16, 32],
        {"wall": "ne", "frame": 2, "open_degrees": 90},
    ),  # fmt: skip
    "catapult_f1": ("siege", [64, 64], [32, 48], {"frame": 1, "arm_degrees": 0}),
    "catapult_f2": ("siege", [64, 64], [32, 48], {"frame": 2, "arm_degrees": 60}),
}


def _tile_kit(root: Path) -> Path:
    pack = root / "kit" / "Gridwright Isometric Tiles"
    sprites = {}
    for name, (category, size, anchor, more) in SPRITES.items():
        rel = f"PNG/1x/{category}/{name}.png"
        for k in (1, 2):
            colour = (90, 160, 60) if "f2" not in name else (60, 90, 160)
            _png(pack / rel.replace("/1x/", f"/{k}x/"), (size[0] * k, size[1] * k), colour)
        sprites[name] = {"file": rel, "size": size, "footprint": [1, 1], "anchor": anchor, **more}
    _png(pack / "Sheets" / "floors_1x.png", (64, 16), (90, 160, 60))
    manifest = {"pack": "Gridwright Isometric Tiles", "grid": "ground diamond 32 x 16 px",
                "sprites": sprites}  # fmt: skip
    (pack / "isometric.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pack / "LICENSE.txt").write_text("Use it in your games.", encoding="utf-8")
    return root / "kit"


def _character(
    folder: Path, name: str, data: dict, actions: tuple = (("idle", 4), ("walk", 8))
) -> None:
    anims = {}
    for action, frames in actions:
        _png(folder / f"{name}_{action}.png", (64 * frames, 64 * 8), (200, 60, 60))
        anims[action] = {"image": f"{name}_{action}.png", "frames": frames, "fps": 6,
                         "loop": True}  # fmt: skip
    body = {"cell": [64, 64], "anchor": [32, 46], "rows": DIRECTIONS, "animations": anims, **data}
    (folder / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


def _characters(root: Path) -> Path:
    pack = root / "chars" / "Gridwright Isometric Characters"
    for name, side in (("knight", "hero"), ("goblin", "enemy")):
        _character(pack / "Sheets" / "1x" / name, name, {"character": name, "side": side})
        for d in DIRECTIONS:
            _png(
                pack / "PNG" / "1x" / name / "idle" / f"{name}_idle_{d}_01.png",
                (64, 64),
                (200, 60, 60),
            )
    _png(pack / "Effects" / "1x" / "shadow.png", (32, 16), (0, 0, 0))
    _png(pack / "Effects" / "1x" / "arrow.png", (32, 256), (220, 220, 200))
    _png(pack / "Effects" / "1x" / "shadow_bolt.png", (128, 256), (80, 0, 120))
    _png(pack / "Effects" / "1x" / "arcane_impact.png", (160, 32), (120, 120, 255))
    _png(pack / "Effects" / "1x" / "frames" / "arrow_s.png", (32, 32), (220, 220, 200))
    (pack / "LICENSE.txt").write_text("Use it in your games.", encoding="utf-8")
    return root / "chars"


def _catalog(source: Path) -> catalog.Catalog:
    opened = archive.open_pack(source, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _eff(cat: catalog.Catalog, ending: str) -> dict:
    found = [a for a in cat.assets if a.path.endswith(ending)]
    assert len(found) == 1, (ending, [a.path for a in cat.assets])
    return catalog.effective(found[0])


def _unused(eff: dict) -> str:
    return next((t for t in eff.get("tags", []) if t.startswith("unused_because:")), "")


def test_the_origin_is_the_middle_of_the_cell_nearest_the_camera() -> None:
    assert gridwright.origin_of((16, 16), (1, 1), (32, 16)) == [16, 24]  # a block
    assert gridwright.origin_of((16, 0), (1, 1), (32, 16)) == [16, 8]  # a floor
    assert gridwright.origin_of((48, 32), (2, 2), (32, 16)) == [48, 56]  # a cottage
    assert gridwright.origin_of((32, 16), (2, 1), (32, 16)) == [48, 32]  # a stall along col
    assert gridwright.joins_of(6) == ["e", "s"]  # SE and SW


def test_a_tile_kit_is_read_by_its_manifest(tmp_path: Path) -> None:
    cat = _catalog(_tile_kit(tmp_path))
    assert "isometric:32x16:manifest" in cat.packs[0].warnings
    floor = _eff(cat, "1x/floors/floor_grass_01.png")
    assert floor["usage"] == "iso_tile" and floor["role"] == "GROUND"
    assert floor["footprint"] == [32, 16] and floor["origin"] == [16, 8] and floor["rise"] == 0
    assert _eff(cat, "1x/paths/path_dirt_05.png")["role"] == "ROAD"
    fence = _eff(cat, "1x/fences/fence_wood_06.png")
    assert fence["role"] == "WALL" and fence["joins"] == ["e", "s"]
    alone = _eff(cat, "1x/fences/fence_wood_00.png")  # joins nothing: a plain wall tile
    assert alone["role"] == "WALL" and "joins" not in alone and "post" not in alone
    assert _eff(cat, "1x/walls/wall_stone_ne.png")["edge"] == "n"
    assert _eff(cat, "1x/walls/wall_stone_post.png")["post"] == "nw"
    tree = _eff(cat, "1x/nature/tree_oak_large.png")
    assert tree["usage"] == "sprite" and tree["stands_on"] == [1, 1] and tree["origin"] == [32, 56]
    assert tree["shadow"].endswith("1x/shadows/tree_oak_shadow.png")
    house = _eff(cat, "1x/buildings/cottage_left.png")
    assert house["stands_on"] == [2, 2] and house["origin"] == [48, 56]
    # set aside: only what another picture shows again
    assert _unused(_eff(cat, "1x/shadows/tree_oak_shadow.png")).endswith("shadow")
    assert _unused(_eff(cat, "2x/floors/floor_grass_01.png")).endswith("other_size")
    assert _unused(_eff(cat, "Sheets/floors_1x.png")).endswith("atlas_copy")


def test_what_is_stacked_says_where_and_how_high(tmp_path: Path) -> None:
    cat = _catalog(_tile_kit(tmp_path))
    block = _eff(cat, "1x/blocks/block_grass_01.png")
    assert block["usage"] == "iso_tile" and block["stack"] == "block" and block["lift"] == 16
    ramp = _eff(cat, "1x/ramps/ramp_grass_up_ne_low.png")
    assert ramp["stack"] == "ramp" and ramp["lift"] == 8 and "up:n" in ramp["tags"]
    storey = _eff(cat, "1x/storeys/storey_brick_ground_door_sw.png")
    assert storey["role"] == "BUILDING" and storey["stack"] == "storey" and storey["lift"] == 20
    assert {"facade:brick", "level:ground", "storey:door_sw"} <= set(storey["tags"])
    roof = _eff(cat, "1x/roofs/roof_06.png")
    assert roof["stack"] == "roof" and roof["joins"] == ["e", "s"]
    assert _eff(cat, "1x/rooftop/ac_unit.png")["stack"] == "on_roof"
    awning = _eff(cat, "1x/facade/awning_red_sw.png")
    assert awning["stack"] == "on_storey" and "face:s" in awning["tags"]
    lantern = _eff(cat, "1x/decor/lantern_ne.png")
    assert lantern["usage"] == "iso_tile" and lantern["stack"] == "on_wall"
    assert "wall:n" in lantern["tags"]
    assert _eff(cat, "1x/foam/foam_ne_f1.png")["stack"] == "overlay"


def test_what_moves_is_animated(tmp_path: Path) -> None:
    cat = _catalog(_tile_kit(tmp_path))
    # a tile: Godot animates it from its frames
    water = _eff(cat, "1x/liquids/water_floor_f1.png")
    assert water["role"] == "WATER" and len(water["tile_frames"]) == 1
    assert water["tile_frames"][0].endswith("1x/liquids/water_floor_f2.png")
    assert water["tile_fps"] > 0
    assert _unused(_eff(cat, "1x/liquids/water_floor_f2.png")).endswith("animation_frame")
    # a thing: a strip put together from its frames
    fountain = _eff(cat, "1x/street/fountain_f1.png")
    loop = fountain["animations"]["idle_down"]
    assert loop["frames"] == [[0, 0], [1, 0]] and loop["loop"] is True
    assert loop["source"].startswith("generated/frame_strips/")
    # poses: a door is a tile a pose, a catapult plays its poses once
    for frame in ("f1", "f2"):
        door = _eff(cat, f"1x/doors/door_wood_ne_{frame}.png")
        assert door["role"] == "WALL" and door["edge"] == "n" and "door" in door["tags"]
        assert "tile_frames" not in door
    catapult = _eff(cat, "1x/siege/catapult_f1.png")["animations"]
    assert catapult["idle_down"]["frames"] == [[0, 0]]
    assert catapult["use_down"]["frames"] == [[0, 0], [1, 0]] and not catapult["use_down"]["loop"]


def test_a_character_is_read_by_its_own_json(tmp_path: Path) -> None:
    cat = _catalog(_characters(tmp_path))
    knight = _eff(cat, "knight/knight_idle.png")
    assert knight["role"] == "PLAYER" and knight["directions"] == 8
    assert knight["frame"] == [64, 64] and knight["origin"] == [32, 46]
    assert len(knight["animations"]) == 16  # two animations in eight directions
    assert knight["animations"]["idle_down"]["frames"][0] == [0, 0]
    assert knight["animations"]["idle_up_left"]["frames"][0] == [0, 3]  # nw is the fourth row
    walk = knight["animations"]["walk_right"]
    assert len(walk["frames"]) == 8 and walk["source"].endswith("knight/knight_walk.png")
    assert "source" not in knight["animations"]["idle_down"]  # its own picture
    assert knight["shadow"].endswith("Effects/1x/shadow.png")
    assert _eff(cat, "goblin/goblin_idle.png")["role"] == "ENEMY"
    assert _unused(_eff(cat, "knight/knight_walk.png")).endswith("animation_sheet")
    assert _unused(_eff(cat, "idle/knight_idle_s_01.png")).endswith("sheet_frame")
    assert _unused(_eff(cat, "Effects/1x/shadow.png")).endswith("shadow")


def test_the_effects_of_a_character_pack_play(tmp_path: Path) -> None:
    cat = _catalog(_characters(tmp_path))
    arrow = _eff(cat, "Effects/1x/arrow.png")
    assert arrow["role"] == "PROJECTILE" and arrow["directions"] == 8
    assert arrow["animations"]["fly_up_left"]["frames"] == [[0, 3]]
    bolt = _eff(cat, "Effects/1x/shadow_bolt.png")  # the cultist's bolt, not a shadow
    assert bolt["role"] == "PROJECTILE" and len(bolt["animations"]["fly_down"]["frames"]) == 4
    impact = _eff(cat, "Effects/1x/arcane_impact.png")
    assert impact["role"] == "EFFECT" and impact["animations"]["idle_down"]["loop"] is False
    assert _unused(_eff(cat, "Effects/1x/frames/arrow_s.png")).endswith("sheet_frame")


def test_an_effect_drawn_a_picture_a_direction_and_a_frame_is_one(tmp_path: Path) -> None:
    pack = tmp_path / "heroes" / "Gridwright Isometric Hero Creator"
    _character(pack / "Characters" / "1x" / "archer", "archer", {"character": "archer",
               "layers": [["body", "pale"]]})  # fmt: skip
    for d in DIRECTIONS:
        _png(pack / "Effects" / "1x" / f"arrow_{d}.png", (32, 32), (220, 220, 200))
        for n in (1, 2):
            _png(pack / "Effects" / "1x" / f"bolt_arcane_{d}_{n}.png", (32, 32), (120, 0, 255))
    for n in (1, 2, 3):
        _png(pack / "Effects" / "1x" / f"impact_arcane_{n}.png", (32, 32), (120, 120, 255))
    cat = _catalog(tmp_path / "heroes")
    assert _eff(cat, "archer/archer_idle.png")["role"] == "PLAYER"  # of a creator of heroes
    arrow = _eff(cat, "Effects/1x/arrow_s.png")
    assert arrow["role"] == "PROJECTILE" and arrow["directions"] == 8
    assert arrow["animations"]["fly_left"]["frames"] == [[0, 2]]
    assert arrow["animations"]["fly_left"]["source"].startswith("generated/frame_strips/")
    bolt = _eff(cat, "Effects/1x/bolt_arcane_s_1.png")["animations"]
    assert bolt["fly_down"]["frames"] == [[0, 0], [1, 0]]
    impact = _eff(cat, "Effects/1x/impact_arcane_1.png")
    assert impact["role"] == "EFFECT" and len(impact["animations"]["idle_down"]["frames"]) == 3
    assert _unused(_eff(cat, "Effects/1x/arrow_e.png")).endswith("animation_sheet")


def test_the_layers_of_a_creator_are_a_layered_character(tmp_path: Path) -> None:
    pack = tmp_path / "creator" / "Gridwright Isometric Character Creator"
    files = {}
    for build in ("broad", "slim"):
        for group, style, colour in (("body", "body", "pale"), ("hair", "hair_short", "brown"),
                                     ("top", "top_shirt", "green")):  # fmt: skip
            rel = f"Layers/{build}/{group}/{build}_{style}_{colour}.png"
            _png(pack / rel, (64 * 8, 64 * 8), (180, 140, 100))
            files.setdefault(build, {}).setdefault(style, {})[colour] = rel
    data = {
        "pack": "Gridwright Isometric Character Creator", "cell": [64, 64], "anchor": [32, 46],
        "rows": DIRECTIONS, "order": ["body", "top", "hair"], "layers": files,
        "styles": {"body": {"group": "body"}, "hair_short": {"group": "hair"},
                   "top_shirt": {"group": "top"}},
        "animations": [{"name": "idle", "frames": 4, "fps": 6, "loop": True, "column": 0},
                       {"name": "walk", "frames": 4, "fps": 10, "loop": True, "column": 4}],
    }  # fmt: skip
    (pack / "layers.json").write_text(json.dumps(data), encoding="utf-8")
    cat = _catalog(tmp_path / "creator")
    body = next(a for a in cat.assets if a.path.endswith("broad/body/broad_body_pale.png"))
    assert lpc_compose.is_body(body) and lpc_compose.is_layered(body)
    hair = next(a for a in cat.assets if a.path.endswith("broad/hair/broad_hair_short_brown.png"))
    assert lpc_compose.part_of(hair) == "hair" and lpc_compose.fits(hair, body)
    slim = next(a for a in cat.assets if a.path.endswith("slim/body/slim_body_pale.png"))
    assert not lpc_compose.fits(hair, slim)  # a build's layers are its own character's
    walk = catalog.effective(hair)["animations"]["walk_up"]
    assert walk["frames"][0] == [4, 4]  # its column, the row of n


@pytest.mark.parametrize(
    ("data", "pack_role", "role"),
    [
        ({"side": "npc"}, "", ("NPC", "")),
        ({"group": "Farm", "species": "cow"}, "ANIMAL", ("ANIMAL", "animal")),
        ({"group": "Pets", "species": "dog"}, "ANIMAL", ("DECORATION", "pet")),
        ({"group": "Wild", "species": "wolf"}, "ANIMAL", ("ENEMY", "wild")),
        ({"group": "Wild", "species": "deer"}, "ANIMAL", ("DECORATION", "wild")),
        ({"unit": "archer", "animations": {"attack": {}}}, "", ("ENEMY", "")),
        ({"unit": "priest", "animations": {"heal": {}}}, "", ("NPC", "")),
        ({"layers": []}, "HERO", ("PLAYER", "")),
        ({"layers": []}, "", ("NPC", "")),
        ({"monster": "bat"}, "ENEMY", ("ENEMY", "")),
    ],
)
def test_the_role_of_a_character_is_what_its_json_says(
    data: dict, pack_role: str, role: tuple
) -> None:
    assert gridwright.role_of(data, pack_role) == role


def test_a_zip_whose_long_name_is_cut_is_named_by_its_one_folder(tmp_path: Path) -> None:
    import zipfile

    from rpggen import ids

    long = tmp_path / "isometric-map-builder-pixel-art-godot-tiled-pack-isometric-tiles.zip"
    with zipfile.ZipFile(long, "w") as zf:
        zf.writestr("Gridwright Isometric Tiles/README.txt", "a pack")
        zf.writestr("__MACOSX/._README.txt", "")
    assert archive.pack_name(long) == "Gridwright Isometric Tiles"
    assert ids.pack_id_from_name(archive.pack_name(long), set()) == "gridwright_isometric_tiles"
    loose = tmp_path / "isometric-map-builder-pixel-art-godot-tiled-pack-isometric-city.zip"
    with zipfile.ZipFile(loose, "w") as zf:  # files beside the folder: the zip's own name
        zf.writestr("Gridwright Isometric City/README.txt", "a pack")
        zf.writestr("LICENSE.txt", "use it")
    assert archive.pack_name(loose) == loose.stem
    short = tmp_path / "Tiny Farm.zip"  # a name an id keeps whole is the name
    with zipfile.ZipFile(short, "w") as zf:
        zf.writestr("Kenney Tiny Farm/tile.png", "")
    assert archive.pack_name(short) == "Tiny Farm"
    assert archive.pack_name(tmp_path) == tmp_path.name


def test_the_folders_of_copies_are_kept_out_of_godots_import(tmp_path: Path) -> None:
    from rpggen.core import staging

    source = _tile_kit(tmp_path)
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    stg = staging.Staging(tmp_path / "game", tmp_path / "game" / ".rpggen_staging")
    stg.staging.mkdir(parents=True)
    staging.install_pack(stg, opened.root, inv.pack_id, inv)
    written = staging.ignore_copies(stg, cat)
    root = f"assets/packs/{inv.pack_id}/Gridwright Isometric Tiles"
    # the 2x copies and the sheet that holds the pieces again are copies; 1x is used
    assert sorted(written) == [f"{root}/PNG/2x/.gdignore", f"{root}/Sheets/.gdignore"]
    assert (stg.staging / root / "PNG" / "2x" / ".gdignore").is_file()
    assert not (stg.staging / root / "PNG" / "1x" / ".gdignore").exists()
    # a later frame and a shadow are set aside but used (the tile's frames, the tree's shadow)
    assert (stg.staging / root / "PNG" / "1x" / "liquids" / "water_floor_f2.png").is_file()
    assert staging.ignore_copies(stg, cat) == written  # again: the same markers


def test_a_copy_the_build_animates_is_not_kept_out_of_godots_import(tmp_path: Path) -> None:
    """CI (metroidvania, farm_sizes): the sprite frames of every animated sprite are built,
    set aside or not, so the folder of a 32 px copy of an animated sheet must stay imported."""
    from rpggen.core import staging

    source = _tile_kit(tmp_path)
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    copy = next(a for a in cat.assets if "/PNG/2x/" in a.path and a.status == "UNUSED")
    assert copy.path not in staging._referenced(cat)
    copy.overrides = {**copy.overrides, "usage": "sprite", "animations": {"idle": {"frames": [0]}}}
    assert copy.path in staging._referenced(cat)
    stg = staging.Staging(tmp_path / "game", tmp_path / "game" / ".rpggen_staging")
    stg.staging.mkdir(parents=True)
    staging.install_pack(stg, opened.root, inv.pack_id, inv)
    root = f"assets/packs/{inv.pack_id}/Gridwright Isometric Tiles"
    assert f"{root}/PNG/2x/.gdignore" not in staging.ignore_copies(stg, cat)


def test_the_things_of_a_preview_are_none(tmp_path: Path) -> None:
    kit = _tile_kit(tmp_path)
    preview = kit / "Gridwright Isometric Tiles" / "Preview" / "kit.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (1920, 1080), (30, 30, 40, 255)).save(preview)
    cat = _catalog(kit)
    sheet = next(a for a in cat.assets if a.path.endswith("Preview/kit.png"))
    assert sheet.status == "UNUSED"
    assert "unused_because:preview_folder" in catalog.effective(sheet)["tags"]

    def cut(n: int, status: str = "AUTO_DETECTED") -> catalog.SheetObject:
        return catalog.SheetObject(
            f"{sheet.id}#object_{n}", sheet.id, f"object_{n}", "DECORATION", [0, 0, 32, 32],
            [16, 31], [], {"profile": "NONE"}, [], status=status, source="auto",
        )  # fmt: skip

    before = catalog.Catalog.from_json(cat.to_json())
    before.objects = [cut(2)]  # a project that has used the second one
    cat.objects = [cut(1), cut(2), cut(3, "CONFIRMED")]
    catalog.set_aside_preview_objects(cat, before)
    assert [o.status for o in cat.objects] == ["UNUSED", "AUTO_DETECTED", "CONFIRMED"]
