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
