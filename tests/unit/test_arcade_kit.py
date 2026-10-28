"""T16.03: the drawn stand-ins of the arcade kinds, the new roles, what each kind requires and
its sound slots."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import (
    arcade_kit,
    archive,
    catalog,
    config,
    inventory,
    labels,
    mapping,
    orchestrator,
    requirements,
    sound_slots,
)
from rpggen.core.analyzer import frames, image_facts

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
KINDS = ("shmup", "run_and_gun", "racing")


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


def _cfg(source: Path, archetype: str) -> config.GeneratorConfig:
    ref = config.PackRef(source.stem, str(source), "0" * 64, "folder")
    return config.default_for("Arcade", [ref], archetype=archetype)


# ----------------------------------------------------------------------------- the pictures

PICTURES = {
    "bullet": (arcade_kit.bullet, lambda t: (t // 2, t // 2)),
    "laser": (arcade_kit.laser, lambda t: (t // 4, t)),
    "missile": (arcade_kit.missile, lambda t: (t // 2, t)),
    "explosion": (arcade_kit.explosion, lambda t: (6 * t, t)),
    "capsule": (arcade_kit.capsule, lambda t: (t, t)),
    "ship": (arcade_kit.ship, lambda t: (t * 3 // 2, t * 3 // 2)),
    "car": (arcade_kit.car, lambda t: (16 * (t * 3 // 2), t * 3 // 2)),
    "road": (arcade_kit.road, lambda t: (9 * t, t)),
    "hook": (arcade_kit.hook, lambda t: (t, t)),
    "chain": (arcade_kit.chain, lambda t: (t // 2, t // 2)),
}


@pytest.mark.parametrize("tile", [16, 32])
@pytest.mark.parametrize("name", sorted(PICTURES))
def test_every_stand_in_is_drawn_in_its_size_and_the_same_every_time(name: str, tile: int) -> None:
    draw, size = PICTURES[name]
    image = draw(tile)
    assert image.mode == "RGBA" and image.size == size(tile)
    assert np.asarray(image)[..., 3].any(), "something is drawn"
    assert _png(image) == _png(draw(tile)), "byte for byte, on every run"


@pytest.mark.parametrize("tile", [16, 32])
def test_the_weapon_icons_are_one_per_weapon_and_differ(tile: int) -> None:
    icons = {kind: _png(arcade_kit.weapon_icon(tile, kind)) for kind in arcade_kit.WEAPONS}
    assert len(set(icons.values())) == len(arcade_kit.WEAPONS) == 5
    assert arcade_kit.weapon_icon(tile, "laser").size == (tile, tile)
    with pytest.raises(ValueError, match="no such weapon"):
        arcade_kit.weapon_icon(tile, "banana")


@pytest.mark.parametrize("tile", [16, 32])
def test_the_drawn_car_is_a_rotation_sheet_and_the_explosion_six_frames(tile: int) -> None:
    car = arcade_kit.car(tile)
    ring = frames.heading_ring(image_facts.occupancy(np.asarray(car)))
    cell = tile * 3 // 2
    assert ring is not None and (ring.headings, ring.frame, ring.order) == (
        16,
        (cell, cell),
        "up_cw",
    )
    burst = np.asarray(arcade_kit.explosion(tile))[..., 3] > 0
    filled = [int(burst[:, i * tile : (i + 1) * tile].sum()) for i in range(6)]
    assert all(filled) and filled[0] < filled[2], "it grows"
    road = arcade_kit.road(tile)
    cells = {_png(road.crop((i * tile, 0, (i + 1) * tile, tile))) for i in range(9)}
    assert len(cells) == 9 == len(arcade_kit.ROAD_TILES), "nine different tiles"
    assert np.asarray(road)[..., 3].all(), "a road sheet has no hole"


def test_a_tile_size_that_is_too_small_is_drawn_at_eight() -> None:
    assert arcade_kit.ship(2).size == arcade_kit.ship(8).size == (12, 12)


# ----------------------------------------------------------------------------- the catalog


def test_a_plain_rpg_pack_as_a_shoot_em_up_passes_with_notes_only(tmp_path: Path) -> None:
    """The card's *Done when*."""
    pack = SYNTH / "basic16"
    cat = _catalog(pack)
    cfg = _cfg(pack, "shmup")
    issues = requirements.check(cat, cfg)
    assert not [i for i in issues if i.severity.value == "error"], [i.message for i in issues]
    notes = [i for i in issues if i.code == "ASSET-031"]
    assert {i.detail["role"] for i in notes} == {"PROJECTILE", "EXPLOSION", "POWERUP"}
    assert all(i.severity.value == "info" for i in notes)
    # the run draws them: the catalog has what the kind needs, with a note each
    made, stand_ins = orchestrator.add_run_made_assets(cat, cfg, [], tmp_path / "staging")
    assert list(made) == [] and stand_ins == [], "the note is the check's, once"
    schema.validate("catalog", cat.to_json())
    kit = {a.id: a for a in cat.assets if a.pack_id == arcade_kit.KIT_PACK}
    assert sorted(kit) == [f"rpggen_arcade_kit.{n}" for n in ("bullet", "capsule", "explosion")]
    burst = catalog.effective(kit["rpggen_arcade_kit.explosion"])
    assert burst["role"] == "EXPLOSION" and len(burst["animations"]["idle_down"]["frames"]) == 6
    assert burst["tags"] == ["arcade_kit", "explosion"] and burst["frame"] == [16, 16]
    assert (tmp_path / "staging" / "generated/arcade_kit/bullet.png").is_file()
    after = requirements.check(cat, cfg)  # the notes stay as long as the packs lack the things
    assert not [i for i in after if i.severity.value == "error"]
    assert [i.detail["role"] for i in after if i.code == "ASSET-031"] == [n.detail["role"] for n in notes]  # fmt: skip
    _names, own = arcade_kit.add(cat, "shmup", 16, tmp_path / "again")
    assert [i.file for i in own] == [f"generated/arcade_kit/{n}.png" for n in ("bullet", "explosion", "capsule")]  # fmt: skip


