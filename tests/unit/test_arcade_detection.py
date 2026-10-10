"""T16.02: what detection knows for the arcade kinds: rotation sheets, the words of a shoot 'em
up, a run and gun and a racing pack, and what kind of pack a pack is."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from rpggen.core import archive, catalog, classifier, inventory
from rpggen.core.analyzer import frames, image_facts

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _ring(
    headings: int,
    cell: tuple[int, int] = (32, 32),
    clockwise: bool = True,
    start: float = 0.0,
    long_side: float = 0.42,
) -> Image.Image:
    """An arrow-shaped thing in ``headings`` views; ``start`` is the first view's turn."""
    w, h = cell
    img = Image.new("RGBA", (headings * w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    half_w, length = min(w, h) * 0.2, min(w, h) * long_side
    shape = [(-half_w, -length * 0.5), (0, -length), (half_w, -length * 0.5), (half_w, length), (-half_w, length)]  # fmt: skip
    for k in range(headings):
        turn = start + (k if clockwise else -k) / headings
        cos, sin = math.cos(turn * 2 * math.pi), math.sin(turn * 2 * math.pi)
        cx, cy = k * w + w / 2 - 0.25, h / 2 - 0.25
        d.polygon(
            [(round(cx + x * cos - y * sin), round(cy + x * sin + y * cos)) for x, y in shape],
            fill=(200, 60, 60, 255),
        )
    return img


def _mask(image: Image.Image) -> np.ndarray:
    return image_facts.occupancy(np.asarray(image.convert("RGBA")))


@pytest.mark.parametrize("headings", [8, 12, 16, 24, 32])
def test_a_rotation_sheet_is_told_with_its_number_of_headings(headings: int) -> None:
    ring = frames.heading_ring(_mask(_ring(headings)))
    assert ring is not None and ring.headings == headings and ring.frame == (32, 32)
    assert ring.order == "up_cw" and ring.score > 0.5


def test_the_cells_need_not_be_square_and_the_order_is_read() -> None:
    wide = frames.heading_ring(_mask(_ring(16, cell=(46, 54))))
    assert wide is not None and (wide.headings, wide.frame) == (16, (46, 54))
    counter = frames.heading_ring(_mask(_ring(16, clockwise=False)))
    assert counter is not None and counter.order == "up_ccw"
    sideways = frames.heading_ring(_mask(_ring(16, start=0.25)))
    assert sideways is not None and sideways.order == "right_cw"


def test_the_racer_cars_are_rotation_sheets() -> None:
    for name in ("player_car", "rival_car_1", "rival_car_2", "rival_car_3"):
        image = Image.open(SYNTH / "racer" / "cars" / f"{name}.png")
        ring = frames.heading_ring(_mask(image))
        assert ring is not None and (ring.headings, ring.frame, ring.order) == (
            16,
            (24, 24),
            "up_cw",
        )


@pytest.mark.parametrize(
    "path",
    [
        "strips/hero_walk_down.png",  # a walk cycle: its frames fit each other best unturned
        "platformer/characters/hero_run.png",
        "shooter/ships/player_ship.png",  # three frames of a ship that banks
        "shooter/fx/explosion_6frames.png",
        "lpc_like/characters/body.png",  # a four-direction walk sheet
        "basic16/characters/hero.png",
        "racer/tiles/road.png",
    ],
)
def test_an_animation_or_a_tile_sheet_is_no_rotation_sheet(path: str) -> None:
    assert frames.heading_ring(_mask(Image.open(SYNTH / path))) is None


def test_a_round_thing_and_an_empty_cell_are_no_ring() -> None:
    discs = Image.new("RGBA", (16 * 24, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(discs)
    for k in range(16):
        d.ellipse([k * 24 + 3, 3, k * 24 + 20, 20], fill=(40, 40, 44, 255))
    assert frames.heading_ring(_mask(discs)) is None, "turned or not, a tyre looks the same"
    gap = _ring(16)
    ImageDraw.Draw(gap).rectangle([5 * 32, 0, 6 * 32 - 1, 31], fill=(0, 0, 0, 0))
    assert frames.heading_ring(_mask(gap)) is None
    assert frames.heading_ring(np.zeros((32, 512), dtype=bool)) is None


# ----------------------------------------------------------------------------- words


@pytest.mark.parametrize(
    ("path", "tags"),
    [
        ("ships/player_ship.png", ["ship"]),
        ("sprites/spaceship_red.png", ["ship"]),
        ("fighter_jet.png", ["ship"]),
        ("bullets/laser_blue.png", ["bullet"]),
        ("weapons/missile.png", ["bullet"]),
        ("fx/explosion_big.png", ["explosion"]),
        ("meteor_small.png", ["asteroid"]),
        ("pickups/power_up.png", ["powerup"]),
        ("pickups/weapon_pickup_spread.png", ["powerup"]),
        ("capsule.png", ["powerup"]),
        ("enemies/trooper_walk.png", ["soldier"]),
        ("machinegun.png", ["gun"]),
        ("laser_gun.png", ["bullet", "gun"]),
        ("grenade.png", ["grenade"]),
        ("cannon_turret.png", ["turret"]),
        ("grapple_hook.png", ["grapple"]),
        ("Cars/Classic_Bug/Classic_Bug_red.png", ["car"]),
        ("Bikes/Iron_Chopper/Iron_Chopper.png", ["bike"]),
        ("kart.png", ["car"]),
        ("Tilesets/race_track_1.png", ["road"]),
        ("dirt_track.png", ["road"]),
        ("start_line.png", ["finish"]),
        ("Enviroment/tire.png", ["tyre"]),
        ("barrier_red.png", ["tyre"]),
        ("oil.png", ["oil"]),
        ("speed_up.png", ["boost"]),
        ("VFX/Nitro/nitro.png", ["boost", "vfx"]),
        ("VFX/Smoke/smoke.png", ["vfx"]),
        ("Tilesets/grass_dirt_mix.png", ["mix"]),
        ("tiles/grass.png", []),
        ("characters/hero.png", []),
        ("objects/rock.png", []),  # a rock is scenery in every other kind of pack
        ("soundtrack.png", []),
        ("carpet.png", []),  # a word inside a word is no word
    ],
)
def test_the_words_of_the_arcade_kinds(path: str, tags: list[str]) -> None:
    assert classifier.arcade_tags(path) == tags
    assert set(tags) <= classifier.ARCADE_TAGS


def _catalog(pack: Path) -> catalog.Catalog:
    opened = archive.open_pack(pack, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _tags(cat: catalog.Catalog, name: str) -> list[str]:
    asset = next(a for a in cat.assets if a.path.endswith("/" + name))
    return list(catalog.effective(asset).get("tags") or [])


def test_the_racer_pack_is_a_racing_pack_with_its_cars_in_sixteen_headings() -> None:
    cat = _catalog(SYNTH / "racer")
    assert cat.packs[0].warnings == [catalog.VIEW_RACING]
    for asset in cat.assets:
        eff = catalog.effective(asset)
        if "/cars/" in asset.path:
            assert (eff["usage"], eff["headings"], eff["heading_order"]) == ("sprite", 16, "up_cw")
            assert eff["frame"] == [24, 24] and eff["origin"] == [12, 23] and "car" in eff["tags"]
            assert "animations" not in eff, "a rotation sheet is not an animation"
        else:
            assert "headings" not in eff
    assert _tags(cat, "road.png") == ["road"] and _tags(cat, "oil.png") == ["oil"]
    assert _tags(cat, "tyre.png") == ["tyre"] and _tags(cat, "boost.png") == ["boost"]


def test_the_shooter_pack_is_a_shooter_pack() -> None:
    cat = _catalog(SYNTH / "shooter")
    assert cat.packs[0].warnings == [catalog.VIEW_SHMUP]
    assert _tags(cat, "player_ship.png") == ["ship"] and _tags(cat, "bullet.png") == ["bullet"]
    assert _tags(cat, "explosion_6frames.png") == ["explosion"]
    assert _tags(cat, "asteroid_1.png") == ["asteroid"]
    # in such a pack a capsule is a power-up, not an ability of a metroidvania
    assert _tags(cat, "capsule_1.png") == ["powerup"]
    assert _tags(cat, "space_far.png") == ["parallax:1"]


def test_the_gunner_pack_is_a_side_view_pack_and_older_packs_are_what_they_were() -> None:
    cat = _catalog(SYNTH / "gunner")
    assert catalog.VIEW_SIDE in cat.packs[0].warnings
    assert not {catalog.VIEW_SHMUP, catalog.VIEW_RACING} & set(cat.packs[0].warnings)
    assert _tags(cat, "soldier_idle.png") == ["soldier"] and _tags(cat, "turret.png") == ["turret"]
    assert _tags(cat, "grapple_hook.png") == ["grapple"]
    assert "powerup" in _tags(cat, "weapon_pickup_machinegun.png")
    for name in ("basic16", "mixed", "rpgmaker_like", "frames_export"):
        views = {w for w in _catalog(SYNTH / name).packs[0].warnings if w.startswith("view:")}
        assert views == set(), name
    platformer = _catalog(SYNTH / "platformer")
    assert catalog.VIEW_SIDE in platformer.packs[0].warnings
    assert "ability" in _tags(platformer, "powerup_orb_1.png"), "as before M16"


def test_a_few_such_words_do_not_make_a_pack_one(tmp_path: Path) -> None:
    pack = tmp_path / "rpg"
    for name in ("tiles/grass.png", "tiles/road.png", "props/cart.png", "items/rocket.png"):
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (16, 16), (90, 120, 60, 255)).save(pack / name)
    assert {w for w in _catalog(pack).packs[0].warnings if w.startswith("view:")} == set()
