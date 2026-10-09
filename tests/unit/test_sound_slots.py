from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import archive, catalog, config, inventory, requirements, sound_slots

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
SAMPLE = Path(__file__).resolve().parents[2] / "sample_pack"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _catalog(pack: Path, pack_id: str | None = None) -> catalog.Catalog:
    opened = archive.open_pack(pack, set(), pack_id=pack_id)
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    return cat


def test_audio_basic_roles_and_slot_defaults() -> None:
    cat = _catalog(SYNTH / "audio_basic")
    expected = json.loads((SYNTH / "audio_basic.expected.json").read_text(encoding="utf-8"))
    for rel, facts in expected.items():
        asset = next(a for a in cat.assets if a.path.endswith(rel))
        assert catalog.effective(asset)["role"] == facts["role"], rel
    want = json.loads((SYNTH / "audio_basic.slots.json").read_text(encoding="utf-8"))
    assert sound_slots.default_sounds(cat) == want


def test_slot_tokens_and_fallbacks() -> None:
    cat = _catalog(SYNTH / "audio_basic")
    sounds = sound_slots.default_sounds(cat)
    assert "sfx_door" not in sounds and "sfx_save" not in sounds  # nothing plausible: silent
    assert sounds["music_title"] == sounds["music_map"]  # no title track: the map music