def test_a_pack_without_a_player_still_makes_a_shooter_and_a_racing_game(tmp_path: Path) -> None:
    pack = tmp_path / "tiles_only"
    (pack / "tiles").mkdir(parents=True)
    Image.new("RGBA", (64, 64), (60, 140, 70, 255)).save(pack / "tiles" / "grass.png")
    for kind, roles, names in (
        ("shmup", {"PLAYER", "PROJECTILE", "EXPLOSION", "POWERUP"}, ["bullet", "capsule", "explosion", "ship"]),
        ("racing", {"VEHICLE", "GROUND"}, ["car", "road"]),
    ):  # fmt: skip
        cat = _catalog(pack)
        cfg = _cfg(pack, kind)
        if kind == "racing":  # its grass is ground already: only the car is drawn
            roles, names = {"VEHICLE"}, ["car"]
        issues = requirements.check(cat, cfg)
        assert not [i for i in issues if i.severity.value == "error"], kind
        assert {i.detail["role"] for i in issues if i.code == "ASSET-031"} == roles
        orchestrator.add_run_made_assets(cat, cfg, [], tmp_path / kind)
        assert sorted(a.id.split(".")[-1] for a in cat.assets if a.pack_id == arcade_kit.KIT_PACK) == names  # fmt: skip
        schema.validate("catalog", cat.to_json())
    car = catalog.effective(cat.asset("rpggen_arcade_kit.car"))
    assert (car["role"], car["headings"], car["heading_order"], car["frame"]) == ("VEHICLE", 16, "up_cw", [24, 24])  # fmt: skip


def test_the_road_is_drawn_when_a_pack_has_no_ground_and_is_a_tile_set(tmp_path: Path) -> None:
    pack = tmp_path / "cars_only"
    (pack / "cars").mkdir(parents=True)
    arcade_kit.car(16).save(pack / "cars" / "my_car.png")
    cat = _catalog(pack)
    assert catalog.effective(cat.assets[0])["role"] == "VEHICLE"
    cfg = _cfg(pack, "racing")
    assert {i.detail["role"] for i in requirements.check(cat, cfg) if i.code == "ASSET-031"} == {
        "GROUND"
    }
    orchestrator.add_run_made_assets(cat, cfg, [], tmp_path / "staging")
    road = catalog.effective(cat.asset("rpggen_arcade_kit.road"))
    assert (
        road["usage"] == "tiles" and road["grid"]["cell"] == [16, 16] and road["role"] == "GROUND"
    )
    barrier = road["tile_overrides"][f"{arcade_kit.ROAD_TILES.index('barrier')},0"]
    assert barrier["collision"] == {"profile": "FULL"} and barrier["custom"] == {"road": "barrier"}
    assert any(src["asset"] == "rpggen_arcade_kit.road" for t in cat.tilesets for src in t.sources)
    schema.validate("catalog", cat.to_json())


