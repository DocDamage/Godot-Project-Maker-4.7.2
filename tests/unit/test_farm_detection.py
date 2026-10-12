"""T17.01: detection for the farm. The farm's words as tags, growth strips told from
animations, sheets drawn once a season as one group, the pack view, and the ``ranch`` pack."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import archive, catalog, classifier, explain, inventory, labels, pack_sniff
from rpggen.core.adapters import strips
from rpggen.core.terrain import blob

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(source: Path) -> tuple[catalog.Catalog, list]:
    opened = archive.open_pack(source, set())
    cat, issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat, list(issues)


def _by_path(cat: catalog.Catalog) -> dict[str, catalog.Asset]:
    return {a.path.split("/", 3)[-1]: a for a in cat.assets}


def _inv(*paths: str) -> SimpleNamespace:
    return SimpleNamespace(files=[SimpleNamespace(path=p) for p in paths])


# ------------------------------------------------------------------------------------ tags


@pytest.mark.parametrize(
    ("path", "tags"),
    [
        ("crops/corn_16x32_8frames.png", ["crop"]),
        ("farm/turnip.png", ["crop"]),
        ("Plants/bush.png", ["crop"]),
        ("vegetables/01.png", ["crop"]),
        ("fruit/apple.png", ["crop"]),
        ("items/seeds_corn.png", ["crop", "seed"]),
        ("trees/sapling.png", ["seed"]),
        ("tiles/soil.png", ["soil"]),
        ("tiles/farmland.png", ["soil"]),
        ("tiles/dirt_tilled.png", ["soil"]),
        ("tiles/plowed.png", ["soil"]),
        ("tiles/soil_watered.png", ["watered"]),
        ("tiles/wet_soil.png", ["watered"]),
        ("tools/hoe.png", ["tool"]),
        ("icons/shovel.png", ["tool"]),
        ("icons/watering_can.png", ["tool"]),
        ("tools/water_16x16.png", ["tool"]),
        ("icons/sickle.png", ["tool"]),
        ("icons/scythe.png", ["tool"]),
        ("weapons/axe.png", ["tool"]),
        ("icons/pickaxe.png", ["tool"]),
        ("icons/fishing_rod.png", ["fish", "tool"]),
        ("animals/cows/cow_01_brown_move_down_32x32_4frames.png", ["animal"]),
        ("farm/chicken.png", ["animal"]),
        ("farm/hen_walk.png", ["animal"]),
        ("farm/sheep.png", ["animal"]),
        ("farm/pig.png", ["animal"]),
        ("farm/goat.png", ["animal"]),
        ("farm/duck.png", ["animal"]),
        ("farm/horse.png", ["animal"]),
        ("items/egg.png", ["product"]),
        ("items/milk.png", ["product"]),
        ("items/wool.png", ["product"]),
        ("buildings/coop.png", ["coop"]),
        ("buildings/barn.png", ["barn"]),
        ("autotiles/03_fence.png", ["fence"]),
        ("props/shipping_bin.png", ["bin"]),
        ("props/crate.png", ["bin"]),
        ("weather/rain_64x64_3frames.png", ["weather"]),
        ("overlays/snow.png", ["weather"]),
        ("overlays/storm.png", ["weather"]),
        ("fish/trout.png", ["fish"]),
        ("forage/mushroom.png", ["forage"]),
        ("crops/wheat_growth.png", ["crop", "growth"]),
        ("tiles/winter/grass.png", ["season:winter"]),
        ("Summer/tiles/trees.png", ["season:summer"]),
        ("tiles/fall/grass.png", ["season:autumn"]),
        ("tiles/Spring/grass.png", ["season:spring"]),
        ("trees/oak_autumn.png", ["season:autumn"]),
    ],
)
def test_the_words_of_a_farm_are_tags(path: str, tags: list[str]) -> None:
    assert classifier.farm_tags(path) == tags


@pytest.mark.parametrize(
    "path",
    [
        "tiles/water.png",  # what a river is made of: a tool in a folder of tools only
        "sprites/hero_fall.png",  # what a hero does, not a season
        "props/spring.png",  # something to jump on
        "enemies/rodent.png",
        "characters/hero_walk_down.png",
        "ui/cabinet.png",
    ],
)
def test_words_that_mean_something_else_are_no_farm_tag(path: str) -> None:
    assert classifier.farm_tags(path) == []


def test_every_farm_tag_has_a_case_and_none_is_an_older_tag() -> None:
    assert set(classifier.FARM_TAGS) == {
        "crop", "seed", "soil", "watered", "tool", "animal", "product", "coop", "barn", "fence",
        "bin", "weather", "fish", "forage", "growth",
    }  # fmt: skip
    older = {tag for tag, _w in classifier.SIDE_TAG_WORDS} | set(classifier.ARCADE_TAGS)
    assert not older & classifier.FARM_TAGS


def test_snow_on_a_tile_sheet_is_ground_not_weather() -> None:
    facets: dict = {"usage": "tiles", "role": "GROUND"}
    catalog._suggest_tags(facets, "tiles/snow.png")
    assert facets["tags"] == ["surface:snow"]
    overlay: dict = {"usage": "sprite", "role": "EFFECT"}
    catalog._suggest_tags(overlay, "weather/snow.png")
    assert overlay["tags"] == ["weather"]


# ---------------------------------------------------------------------------------- seasons


@pytest.mark.parametrize(
    ("path", "key", "season"),
    [
        ("tiles/winter/grass_16x16.png", "tiles/grass_16_x_16", "winter"),
        ("tiles/spring/grass_16x16.png", "tiles/grass_16_x_16", "spring"),
        ("tiles/Fall/grass_16x16.png", "tiles/grass_16_x_16", "autumn"),
        ("trees/oak_autumn.png", "trees/oak", "autumn"),
        ("trees/oak_fall.png", "trees/oak", "autumn"),
        ("trees/oak.png", "trees/oak", ""),
        ("Winter Tiles/grass.png", "tiles/grass", "winter"),
        ("props/spring.png", "props/", "spring"),
    ],
)
def test_season_key(path: str, key: str, season: str) -> None:
    assert classifier.season_key(path) == (key, season)


def test_a_season_in_a_file_name_needs_no_folder_but_spring_and_fall_do() -> None:
    assert classifier.season_of("trees/oak_winter.png") == "winter"
    assert classifier.season_of("trees/oak_spring.png") is None
    assert classifier.season_of("trees/oak_fall.png") is None
    assert classifier.season_of("fall/trees/oak.png") == "autumn"
    assert classifier.season_of("trees/oak.png") is None


def _sheet(colour: tuple[int, int, int], size: tuple[int, int] = (64, 32)) -> Image.Image:
    img = Image.new("RGBA", size)
    for x in range(size[0]):
        for y in range(size[1]):
            shade = ((x // 16) * 9 + (y // 16) * 17) % 40 + (x % 16) * 2
            img.putpixel((x, y), (min(255, colour[0] + shade), colour[1], colour[2], 255))
    return img


def test_sheets_drawn_once_a_season_are_one_group(tmp_path: Path) -> None:
    pack = tmp_path / "seasons"
    colours = {"spring": (90, 170, 80), "summer": (60, 150, 60), "fall": (180, 130, 60)}
    for season, colour in colours.items():
        (pack / "tiles" / season).mkdir(parents=True)
        _sheet(colour).save(pack / "tiles" / season / "grass.png")
    (pack / "trees").mkdir()
    for n, name in enumerate(("oak", "oak_spring", "oak_fall", "pine", "spring")):
        _sheet((40 + n * 30, 120, 60), (16, 32)).save(pack / "trees" / f"{name}.png")
    cat, _issues = _catalog(pack)
    assets = _by_path(cat)
    grass = {s: assets[f"tiles/{s}/grass.png"] for s in colours}
    assert catalog.season_groups(cat)[grass["spring"].id] == {
        "spring": grass["spring"].id,
        "summer": grass["summer"].id,
        "autumn": grass["fall"].id,
    }
    assert "season:autumn" in grass["fall"].detected["tags"]
    assert f"variant_of:{grass['spring'].id}" in grass["summer"].detected["tags"]
    assert not [t for t in grass["spring"].detected["tags"] if t.startswith("variant_of:")]
    # one card in the audit: the group is what the colour groups of T16.21 are
    assert catalog.colour_groups(cat)[grass["spring"].id] == [grass["fall"].id, grass["summer"].id]
    assert [catalog.colour_name(a) for a in catalog.colour_group(cat, grass["fall"].id)] == [
        "spring", "autumn", "summer",
    ]  # fmt: skip
    assert "drawn for another season" in explain.why(grass["summer"])
    # the sheet without a season is the first of its group; spring and fall in a file name
    # are seasons beside it
    oak = assets["trees/oak.png"]
    assert catalog.season_groups(cat)[oak.id] == {
        "": oak.id,
        "autumn": assets["trees/oak_fall.png"].id,
        "spring": assets["trees/oak_spring.png"].id,
    }
    alone = (assets["trees/pine.png"], assets["trees/spring.png"])
    for asset in alone:
        assert not [t for t in asset.detected.get("tags", []) if t.startswith("season:")]
    schema.validate("catalog", cat.to_json())


# ----------------------------------------------------------------------------- growth strips


@pytest.mark.parametrize(
    ("path", "frame", "stages", "evidence"),
    [
        ("crops/corn_16x32_8frames.png", [16, 32], 8, "name"),
        ("sprites/wheat_growth_16x16_5frames.png", [16, 16], 5, "name"),
        ("farm/crop_3.png", [16, 16], 4, "name"),
        ("crops/corn_idle_16x32_8frames.png", [16, 32], 8, None),  # an action: an animation
        ("crops/corn_down_16x32_8frames.png", [16, 32], 8, None),  # a direction
        ("hero/hero_idle_16x32_8frames.png", [16, 32], 8, None),
        ("crops/a_16x32_4frames.png", [16, 32], 4, "size"),  # its folder and its shape
        ("Plants/01.png", [16, 32], 5, "size"),
        ("seeds/a.png", [16, 24], 3, "size"),
        ("crops/a_16x16_4frames.png", [16, 16], 4, None),  # not taller than wide
        ("crops/a_16x32_2frames.png", [16, 32], 2, None),  # two cells are not several
        ("props/flag_16x32_4frames.png", [16, 32], 4, None),
        ("plants/plant_16x16_4frames.png", [16, 16], 4, None),  # a plant that sways
    ],
)
def test_growth_evidence(path: str, frame: list[int], stages: int, evidence: str | None) -> None:
    assert classifier.growth_evidence(path, frame, stages) == evidence


def test_only_a_plain_one_row_strip_can_be_a_growth_strip() -> None:
    row = {"frames": [[0, 0], [1, 0], [2, 0]], "fps": 4.0, "loop": True}
    plain = {"usage": "sprite", "frame": [16, 32], "animations": {"idle_down": dict(row)}}
    assert strips.growth_stages(plain) == 3
    assert strips.growth_stages({**plain, "animations": {"walk_down": row}}) == 0
    assert strips.growth_stages({**plain, "animations": {"idle_down": row, "idle_up": row}}) == 0
    assert strips.growth_stages({**plain, "headings": 16}) == 0
    assert strips.growth_stages({**plain, "usage": "tiles"}) == 0
    second_row = {"idle_down": {**row, "frames": [[0, 1], [1, 1]]}}
    assert strips.growth_stages({**plain, "animations": second_row}) == 0
    assert strips.growth_stages({"usage": "sprite", "frame": [16, 16]}) == 0
    strips.as_growth_strip(plain)
    assert plain == {"usage": "growth_strip", "frame": [16, 32], "stages": 3}


def _strip(frames: int, colour: tuple[int, int, int], fw: int = 16, fh: int = 32) -> Image.Image:
    img = Image.new("RGBA", (frames * fw, fh))
    for i in range(frames):
        height = 4 + i * (fh - 6) // max(1, frames - 1)
        img.paste((*colour, 255), (i * fw + 6, fh - height, i * fw + 10, fh))
    return img


def test_a_growth_strip_against_an_idle_animation_of_the_same_size(tmp_path: Path) -> None:
    pack = tmp_path / "field"
    (pack / "crops").mkdir(parents=True)
    (pack / "plants").mkdir()
    (pack / "npc").mkdir()
    _strip(6, (60, 160, 60)).save(pack / "crops" / "corn_16x32_6frames.png")
    _strip(6, (160, 60, 60)).save(pack / "npc" / "scarecrow_idle_16x32_6frames.png")
    _strip(6, (60, 60, 160)).save(pack / "crops" / "corn_idle_16x32_6frames.png")
    _strip(4, (160, 160, 60)).save(pack / "plants" / "a_16x32_4frames.png")
    cat, issues = _catalog(pack)
    assets = _by_path(cat)
    corn = assets["crops/corn_16x32_6frames.png"]
    eff = catalog.effective(corn)
    assert eff["usage"] == "growth_strip" and eff["stages"] == 6 and "animations" not in eff
    assert eff["frame"] == [16, 32] and eff["grid"]["cell"] == [16, 32]
    assert eff["role"] == "CROP" and "crop" in eff["tags"]
    assert corn.status == "AUTO_DETECTED", "its name says what it is: no review"
    for path in ("npc/scarecrow_idle_16x32_6frames.png", "crops/corn_idle_16x32_6frames.png"):
        idle = catalog.effective(assets[path])
        assert idle["usage"] == "sprite" and len(idle["animations"]["idle_down"]["frames"]) == 6
        assert "stages" not in idle
    by_size = assets["plants/a_16x32_4frames.png"]
    assert catalog.effective(by_size)["usage"] == "growth_strip"
    assert catalog.effective(by_size)["stages"] == 4
    assert by_size.status == "NEEDS_REVIEW", "told by its folder and its size: offered for review"
    assert "ASSET-034" not in [i.code for i in issues], "no farming pack: no note"
    schema.validate("catalog", cat.to_json())
    assert labels.usage_label("growth_strip") == "Growth strip"


# -------------------------------------------------------------------------------- pack view


def test_pack_view_farm_from_words() -> None:
    farm = _inv("crops/corn.png", "animals/cow.png", "tiles/soil.png")
    assert classifier.pack_view(farm) == "farm"
    assert classifier.farm_view(_inv("crops/corn.png", "crops/wheat.png", "animals/hen.png"))
    # three names in one of the three ways are a pack with a few crops, or a few animals
    assert not classifier.farm_view(_inv("items/corn.png", "items/carrot.png", "items/tomato.png"))
    assert not classifier.farm_view(_inv("npc/cow.png", "npc/pig.png", "npc/duck.png", "a/b.png"))
    assert classifier.pack_view(_inv("items/corn.png", "npc/cow.png")) == "top"
    # words every pack has say nothing
    assert (
        classifier.pack_view(_inv("plants/tree.png", "props/crate.png", "npc/horse.png")) == "top"
    )


def test_pack_view_farm_counts_a_growth_strip_and_gives_way_to_the_other_views() -> None:
    growth = {"usage": "growth_strip", "stages": 5}
    assert classifier.pack_view(_inv("sprites/a.png", "farm/corn.png"), [growth]) == "farm"
    assert classifier.pack_view(_inv("sprites/a.png"), [growth]) == "top", "one sign is not enough"
    side = ("platformer/corn.png", "platformer/cow.png", "platformer/soil.png")
    assert classifier.pack_view(_inv(*side)) == "side"
    racing = ("cars/car.png", "roads/road.png", "props/tyre.png", "crops/corn.png", "farm/cow.png",
              "tiles/soil.png")  # fmt: skip
    assert classifier.pack_view(_inv(*racing)) == "racing"


@pytest.mark.parametrize(
    "pack", ["basic16", "mixed", "strips", "platformer", "shooter", "gunner", "racer"]
)
def test_the_older_packs_are_no_farming_packs(pack: str) -> None:
    opened = archive.open_pack(SYNTH / pack, set())
    assert classifier.pack_view(inventory.build_inventory(opened)) != "farm"


# -------------------------------------------------------------------------------- the ranch


@pytest.fixture(scope="module")
def ranch() -> tuple[catalog.Catalog, list]:
    return _catalog(SYNTH / "ranch")


def test_the_ranch_is_a_farming_pack(ranch: tuple[catalog.Catalog, list]) -> None:
    cat, _issues = ranch
    assert catalog.VIEW_FARM in cat.packs[0].warnings
    assert catalog.pack_view(cat.packs[0]) == "top", (
        "the wizard of the older kinds asks side or top"
    )
    assert "view:farm" in pack_sniff.sniff(SYNTH / "ranch").marks
    schema.validate("catalog", cat.to_json())


def test_the_ranchs_crops_are_growth_strips_with_their_stages(
    ranch: tuple[catalog.Catalog, list],
) -> None:
    cat, issues = ranch
    assets = _by_path(cat)
    stages = {
        path.split("/")[-1].split("_")[0]: catalog.effective(asset).get("stages")
        for path, asset in assets.items()
        if catalog.effective(asset)["usage"] == "growth_strip"
    }
    assert stages == {"corn": 8, "wheat": 5, "tomato": 12}
    for name, count in stages.items():
        asset = assets[f"crops/{name}_16x32_{count}frames.png"]
        assert asset.status == "AUTO_DETECTED" and "animations" not in catalog.effective(asset)
    pumpkin = assets["crops/pumpkin_16x16.png"]
    assert catalog.effective(pumpkin)["usage"] == "sprite"
    notes = [i for i in issues if i.code == "ASSET-034"]
    assert [i.severity.value for i in notes] == ["info"] and pumpkin.id in notes[0].message


def test_the_ranchs_things_have_their_tags(ranch: tuple[catalog.Catalog, list]) -> None:
    cat, _issues = ranch
    assets = _by_path(cat)

    def tags(path: str) -> set[str]:
        return set(catalog.effective(assets[path]).get("tags") or [])

    assert "crop" in tags("crops/corn_16x32_8frames.png")
    for tool in ("hoe", "shovel", "water", "sickle"):
        assert "tool" in tags(f"tools/{tool}_16x16.png"), tool
    assert "soil" in tags("autotiles/01_soil_tilled.png")
    assert tags("autotiles/02_soil_watered.png") >= {"watered"}
    assert "soil" not in tags("autotiles/02_soil_watered.png")
    assert "fence" in tags("autotiles/03_fence.png")
    assert "weather" in tags("weather/rain_64x64_3frames.png")
    assert "coop" in tags("buildings/coop.png") and "bin" in tags("props/shipping_bin.png")
    cows = "animals/cows/cow_01"
    move = {c: assets[f"{cows}/{c}/move/cow_01_{c}_move_down_32x32_4frames.png"] for c in ("black", "brown", "white")}  # fmt: skip
    for asset in move.values():
        assert "animal" in asset.detected["tags"]
    assert [a.id for a in catalog.colour_variants(cat, move["black"].id)] == [
        move["brown"].id,
        move["white"].id,
    ]
    hen = assets["animals/chickens/hen_01/white/sleep/hen_01_white_sleep_16x16_2frames.png"]
    assert sorted(catalog.effective(hen)["animations"]) == ["sleep_down"]
    farmer = catalog.effective(assets["characters/farmer/farmer_walk_down_16x16_4frames.png"])
    assert farmer["role"] == "PLAYER" and len(farmer["animations"]) == 4


def test_the_ranchs_ground_comes_once_a_season_and_its_sheets_are_terrains(
    ranch: tuple[catalog.Catalog, list],
) -> None:
    cat, issues = ranch
    assets = _by_path(cat)
    grass = {s: assets[f"tiles/{s}/grass_16x16.png"] for s in classifier.SEASONS}
    assert catalog.season_groups(cat) == {
        grass["spring"].id: {s: grass[s].id for s in classifier.SEASONS}
    }
    for season, asset in grass.items():
        eff = catalog.effective(asset)
        assert eff["usage"] == "tiles" and eff["role"] == "GROUND"
        assert f"season:{season}" in eff["tags"]
    layouts = {
        path.split("/")[-1]: catalog.effective(asset)["terrain_proposal"]["layout"]
        for path, asset in assets.items()
        if blob.has_proposal(asset)
    }
    assert layouts == {
        "01_soil_tilled.png": blob.BLOB47_GODOT,
        "02_soil_watered.png": blob.BLOB47_GODOT,
        "03_fence.png": blob.SIDES16_GODOT,
    }
    fence = catalog.effective(assets["autotiles/03_fence.png"])
    assert fence["role"] == "WALL" and len(fence["terrain_proposal"]["tile_overrides"]) == 16
    assert "TILE-006" not in [i.code for i in issues]


# ------------------------------------------------------ a character using a tool (T17.10)


@pytest.mark.parametrize(
    ("path", "who", "tool"),
    [
        ("characters/farmer/farmer_hoe_down_16x16_3frames.png", ["farmer"], "hoe"),
        ("characters/farmer/farmer_water_down_16x16_3frames.png", ["farmer"], "water"),
        ("player/farmer_watering_can_left.png", ["farmer"], "water"),
        ("player/old_farmer_scythe_up_4frames.png", ["old", "farmer"], "sickle"),
        ("player/farmer_sickle.png", ["farmer"], "sickle"),
        ("player/farmer_axe_right.png", ["farmer"], "axe"),
        ("player/farmer_rod_down.png", ["farmer"], "rod"),
        ("player/farmer_fish_down.png", ["farmer"], "rod"),
        ("characters/farmer/farmer_walk_down_16x16_4frames.png", ["farmer"], ""),
        ("characters/farmer/farmer_idle.png", ["farmer"], ""),
        ("animals/cow_01_brown_move_down_32x32_4frames.png", ["cow", "brown"], ""),
        ("tools/hoe_16x16.png", [], "hoe"),
    ],
)
def test_whose_strip_it_is_and_which_tool_it_shows(path: str, who: list[str], tool: str) -> None:
    assert classifier.character_words(path) == (who, tool)
    assert set(classifier.USE_ANIM_WORDS.values()) == {"hoe", "water", "sickle", "axe", "rod"}


def test_the_farmer_using_a_tool_is_an_animation_of_the_farmer_not_a_villager(
    ranch: tuple[catalog.Catalog, list],
) -> None:
    cat, _issues = ranch
    assets = _by_path(cat)
    farmer = assets["characters/farmer/farmer_walk_down_16x16_4frames.png"]
    for tool in ("hoe", "water"):
        strip = assets[f"characters/farmer/farmer_{tool}_down_16x16_3frames.png"]
        eff = catalog.effective(strip)
        assert (eff["role"], strip.status) == ("NONE", "UNUSED"), tool
        assert "roles_alt" not in eff and eff["usage"] == "sprite"
        assert {f"use_anim:{tool}", f"of:{farmer.id}", "unused_because:use_anim"} <= set(
            eff["tags"]
        )
        assert len(eff["animations"]["idle_down"]["frames"]) == 3, "its frames stay read"
        why = explain.why(strip)
        assert why.startswith("unused: an animation of characters/farmer/farmer_walk_down")
        assert f"using a tool ({tool})" in why and "Give it a role" in why
    assert catalog.effective(farmer)["role"] == "PLAYER"
    people = [a.id for a in cat.assets if catalog.effective(a).get("role") == "NPC"]
    assert people == [], "nobody of the ranch is a villager: its people are drawn or lent"
    # the hoe's icon is still the tool, and a tool word alone makes no animation of anybody
    assert catalog.effective(assets["tools/hoe_16x16.png"])["role"] == "TOOL"
    assert not [t for t in catalog.effective(assets["tools/hoe_16x16.png"])["tags"] if ":" in t]


def _person_strip(path: Path, frames: int, shade: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (16 * frames, 16), (0, 0, 0, 0))
    for i in range(frames):
        image.paste((shade, 90 + 20 * i, 60, 255), (i * 16 + 4, 2 + i, i * 16 + 12, 15))
    image.save(path)


def test_a_tool_strip_is_an_animation_only_of_a_character_beside_it_in_a_farming_pack(
    tmp_path: Path,
) -> None:
    def names(pack: Path) -> dict[str, tuple[str, list[str]]]:
        cat, _issues = _catalog(pack)
        return {
            a.path.rsplit("/", 1)[-1]: (
                catalog.effective(a)["role"],
                [t for t in catalog.effective(a).get("tags", []) if t.startswith(("use_", "of:"))],
            )
            for a in cat.assets
        }

    # a village pack with the same names is no farming pack: nothing changes
    village = tmp_path / "village"
    for name in ("hero_walk_down_16x16_4frames", "hero_axe_down_16x16_3frames"):
        _person_strip(village / "characters" / f"{name}.png", int(name[-7]), 120)
    plain = names(village)
    assert plain["hero_axe_down_16x16_3frames.png"][0] != "NONE"
    assert not plain["hero_axe_down_16x16_3frames.png"][1]
    # a farming pack: another character's tool strip, and a tool strip of nobody
    farm = tmp_path / "farm"
    (farm / "crops").mkdir(parents=True)
    for crop in ("corn", "wheat", "carrot"):
        _person_strip(farm / "crops" / f"{crop}_16x16_5frames.png", 5, 200)
    _person_strip(farm / "tiles" / "soil_tilled.png", 1, 90)
    people = farm / "characters"
    for name in ("farmer_walk_down_16x16_4frames", "farmer_axe_down_16x16_3frames",
                 "helper_walk_down_16x16_4frames", "helper_sickle_down_16x16_3frames",
                 "stranger_hoe_down_16x16_3frames"):  # fmt: skip
        _person_strip(people / f"{name}.png", int(name[-7]), 60 + 9 * len(name))
    cat, _issues = _catalog(farm)
    assert catalog.VIEW_FARM in cat.packs[0].warnings
    found = names(farm)
    assert found["farmer_axe_down_16x16_3frames.png"] == (
        "NONE",
        ["of:farm.characters.farmer_walk_down_16x16_4frames", "use_anim:axe"],
    )
    assert found["helper_sickle_down_16x16_3frames.png"] == (
        "NONE",
        ["of:farm.characters.helper_walk_down_16x16_4frames", "use_anim:sickle"],
    )
    assert found["stranger_hoe_down_16x16_3frames.png"][0] != "NONE", (
        "nobody beside it is called so"
    )
    assert not found["stranger_hoe_down_16x16_3frames.png"][1]
    assert found["farmer_walk_down_16x16_4frames.png"][0] == "PLAYER"
    schema.validate("catalog", cat.to_json())