def test_the_longest_track_is_the_map_music_when_no_name_matches(tmp_path: Path) -> None:
    import wave

    pack = tmp_path / "plain"
    for name, seconds in (("alpha", 25), ("omega", 40), ("zed", 22)):
        (pack / "music").mkdir(parents=True, exist_ok=True)
        with wave.open(str(pack / "music" / f"{name}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(1000)
            w.writeframes(bytes(2) * 1000 * seconds)
    cat = _catalog(pack, "plain")
    assert sound_slots.default_sounds(cat)["music_map"] == "plain.music.omega"


def test_stale_ids_are_dropped_and_gaps_filled() -> None:
    cat = _catalog(SYNTH / "audio_basic")
    current = {
        "music_map": "audio_basic.music.battle_bgm",  # a valid choice is kept
        "sfx_hit": "audio_basic.nope",  # stale: replaced by the default
        "sfx_chest": "audio_basic.tiles.terrain",  # wrong kind: replaced
    }
    resolved = sound_slots.resolve_sounds(cat, current)
    assert resolved["music_map"] == "audio_basic.music.battle_bgm"
    assert resolved["sfx_hit"] == "audio_basic.sfx.hit"
    assert resolved["sfx_chest"] == "audio_basic.sfx.chest_open"


def test_summary_text() -> None:
    assert sound_slots.summary({}) == "0 music tracks, 0 sound effects assigned"
    assert (
        sound_slots.summary({"music_map": "a", "sfx_hit": "b", "sfx_step": "c"})
        == "1 music track, 2 sound effects assigned"
    )


def test_config_round_trip_and_omission(tmp_path: Path) -> None:
    ref = config.PackRef("p", "C:/p", "0" * 64, "folder")
    cfg = config.default_for("T", [ref])
    assert "sounds" not in cfg.to_json() and "starter_map" not in cfg.to_json()
    cfg.sounds = {"music_map": "p.music.a", "sfx_hit": "p.sfx.b"}
    path = tmp_path / "c.json"
    config.save(cfg, path)
    back = config.load(path)
    assert back.sounds == cfg.sounds
    cfg.sounds = {"bogus_slot": "x"}
    with pytest.raises(Exception, match="bogus_slot|Additional"):
        config.save(cfg, tmp_path / "bad.json")


def test_info_issues_when_the_packs_have_no_audio() -> None:
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    cfg = config.default_for("T", [ref])
    codes = [i.code for i in requirements.check(_catalog(SYNTH / "basic16"), cfg)]
    assert "ASSET-026" in codes and "ASSET-027" in codes
    codes = [i.code for i in requirements.check(_catalog(SYNTH / "audio_basic"), cfg)]
    assert "ASSET-026" not in codes and "ASSET-027" not in codes


def test_the_sample_pack_has_music_and_effects() -> None:
    cat = _catalog(SAMPLE, "sample_pack")
    sounds = sound_slots.default_sounds(cat)
    assert sounds["music_map"] == "sample_pack.music.town_theme"
    assert sounds["music_battle"] == "sample_pack.music.battle_theme"
    assert len(sounds) >= 10


# ------------------------------------------------------------------------ custom slots (T13.16)


def _wav(path: Path, seconds: float = 0.2) -> None:
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(1000)
        w.writeframes(bytes(2) * int(1000 * seconds))


def _step_pack(tmp_path: Path) -> catalog.Catalog:
    import shutil

    pack = tmp_path / "steps"
    shutil.copytree(SYNTH / "basic16", pack)
    (pack / "tiles" / "stone").mkdir()
    shutil.copy(pack / "tiles" / "terrain.png", pack / "tiles" / "stone" / "floor.png")
    for name in ("step", "step_grass", "footstep-stone", "walk_wood", "grass_rustle", "magic"):
        _wav(pack / "sfx" / f"{name}.wav")
    return _catalog(pack, "steps")


@pytest.mark.parametrize(
    ("key", "ok"),
    [
        ("sfx_magic", True),
        ("music_cave", True),
        ("sfx_step_grass", True),
        ("sfx_a1", True),
        ("sfx_" + "a" * 31, True),
        ("sfx_" + "a" * 32, False),
        ("sfx_a", False),  # at least two characters after the prefix
        ("sfx_1up", False),
        ("sfx_Magic", False),
        ("sfx-magic", False),
        ("sound_magic", False),
        ("magic", False),
        ("sfx_", False),
        ("", False),
    ],
)
def test_the_slot_name_pattern(key: str, ok: bool) -> None:
    assert sound_slots.is_valid_name(key) is ok
    assert all(sound_slots.is_valid_name(k) for k in sound_slots.SLOT_KEYS)
    assert sound_slots.is_valid_name(None) is False


def test_custom_slots_are_told_from_the_fixed_ones() -> None:
    sounds = {"sfx_hit": "a", "sfx_magic": "b", "music_cave": "", "Bad Key": "c"}
    assert sound_slots.custom_slots(sounds) == ["music_cave", "sfx_magic"]
    assert sound_slots.invalid_names(sounds) == ["Bad Key"]
    assert (
        sound_slots.kind_of("music_cave") == "music" and sound_slots.kind_of("sfx_magic") == "sfx"
    )
    assert sound_slots.slot("sfx_step_grass").label == "Footstep (grass)"
    assert sound_slots.slot("sfx_magic").label == "sfx_magic"
    assert sound_slots.slot("sfx_hit").label == "Hit"
    assert sound_slots.summary(sounds) == "0 music tracks, 2 sound effects assigned"


def test_default_sounds_fills_the_surface_steps_from_file_names(tmp_path: Path) -> None:
    cat = _step_pack(tmp_path)
    sounds = sound_slots.default_sounds(cat)
    assert sounds["sfx_step_grass"] == "steps.sfx.step_grass"
    assert sounds["sfx_step_stone"] == "steps.sfx.footstep_stone"
    assert sounds["sfx_step_wood"] == "steps.sfx.walk_wood"
    assert "sfx_step_water" not in sounds and "sfx_step_sand" not in sounds
    assert sounds["sfx_step"].startswith("steps.sfx.")
    assert sound_slots.SURFACES == ["grass", "stone", "wood", "water", "sand"]


def test_a_ground_asset_is_tagged_with_its_surface(tmp_path: Path) -> None:
    from rpggen.core import classifier

    assert classifier.suggested_surface("tiles/stone/floor.png") == "stone"
    assert classifier.suggested_surface("tiles/grass/stone_path.png") == "stone", "the file wins"
    assert classifier.suggested_surface("tiles/Snow Fields/a/ground.png") == "snow"
    assert classifier.suggested_surface("tiles/terrain.png") is None
    cat = _step_pack(tmp_path)
    floor = next(a for a in cat.assets if a.path.endswith("stone/floor.png"))
    plain = next(a for a in cat.assets if a.path.endswith("tiles/terrain.png"))
    assert catalog.effective(floor)["role"] == "GROUND"
    assert "surface:stone" in catalog.effective(floor)["tags"]
    assert sound_slots.surface_of(floor) == "stone"
    assert sound_slots.surface_of(plain) is None
    # only ground: a sound named after grass is not a surface
    rustle = next(a for a in cat.assets if a.path.endswith("grass_rustle.wav"))
    assert sound_slots.surface_of(rustle) is None


def test_resolve_keeps_custom_slots_and_drops_bad_names(tmp_path: Path) -> None:
    cat = _step_pack(tmp_path)
    current = {
        "sfx_magic": "steps.sfx.magic",  # a custom slot with a sound
        "sfx_spell": "",  # a custom slot the user has not filled yet
        "sfx_gone": "steps.sfx.nope",  # its sound left the pack: the slot stays, silent
        "music_cave": "steps.sfx.magic",  # wrong kind: silent
        "Bad Key": "steps.sfx.magic",
        "sfx_step_grass": "",  # cleared on purpose: stays silent
    }
    resolved = sound_slots.resolve_sounds(cat, current)
    assert resolved["sfx_magic"] == "steps.sfx.magic"
    assert (
        resolved["sfx_spell"] == "" and resolved["sfx_gone"] == "" and resolved["music_cave"] == ""
    )
    assert "Bad Key" not in resolved
    assert resolved["sfx_step_grass"] == ""
    assert resolved["sfx_step_stone"] == "steps.sfx.footstep_stone"  # a default surface step
    assert sound_slots.valid_choice(cat, "sfx_magic", "steps.sfx.magic")
    assert not sound_slots.valid_choice(cat, "Bad Key", "steps.sfx.magic")


def test_a_bad_slot_name_in_a_config_file_is_cat_006(tmp_path: Path) -> None:
    from rpggen import jsonio
    from rpggen.errors import RpgGenError

    cfg = config.default_for("Game", [config.pack_ref_from_source(SYNTH / "audio_basic", "a")])
    cfg.sounds = {"sfx_magic": "a.b", "music_cave": ""}
    path = tmp_path / "generator_config.json"
    config.save(cfg, path)
    assert config.load(path).sounds == {"sfx_magic": "a.b", "music_cave": ""}
    data = jsonio.read(path)
    data["sounds"]["Magic Sound"] = "a.b"
    jsonio.write(path, data)
    with pytest.raises(RpgGenError) as caught:
        config.load(path)
    assert caught.value.code == "CAT-006"
    assert "Magic Sound" in str(caught.value)
    cfg.sounds = {"sfx_": "x"}
    with pytest.raises(RpgGenError) as caught:
        config.save(cfg, path)
    assert caught.value.code == "CAT-006"


def test_the_readme_lists_the_custom_slots() -> None:
    from rpggen.core import staging

    template = "Custom:\n{custom_sound_slots}\n"
    template = (
        "{project_name}{archetype}{runtime_version}{godot_version}{packs_list}"
        "{version_control_note}\n" + template
    )
    cfg = config.default_for("Game", [])
    assert "  - (none yet)" in staging.render_readme(template, cfg, "1.1.0")
    cfg.sounds = {"sfx_hit": "a", "sfx_magic": "b", "sfx_step_grass": ""}
    text = staging.render_readme(template, cfg, "1.1.0")
    assert "  - `sfx_magic`\n  - `sfx_step_grass`" in text and "sfx_hit" not in text
    real = Path(staging.__file__).parents[2] / "godot_templates/project_files/README.template.md"
    assert "{custom_sound_slots}" in real.read_text(encoding="utf-8")


def test_a_metroidvania_has_four_more_fixed_slots_and_the_others_are_unchanged() -> None:
    """T14.10: jump, land, dash and ability are fixed slots of the metroidvania only; for the
    other archetypes such a name is a custom slot, so their projects are what they were."""
    shared = sound_slots.slot_keys()
    assert shared == sound_slots.SLOT_KEYS == sound_slots.slot_keys("arpg")
    own = sound_slots.slot_keys("metroidvania")
    assert own[: len(shared)] == shared
    assert own[len(shared) :] == ("sfx_jump", "sfx_land", "sfx_dash", "sfx_ability")
    assert all(sound_slots.is_valid_name(k) for k in own)
    assert sound_slots.slot("sfx_jump").label == "Jump"
    assert sound_slots.slot("sfx_ability").help == "An ability is found."
    assert sound_slots.is_custom("sfx_jump") and not sound_slots.is_custom(
        "sfx_jump", "metroidvania"
    )
    assert not sound_slots.is_custom("sfx_hit", "metroidvania")
    assert sound_slots.custom_slots(["sfx_jump", "sfx_magic"]) == ["sfx_jump", "sfx_magic"]
    assert sound_slots.custom_slots(["sfx_jump", "sfx_magic"], "metroidvania") == ["sfx_magic"]

    cat = _catalog(SAMPLE.parent / "sample_pack_side", "sample_pack_side")
    plain = sound_slots.default_sounds(cat)
    side = sound_slots.default_sounds(cat, "metroidvania")
    assert not {"sfx_jump", "sfx_land", "sfx_dash", "sfx_ability"} & set(plain)
    assert {k: v for k, v in side.items() if k in plain} == plain
    names = {key: side[key].rsplit(".", 1)[-1] for key in own[len(shared) :]}
    assert names == {
        "sfx_jump": "jump",
        "sfx_land": "land",
        "sfx_dash": "dash",
        "sfx_ability": "powerup",
    }
    # a choice is kept, a stale one falls back to the default, a cleared one stays silent
    current = {"sfx_jump": side["sfx_land"], "sfx_dash": "gone.sfx.x", "sfx_land": ""}
    resolved = sound_slots.resolve_sounds(cat, current, "metroidvania")
    assert resolved["sfx_jump"] == side["sfx_land"]
    assert resolved["sfx_dash"] == side["sfx_dash"]
    assert resolved["sfx_land"] == sound_slots.CLEARED
    assert list(resolved)[: len(own)] == [k for k in own if k in resolved]
    # for a top-down game the same table keeps `sfx_jump` only as the custom slot it then is
    top = sound_slots.resolve_sounds(cat, {"sfx_jump": side["sfx_jump"]})
    assert top["sfx_jump"] == side["sfx_jump"] and "sfx_dash" not in top