def test_the_packs_own_things_win_and_a_second_run_draws_the_same(tmp_path: Path) -> None:
    cat = _catalog(SYNTH / "shooter")
    cfg = _cfg(SYNTH / "shooter", "shmup")
    assert arcade_kit.lacking(cat, "shmup") == [], "a shooter pack has all of it"
    assert not [i for i in requirements.check(cat, cfg) if i.code == "ASSET-031"]
    made, _stand_ins = orchestrator.add_run_made_assets(cat, cfg, [], tmp_path / "staging")
    assert list(made) == [] and not [a for a in cat.assets if a.pack_id == arcade_kit.KIT_PACK]
    # a regeneration finds the stand-ins of the last run in the catalog and draws them again
    plain = _catalog(SYNTH / "basic16")
    plain_cfg = _cfg(SYNTH / "basic16", "shmup")
    prints = []
    for run in range(3):
        orchestrator.add_run_made_assets(plain, plain_cfg, [], tmp_path / f"run{run}")
        kit = [a for a in plain.assets if a.pack_id == arcade_kit.KIT_PACK]
        assert len(kit) == 3 and len({a.id for a in plain.assets}) == len(plain.assets)
        prints.append(orchestrator.inputs_fingerprint(plain_cfg, plain, []))
        plain = catalog.Catalog.from_json(plain.to_json())
    assert len(set(prints)) == 1
    assert arcade_kit.KIT_PACK in catalog.RUN_MADE_PACKS


def test_an_older_kind_gets_nothing_drawn(tmp_path: Path) -> None:
    for kind in ("turn_based", "arpg"):
        cat = _catalog(SYNTH / "basic16")
        cfg = _cfg(SYNTH / "basic16", kind)
        made, _stand_ins = orchestrator.add_run_made_assets(cat, cfg, [], tmp_path / kind)
        assert list(made) == [] and not [a for a in cat.assets if a.pack_id == arcade_kit.KIT_PACK]
        assert not [i for i in requirements.check(cat, cfg) if i.code in ("ASSET-031", "ASSET-032")]


# ----------------------------------------------------------------------------- requirements


def test_what_each_kind_requires_and_how_it_says_so() -> None:
    assert requirements.REQUIRED["shmup"] == ["PLAYER"]
    assert requirements.REQUIRED["run_and_gun"] == ["PLAYER", "GROUND"]
    assert requirements.REQUIRED["racing"] == ["VEHICLE", "GROUND"]
    assert requirements.required_by("ENEMY", "racing") == "the rival cars"
    assert requirements.required_by("DECORATION", "racing") == "trackside scenery"
    assert requirements.required_by("PLAYER", "shmup") == "the ship you fly"
    assert requirements.required_by("ENEMY", "turn_based") == "encounters", "as before"
    for kind in KINDS:
        rows = mapping.rows(kind)
        assert [r.role for r in rows if r.required] == requirements.REQUIRED[kind]
        assert all(requirements.required_by(r.role, kind) != r.role.lower() for r in rows), kind
        assert all(labels.role_label(r.role) != r.role for r in rows), "every row has a name"
    assert mapping.ROLE_KEYS["VEHICLE"] == "vehicle"
    assert arcade_kit.drawn_roles("shmup") == {"PLAYER"}
    assert arcade_kit.drawn_roles("racing") == {"VEHICLE", "GROUND"}
    assert arcade_kit.drawn_roles("run_and_gun") == frozenset()
    assert arcade_kit.drawn_roles("arpg") == frozenset()


