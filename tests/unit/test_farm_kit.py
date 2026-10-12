"""T17.02: the drawn stand-ins of the farm, the roles CROP, ANIMAL and TOOL, what a farm
requires and its sound slots."""

from __future__ import annotations

import io
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen import paths, schema
from rpggen.core import (
    archive,
    catalog,
    config,
    farm_kit,
    inventory,
    labels,
    mapping,
    requirements,
    sound_slots,
)
from rpggen.gui.widgets import asset_detail

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
ROLES = {"CROP", "ANIMAL", "TOOL"}
ALL = ["turnip", "carrot", "berry", "soil", "watered", "hoe", "watering_can", "sickle", "axe",
       "seed_bag", "hen", "egg", "shipping_bin", "bed", "rain"]  # fmt: skip


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    return out.getvalue()


def _catalog(source: Path) -> catalog.Catalog:
    opened = archive.open_pack(source, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _cfg(source: Path, archetype: str = "farm") -> config.GeneratorConfig:
    ref = config.PackRef(source.stem, str(source), "0" * 64, "folder")
    return config.default_for("Farm", [ref], archetype=archetype)


def _staged(cat: catalog.Catalog, source: Path, root: Path) -> Path:
    """A staging copy with the pack's files where the catalog says they are."""
    for pack in cat.packs:
        shutil.copytree(source, root / pack.root, dirs_exist_ok=True)
    return root


def _roles(cat: catalog.Catalog) -> dict[str, str]:
    return {a.path.rsplit("/", 1)[-1]: catalog.effective(a)["role"] for a in cat.assets}


def _colours(image: Image.Image) -> set[tuple[int, ...]]:
    return {tuple(int(v) for v in px) for px in np.asarray(image).reshape(-1, 4)}


def _errors(issues) -> list[str]:  # noqa: ANN001
    return [i.message for i in issues if i.severity.value == "error"]


# ----------------------------------------------------------------------------- the pictures

SIZES = {
    "turnip": lambda t: (5 * t, 2 * t),
    "carrot": lambda t: (5 * t, 2 * t),
    "berry": lambda t: (5 * t, 2 * t),
    "soil": lambda t: (t, t),
    "watered": lambda t: (t, t),
    "hoe": lambda t: (t, t),
    "watering_can": lambda t: (t, t),
    "sickle": lambda t: (t, t),
    "axe": lambda t: (t, t),
    "seed_bag": lambda t: (t, t),
    "hen": lambda t: (4 * t, 4 * t),
    "egg": lambda t: (t, t),
    "shipping_bin": lambda t: (t, t),
    "bed": lambda t: (t, 2 * t),
    "rain": lambda t: (3 * 4 * t, 4 * t),
}
FRAMES = {"turnip": 5, "carrot": 5, "berry": 5, "hen": 16, "rain": 3}  # the others are one


def _cells(image: Image.Image, columns: int, rows: int = 1) -> list[Image.Image]:
    w, h = image.width // columns, image.height // rows
    return [
        image.crop((c * w, r * h, (c + 1) * w, (r + 1) * h))
        for r in range(rows)
        for c in range(columns)
    ]


@pytest.mark.parametrize("tile", [16, 32])
@pytest.mark.parametrize("stand_in", farm_kit.STAND_INS, ids=lambda s: s.name)
def test_every_stand_in_is_drawn_in_its_size_and_the_same_every_time(
    stand_in: farm_kit.StandIn, tile: int
) -> None:
    image = stand_in.draw(tile)
    assert image.mode == "RGBA" and image.size == SIZES[stand_in.name](tile)
    assert _png(image) == _png(stand_in.draw(tile)), "byte for byte, on every run"
    facets = farm_kit._facets(stand_in, image, tile)
    frames = FRAMES.get(stand_in.name, 1)
    if stand_in.usage == "growth_strip":
        assert facets["stages"] == frames == farm_kit.CROP_STAGES and "animations" not in facets
        assert facets["frame"] == [tile, 2 * tile] and facets["origin"] == [tile // 2, 2 * tile - 1]
        cells = _cells(image, frames)
    elif stand_in.name == "hen":
        walks = [facets["animations"][f"walk_{d}"]["frames"] for d in farm_kit.HEN_ROWS]
        assert walks == [[[c, r] for c in range(4)] for r in range(4)]
        assert sum(len(w) for w in walks) == frames and facets["frame"] == [tile, tile]
        cells = _cells(image, 4, 4)
    elif stand_in.name == "rain":
        assert len(facets["animations"]["idle_down"]["frames"]) == frames
        assert facets["frame"] == [4 * tile, 4 * tile]
        cells = _cells(image, frames)
    else:
        assert "animations" not in facets and facets["size"] == list(image.size)
        cells = [image]
    assert all(np.asarray(cell)[..., 3].any() for cell in cells), "something in every frame"
    assert facets["role"] == stand_in.role and farm_kit.KIT_TAG in facets["tags"]


@pytest.mark.parametrize("tile", [16, 32])
def test_what_the_pictures_show(tile: int) -> None:
    strips = {name: farm_kit.crop(tile, fruit) for name, fruit in farm_kit.CROPS}
    assert len({_png(s) for s in strips.values()}) == 3, "three crops in three colours"
    for name, fruit in farm_kit.CROPS:
        stages = _cells(strips[name], farm_kit.CROP_STAGES)
        filled = [int((np.asarray(s)[..., 3] > 0).sum()) for s in stages]
        assert filled == sorted(filled) and filled[0] < filled[-1], "it grows"
        assert fruit in _colours(stages[-1]), "the ripe one bears"
        assert fruit not in _colours(stages[1])
    assert np.asarray(farm_kit.soil(tile))[..., 3].all(), "a tile has no hole"
    assert np.asarray(farm_kit.watered(tile))[..., 3].all()
    assert _png(farm_kit.soil(tile)) != _png(farm_kit.watered(tile))
    icons = {kind: _png(farm_kit.tool_icon(tile, kind)) for kind in farm_kit.TOOLS}
    assert len(set(icons.values())) == len(farm_kit.TOOLS) == 4
    with pytest.raises(ValueError, match="no such tool"):
        farm_kit.tool_icon(tile, "banana")
    hen = _cells(farm_kit.hen(tile), 4, 4)
    assert len({_png(c) for c in hen}) >= 12, "a walk: the frames of a row differ"
    left, right = hen[4:8], hen[8:12]
    assert [_png(c.transpose(Image.Transpose.FLIP_LEFT_RIGHT)) for c in left] == [
        _png(c) for c in right
    ]
    drops = _cells(farm_kit.rain(tile), farm_kit.RAIN_FRAMES)
    assert len({_png(c) for c in drops}) == 3, "the rain falls"
    assert all((np.asarray(c)[..., 3] == 0).mean() > 0.8 for c in drops), "an overlay is clear"


def test_a_tile_size_that_is_too_small_is_drawn_at_eight() -> None:
    assert farm_kit.egg(2).size == farm_kit.egg(8).size == (8, 8)
    assert np.asarray(farm_kit.tool_icon(8, "hoe"))[..., 3].any()


@pytest.mark.parametrize("tile", [16, 32])
def test_a_crop_of_one_picture_gets_drawn_stages_and_stays_the_ripe_one(tile: int) -> None:
    pumpkin = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pumpkin.paste((230, 130, 40, 255), (3, 4, 13, 15))
    strip = farm_kit.grown(pumpkin, tile)
    assert strip.size == (5 * tile, 2 * tile) and _png(strip) == _png(farm_kit.grown(pumpkin, tile))
    ripe = _cells(strip, 5)[-1]
    left = (tile - 16) // 2
    assert _png(ripe.crop((left, 2 * tile - 16, left + 16, 2 * tile))) == _png(pumpkin)
    assert (230, 130, 40, 255) in _colours(_cells(strip, 5)[3]), "in bud in its colour"
    big = farm_kit.grown(Image.new("RGBA", (48, 80), (9, 9, 9, 255)), 16)
    assert big.size == (5 * 48, 80), "a cell is as large as a larger picture"


# ----------------------------------------------------------------------------- requirements


def test_what_a_farm_requires_and_how_it_says_so() -> None:
    assert requirements.REQUIRED["farm"] == ["PLAYER", "GROUND"]
    assert requirements.required_by("BUILDING", "farm") == "the house, the coop and the barn"
    assert requirements.required_by("ITEM", "farm") == "seeds, produce and what the shop sells"
    assert requirements.required_by("BUILDING", "turn_based") == "building scenes", "as before"
    rows = mapping.rows("farm")
    assert [r.role for r in rows if r.required] == ["PLAYER", "GROUND"]
    assert ROLES | {"BUILDING", "NPC", "ITEM", "DECORATION", "UI"} <= {r.role for r in rows}
    assert all(labels.role_label(r.role) != r.role for r in rows), "every row has a name"
    own = requirements.REQUIRED_BY_ARCHETYPE["farm"]
    assert ROLES | {"PLAYER", "GROUND", "NPC", "DECORATION", "UI"} <= set(own)
    grouped = {r for _name, roles in labels.MAPPING_GROUPS for r in roles}
    assert {r.role for r in rows} <= grouped, "every row is in a group of the Mapping page"
    assert requirements.FARM_KIT_PACK == farm_kit.KIT_PACK in catalog.RUN_MADE_PACKS


def test_the_top_down_sample_as_a_farm_passes_with_notes_only() -> None:
    """The card's *Done when*."""
    sample = paths.sample_pack_root()
    cat = _catalog(sample)
    issues = requirements.check(cat, _cfg(sample))
    assert not _errors(issues)
    assert {i.severity.value for i in issues} == {"info"}, [i.message for i in issues]
    notes = [i for i in issues if i.code == "ASSET-031"]
    assert [farm_kit.KIT_PACK + "." + n for n in ALL] == [
        farm_kit.asset_id(s) for s in farm_kit.lacking(cat)
    ]
    assert len(notes) == len(ALL) and "a drawn one stands in" in notes[0].message
    # as a village of the older kinds the same pack is told nothing of the farm
    older = requirements.check(cat, _cfg(sample, "turn_based"))
    assert not [i for i in older if i.code == "ASSET-031"]


def test_a_farm_without_a_player_or_ground_is_refused(tmp_path: Path) -> None:
    pack = tmp_path / "icons"
    (pack / "ui").mkdir(parents=True)
    Image.new("RGBA", (16, 16), (200, 200, 60, 255)).save(pack / "ui" / "coin.png")
    issues = requirements.check(_catalog(pack), _cfg(pack))
    missing = sorted(i.detail["role"] for i in issues if i.code == "ASSET-010" and i.severity.value == "error")  # fmt: skip
    assert missing == ["GROUND", "PLAYER"], "the kit draws neither"
    wording = {i.detail["role"]: i.message for i in issues if i.code == "ASSET-010"}
    assert "the farmer" in wording["PLAYER"]
    assert "the house, the coop and the barn" in wording["BUILDING"]
    # drawn crops, animals and tools are noted, not also reported as missing; scenery is
    assert not ROLES & set(wording) and "DECORATION" in wording
    assert not _errors(requirements.check(_catalog(SYNTH / "basic16"), _cfg(SYNTH / "basic16")))


# ----------------------------------------------------------------------------- the catalog


def test_a_plain_pack_gets_the_whole_kit_and_a_second_run_the_same(tmp_path: Path) -> None:
    pack = SYNTH / "basic16"
    cat = _catalog(pack)
    cfg = _cfg(pack)
    before = [(i.code, i.detail.get("role")) for i in requirements.check(cat, cfg)]
    starter = mapping.default_starter(cat, "farm")
    names, notes = farm_kit.add(cat, 16, tmp_path / "staging")
    assert names == ALL and [i.code for i in notes] == ["ASSET-031"] * len(ALL)
    assert [i.file for i in notes] == [f"generated/farm_kit/{n}.png" for n in ALL]
    schema.validate("catalog", cat.to_json())
    kit = {a.id.split(".", 1)[1]: a for a in cat.assets if a.pack_id == farm_kit.KIT_PACK}
    assert sorted(kit) == sorted(ALL)
    assert all(a.status == "CONFIRMED" and a.detected_by == "placeholder" for a in kit.values())
    for name, asset in kit.items():
        assert (tmp_path / "staging" / asset.path).read_bytes() == _png(
            next(s for s in farm_kit.STAND_INS if s.name == name).draw(16)
        )
    turnip = catalog.effective(kit["turnip"])
    assert (turnip["usage"], turnip["role"], turnip["stages"]) == ("growth_strip", "CROP", 5)
    assert turnip["tags"] == ["crop", "farm_kit"]
    hoe, can = catalog.effective(kit["hoe"]), catalog.effective(kit["watering_can"])
    assert (hoe["usage"], hoe["role"], hoe["tags"]) == ("sprite", "TOOL", ["farm_kit", "tool"])
    assert can["frame"] == [16, 16]
    hen = catalog.effective(kit["hen"])
    assert hen["role"] == "ANIMAL" and hen["tags"] == ["animal", "farm_kit", "hen"]
    assert hen["animations"]["walk_left"]["frames"] == [[0, 1], [1, 1], [2, 1], [3, 1]]
    # what the top-down recipes would scatter or take for a chest is an object: theirs to skip
    for name, role, tag in (("seed_bag", "ITEM", "seed"), ("egg", "ITEM", "product"),
                            ("shipping_bin", "DECORATION", "bin"), ("bed", "DECORATION", "bed")):  # fmt: skip
        eff = catalog.effective(kit[name])
        assert (eff["usage"], eff["role"]) == ("object", role) and tag in eff["tags"], name
    rain = catalog.effective(kit["rain"])
    assert (rain["role"], rain["frame"], rain["tags"]) == ("EFFECT", [64, 64], ["farm_kit", "weather"])  # fmt: skip
    soil = catalog.effective(kit["soil"])
    assert (soil["usage"], soil["role"], soil["grid"]["cell"]) == ("tiles", "DECORATION", [16, 16])
    assert catalog.effective(kit["watered"])["tags"] == ["farm_kit", "watered"]
    sources = [src["asset"] for t in cat.tilesets for src in t.sources]
    assert sources[-2:] == ["rpggen_farm_kit.soil", "rpggen_farm_kit.watered"], "after the pack's"
    # the kit of a last run fills no role and no starter key: the check and the mapping say
    # what they said before it was there
    assert [(i.code, i.detail.get("role")) for i in requirements.check(cat, cfg)] == before
    assert mapping.default_starter(cat, "farm") == starter and "chest" not in starter
    assert mapping.best_for(cat, "ITEM") is None and mapping.best_for(cat, "CROP") is None
    again = catalog.Catalog.from_json(cat.to_json())
    names_again, _notes = farm_kit.add(again, 16, tmp_path / "again")
    assert names_again == ALL and again.to_json() == cat.to_json()
    assert len({a.id for a in again.assets}) == len(again.assets)


def test_the_ranch_gets_its_roles_and_keeps_what_it_has(tmp_path: Path) -> None:
    cat = _catalog(SYNTH / "ranch")
    roles = _roles(cat)
    for crop in ("corn_16x32_8frames", "wheat_16x32_5frames", "tomato_16x32_12frames", "pumpkin_16x16"):  # fmt: skip
        assert roles[f"{crop}.png"] == "CROP", crop
    for tool in ("hoe", "shovel", "sickle", "water"):
        assert roles[f"{tool}_16x16.png"] == "TOOL", "water in a folder of tools is the can"
    animals = [n for n in roles if n.startswith(("hen_01", "cow_01"))]
    assert len(animals) == 12 and {roles[n] for n in animals} == {"ANIMAL"}, "walking or asleep"
    assert roles["rain_64x64_3frames.png"] == "EFFECT", "nobody to talk to"
    assert roles["farmer_walk_down_16x16_4frames.png"] == "PLAYER"
    assert roles["farmer_hoe_down_16x16_3frames.png"] == "NPC", "tagged tool, but no icon"
    assert roles["house.png"] == "BUILDING" and roles["shipping_bin.png"] == "DECORATION"
    assert "NPC" not in {roles[n] for n in animals} and "WATER" not in roles.values()
    # a pack's own asset wins: only what the ranch has none of is drawn
    lacking = [s.name for s in farm_kit.lacking(cat)]
    assert lacking == ["axe", "seed_bag", "egg", "bed"]
    own = {s.name: farm_kit.own_asset(cat, s) for s in farm_kit.STAND_INS}
    assert own["hoe"].id == "ranch.tools.hoe_16x16", "not the farmer's strip with the hoe"
    assert own["watering_can"].id == "ranch.tools.water_16x16"
    assert own["soil"].id == "ranch.autotiles.n01_soil_tilled"
    assert own["watered"].id == "ranch.autotiles.n02_soil_watered"
    assert own["shipping_bin"].id == "ranch.props.shipping_bin"
    assert own["rain"].id == "ranch.weather.rain_64x64_3frames"
    assert farm_kit.growing(cat) == 4 and [a.id for a in farm_kit.to_grow(cat)] == [
        "ranch.crops.pumpkin_16x16"
    ]
    issues = requirements.check(cat, _cfg(SYNTH / "ranch"))
    assert not _errors(issues)
    assert [i.detail["thing"] for i in issues if i.code == "ASSET-031"] == [
        "axe", "bag of seeds", "egg", "bed"]  # fmt: skip
    # the run: the four stand-ins, and the pumpkin's stages
    staging = _staged(cat, SYNTH / "ranch", tmp_path / "staging")
    names, notes = farm_kit.add(cat, 16, staging)
    assert names == [*lacking, "grown/pumpkin_16x16"] and len(notes) == 4
    schema.validate("catalog", cat.to_json())
    pumpkin = cat.asset("rpggen_farm_kit.grown.pumpkin_16x16")
    eff = catalog.effective(pumpkin)
    assert (eff["usage"], eff["role"], eff["stages"], eff["frame"]) == ("growth_strip", "CROP", 5, [16, 32])  # fmt: skip
    assert eff["tags"] == ["crop", "farm_kit", "grown_from:ranch.crops.pumpkin_16x16"]
    with (
        Image.open(staging / pumpkin.path) as strip,
        Image.open(SYNTH / "ranch" / "crops" / "pumpkin_16x16.png") as ripe,
    ):
        assert strip.size == (80, 32)
        assert _png(strip.crop((64, 16, 80, 32))) == _png(ripe.convert("RGBA"))
    assert not [t for t in cat.tilesets for s in t.sources if s["asset"].startswith(farm_kit.KIT_PACK)]  # fmt: skip
    # without the pack's files a strip cannot be made; the stand-ins still are
    bare = _catalog(SYNTH / "ranch")
    assert farm_kit.add(bare, 16, tmp_path / "bare")[0] == lacking


def test_a_tag_alone_is_not_the_role(tmp_path: Path) -> None:
    cat = _catalog(SYNTH / "ranch")
    hoe = cat.asset("ranch.tools.hoe_16x16")
    hoe.overrides["role"] = "ITEM"  # still tagged tool
    assert "hoe" in [s.name for s in farm_kit.lacking(cat)], "the recipes look for the role"
    for asset in cat.assets:
        if catalog.effective(asset).get("role") == "ANIMAL":
            asset.overrides["role"] = "NPC"
    assert "hen" in [s.name for s in farm_kit.lacking(cat)]
    # with one crop that grows the three drawn ones are added; a pack's own is kept
    for name in ("corn_16x32_8frames", "tomato_16x32_12frames", "pumpkin_16x16"):
        gone = cat.asset(f"ranch.crops.{name}")
        gone.overrides["role"] = "NONE"
        gone.status = "UNUSED"
    assert farm_kit.growing(cat) == 1
    assert [s.name for s in farm_kit.lacking(cat)][:3] == ["turnip", "carrot", "berry"]


def test_only_a_farming_pack_gets_the_roles() -> None:
    assert set(labels.ROLE_INFO) >= ROLES and set(asset_detail.ROLES) >= ROLES
    assert all(mapping.PLAUSIBLE_USAGE[r] for r in ROLES)
    cat = catalog.Catalog()
    for n, role in enumerate(sorted(ROLES)):
        cat.assets.append(
            catalog.Asset(
                f"p.a{n}",
                "p",
                f"assets/packs/p/a{n}.png",
                "0" * 64,
                "image",
                "AUTO_DETECTED",
                {"usage": "sprite", "role": role},
                {"role": role},
            )
        )
    schema.validate("catalog", cat.to_json())
    for name in ("basic16", "mixed", "platformer", "strips", "gunner", "shooter", "racer"):
        found = {catalog.effective(a).get("role") for a in _catalog(SYNTH / name).assets}
        assert not found & ROLES, name
    multi = _roles(_catalog(SYNTH / "multi_engine"))
    assert multi["corn_16x32_8frames.png"] == multi["wheat_growth_16x32_5frames.png"] == "CROP"
    assert {r for n, r in multi.items() if n.startswith("cow_01")} == {"ANIMAL"}


def test_an_axe_and_a_hen_outside_a_farming_pack_stay_what_they_were(tmp_path: Path) -> None:
    pack = tmp_path / "dungeon"
    for name in ("weapons/axe.png", "tools/water.png", "enemies/chicken_walk_down_16x16_4frames.png"):  # fmt: skip
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        width = 64 if "4frames" in name else 16
        image = Image.new("RGBA", (width, 16), (0, 0, 0, 0))
        for i in range(width // 16):
            image.paste((90 + 30 * i, 80, 60, 255), (i * 16 + 3, 3 + i, i * 16 + 12, 14))
        image.save(pack / name)
    assert not set(_roles(_catalog(pack)).values()) & ROLES


# ----------------------------------------------------------------------------- sounds


def test_the_sound_slots_of_a_farm() -> None:
    own = [s.key for s in sound_slots.ARCHETYPE_SLOTS["farm"]]
    assert own == ["sfx_hoe", "sfx_water", "sfx_plant", "sfx_harvest", "sfx_sell", "sfx_animal",
                   "sfx_rooster", "music_spring", "music_summer", "music_autumn", "music_winter",
                   "music_night"]  # fmt: skip
    keys = sound_slots.slot_keys("farm")
    assert keys == sound_slots.SLOT_KEYS + tuple(own) and len(set(keys)) == len(keys)
    assert all(sound_slots.is_valid_name(k) for k in keys)
    assert all(s.label and s.help and s.tokens for s in sound_slots.ARCHETYPE_SLOTS["farm"])
    assert sound_slots.slot_keys("turn_based") == sound_slots.SLOT_KEYS, "as before"
    assert sound_slots.is_custom("sfx_hoe", "arpg") and not sound_slots.is_custom("sfx_hoe", "farm")


def test_the_slots_defaults_from_the_packs_file_names(tmp_path: Path) -> None:
    # the ranch has no sound: every slot of a farm is silent
    assert sound_slots.default_sounds(_catalog(SYNTH / "ranch"), "farm") == {}
    basic = _catalog(SYNTH / "audio_basic")
    assert sound_slots.default_sounds(basic, "farm") == sound_slots.default_sounds(basic)
    # the ranch with sounds named the way a farming pack names them
    pack = tmp_path / "ranch"
    shutil.copytree(SYNTH / "ranch", pack)
    names = ("sfx/hoe_dig", "sfx/watering_can", "sfx/plant_seed", "sfx/harvest", "sfx/sell_coins",
             "sfx/hen_cluck", "sfx/rooster", "music/spring_day", "music/winter_snow",
             "music/night")  # fmt: skip
    for name in names:
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(pack / f"{name}.wav"), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(1)
            out.setframerate(2000)
            out.writeframes(bytes(2000 if name.startswith("sfx") else 40000))
    cat = _catalog(pack)
    farm = sound_slots.default_sounds(cat, "farm")
    own = {s.key for s in sound_slots.ARCHETYPE_SLOTS["farm"]}
    got = {k: v.rsplit(".", 1)[-1] for k, v in farm.items() if k in own}
    assert got == {
        "sfx_hoe": "hoe_dig",
        "sfx_water": "watering_can",
        "sfx_plant": "plant_seed",
        "sfx_harvest": "harvest",
        "sfx_sell": "sell_coins",
        "sfx_animal": "hen_cluck",
        "sfx_rooster": "rooster",
        "music_spring": "spring_day",
        "music_winter": "winter_snow",
        "music_night": "night",
    }, "summer and autumn have no music of their own: they stay empty"
    assert "sfx_hoe" not in sound_slots.default_sounds(cat, "arpg")
    assert sound_slots.resolve_sounds(cat, {}, "farm")["sfx_rooster"] == farm["sfx_rooster"]