def test_a_run_and_gun_still_needs_a_player_and_ground_of_the_packs(tmp_path: Path) -> None:
    pack = tmp_path / "empty"
    (pack / "ui").mkdir(parents=True)
    Image.new("RGBA", (16, 16), (200, 200, 60, 255)).save(pack / "ui" / "coin.png")
    issues = requirements.check(_catalog(pack), _cfg(pack, "run_and_gun"))
    missing = sorted(i.detail["role"] for i in issues if i.code == "ASSET-010" and i.severity.value == "error")  # fmt: skip
    assert missing == ["GROUND", "PLAYER"]
    wording = {i.detail["role"]: i.message for i in issues if i.code == "ASSET-010"}
    assert "the soldier, seen from the side" in wording["PLAYER"]


def test_a_vehicle_without_headings_is_a_note(tmp_path: Path) -> None:
    pack = tmp_path / "one_car"
    (pack / "tiles").mkdir(parents=True)
    Image.new("RGBA", (64, 64), (70, 70, 78, 255)).save(pack / "tiles" / "road.png")
    Image.new("RGBA", (24, 32), (220, 60, 60, 255)).save(pack / "car.png")
    cat = _catalog(pack)
    car = next(a for a in cat.assets if a.path.endswith("car.png"))
    car.overrides["role"] = "VEHICLE"
    car.status = catalog.recompute_status(car)
    issues = requirements.check(cat, _cfg(pack, "racing"))
    (note,) = [i for i in issues if i.code == "ASSET-032"]
    assert note.severity.value == "info" and car.id in note.message
    assert not [i for i in issues if i.code == "ASSET-031" and i.detail["role"] == "VEHICLE"]
    racer = _catalog(SYNTH / "racer")
    assert not [i for i in requirements.check(racer, _cfg(SYNTH / "racer", "racing"))
                if i.code in ("ASSET-032", "ASSET-031") or i.severity.value == "error"]  # fmt: skip


# ----------------------------------------------------------------------------- roles, sounds


def test_the_new_roles_are_roles_everywhere() -> None:
    new = {"VEHICLE", "EXPLOSION", "POWERUP", "HAZARD"}
    assert new <= set(labels.ROLE_INFO)
    grouped = {r for _name, roles in labels.MAPPING_GROUPS for r in roles}
    assert new <= grouped and "PROJECTILE" in grouped
    cat = catalog.Catalog()
    for n, role in enumerate(sorted(new)):
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
            )  # fmt: skip
        )
    schema.validate("catalog", cat.to_json())


def test_a_cars_rotation_sheet_is_a_vehicle_and_older_packs_have_none_of_the_roles() -> None:
    racer = _catalog(SYNTH / "racer")
    roles = {a.path.rsplit("/", 1)[-1]: catalog.effective(a)["role"] for a in racer.assets}
    assert {roles[f"{n}.png"] for n in ("player_car", "rival_car_1")} == {"VEHICLE"}
    assert (roles["oil.png"], roles["tyre.png"], roles["boost.png"]) == (
        "HAZARD",
        "HAZARD",
        "POWERUP",
    )
    assert roles["pickup_1.png"] == "ITEM" and roles["road.png"] == "GROUND"
    shooter = _catalog(SYNTH / "shooter")
    roles = {a.path.rsplit("/", 1)[-1]: catalog.effective(a)["role"] for a in shooter.assets}
    assert roles["explosion_6frames.png"] == "EXPLOSION" and roles["asteroid_1.png"] == "HAZARD"
    assert roles["capsule_1.png"] == "POWERUP" and roles["laser.png"] == "PROJECTILE"
    assert roles["enemy_ship_1.png"] == "ENEMY" and roles["player_ship.png"] == "PLAYER"
    new = {"VEHICLE", "EXPLOSION", "POWERUP", "HAZARD"}
    for name in ("basic16", "mixed", "platformer", "strips", "gunner"):
        found = {catalog.effective(a).get("role") for a in _catalog(SYNTH / name).assets}
        assert not found & new, name


def test_the_sound_slots_of_each_kind() -> None:
    def own(kind: str) -> list[str]:
        return [s.key for s in sound_slots.ARCHETYPE_SLOTS[kind]]

    assert own("shmup") == ["sfx_shoot", "sfx_explosion", "sfx_powerup", "sfx_bomb", "music_stage", "music_boss"]  # fmt: skip
    assert own("run_and_gun") == ["sfx_shoot", "sfx_explosion", "sfx_grenade", "sfx_weapon_pickup",
                                  "sfx_grapple", "music_stage", "music_boss"]  # fmt: skip
    assert own("racing") == ["sfx_engine", "sfx_skid", "sfx_bump", "sfx_pickup", "sfx_lap",
                             "sfx_countdown", "music_race", "music_results"]  # fmt: skip
    for kind in KINDS:
        keys = sound_slots.slot_keys(kind)
        assert len(set(keys)) == len(keys) or kind == "racing", kind
        assert all(sound_slots.is_valid_name(k) for k in keys)
    assert sound_slots.slot_keys("turn_based") == sound_slots.SLOT_KEYS, "as before"
    assert "sfx_jump" in sound_slots.slot_keys("metroidvania")


def test_the_slots_defaults_from_the_packs_file_names(tmp_path: Path) -> None:
    basic = _catalog(SYNTH / "audio_basic")
    older = sound_slots.default_sounds(basic, "turn_based")
    theme, hit = "audio_basic.music.overworld_theme", "audio_basic.sfx.hit"
    for kind, own in (
        ("shmup", {"music_stage": theme}),
        ("run_and_gun", {"music_stage": theme}),
        ("racing", {"music_race": theme, "sfx_bump": hit}),
    ):
        assert sound_slots.default_sounds(basic, kind) == older | own, kind
    # a pack that names its sounds fills every slot of its kind; the rest stays silent
    import wave

    pack = tmp_path / "sounds"
    names = ("sfx/laser_shot", "sfx/big_explosion", "sfx/engine_loop", "sfx/tyre_skid",
             "sfx/lap_done", "sfx/grapple_hook", "music/boss_fight", "music/results_jingle")  # fmt: skip
    for name in names:
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(pack / f"{name}.wav"), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(1)
            out.setframerate(2000)
            out.writeframes(bytes(2000 if name.startswith("sfx") else 40000))
    cat = _catalog(pack)
    shmup = sound_slots.default_sounds(cat, "shmup")
    assert shmup["sfx_shoot"] == "sounds.sfx.laser_shot" and shmup["music_boss"] == "sounds.music.boss_fight"  # fmt: skip
    assert shmup["sfx_explosion"] == "sounds.sfx.big_explosion" and "sfx_bomb" not in shmup
    gun = sound_slots.default_sounds(cat, "run_and_gun")
    assert gun["sfx_grapple"] == "sounds.sfx.grapple_hook" and "sfx_grenade" not in gun
    race = sound_slots.default_sounds(cat, "racing")
    assert [race[k].rsplit(".", 1)[-1] for k in ("sfx_engine", "sfx_skid", "sfx_lap", "music_results")] == [
        "engine_loop", "tyre_skid", "lap_done", "results_jingle"]  # fmt: skip
    assert "sfx_engine" not in sound_slots.default_sounds(cat, "arpg")


def test_an_isometric_race_without_a_car_of_eight_headings_gets_one_drawn_at_its_angle(
    tmp_path: Path,
) -> None:
    """T18.19: sixteen headings of a box with a cabin seen at the view's angle, the same every
    time; the kit draws it for an isometric race whose packs have no car of eight headings or
    more, and marks it as drawn for that view."""
    first = arcade_kit.iso_car((32, 16))
    assert first.size == (48 * arcade_kit.CAR_HEADINGS, 40)
    assert first.tobytes() == arcade_kit.iso_car((32, 16)).tobytes()
    cell = 48
    shapes = set()
    for k in range(arcade_kit.CAR_HEADINGS):
        frame = first.crop((k * cell, 0, (k + 1) * cell, 40))
        assert frame.getbbox() is not None, k
        shapes.add(frame.tobytes())
    assert len(shapes) >= 8, "the headings look different"
    cat = catalog.Catalog()
    added, _issues = arcade_kit.add(cat, "racing", 16, tmp_path, "isometric", (32, 16))
    assert "car" in added
    car = next(a for a in cat.assets if a.id == arcade_kit.asset_id(arcade_kit.CAR))
    facets = catalog.effective(car)
    assert facets["projection"] == "isometric" and facets["headings"] == 16
    assert catalog.fits_projection(car, "isometric") and not catalog.fits_projection(
        car, "top_down"
    )
