from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from rpggen.core import classifier
from rpggen.core.analyzer import image_facts

CASES = json.loads((Path(__file__).parent / "classifier_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["path"] for c in CASES])
def test_table_driven_roles(case: dict) -> None:
    role, confidence, alt = classifier.classify(case["facets"], case["path"], case.get("analysis"))
    assert role == case["role"], (role, confidence, alt)
    assert 0.0 <= confidence <= 1.0
    if case["role"] not in ("FONT",):
        assert confidence <= 0.95
    assert len(alt) <= 3 and all(a[0] != role for a in alt)


def test_enough_cases() -> None:
    assert len(CASES) >= 40


def test_tokens() -> None:
    assert classifier.tokens("Tilesets/Interior/furniture.png") == (
        ["tilesets", "interior"],
        ["furniture"],
    )
    assert classifier.tokens("Sprites/playerWalk_01.png") == (["sprites"], ["player", "walk"])
    assert classifier.tokens("a/b_c/x1-2.png") == (
        [],
        ["x1"],
    )  # one-letter + numbers dropped
    assert classifier.tokens("chars/tree_s.png") == (
        ["chars"],
        ["tree", "s"],
    )  # direction letters stay
    assert classifier.tokens("\u00c1rbol/Grande.png") == (["arbol"], ["grande"])
    assert classifier.tokens("file.png") == ([], ["file"])


def test_deeper_folders_weigh_more() -> None:
    deep = classifier.classify({"usage": "sprite", "frame": [48, 48]}, "a/b/c/enemies/x.png", None)
    shallow = classifier.classify(
        {"usage": "sprite", "frame": [48, 48]}, "enemies/a/b/c/x.png", None
    )
    assert deep[0] == shallow[0] == "ENEMY"
    assert deep[1] > shallow[1]


def test_confidence_and_alternatives() -> None:
    role, conf, alt = classifier.classify({"usage": "tiles"}, "world/grass.png", None)
    assert role == "GROUND"
    assert 0.5 < conf <= 0.95
    assert alt and alt[0][0] in ("DECORATION", "WALL")
    assert all(isinstance(a[1], float) for a in alt)
    unknown = classifier.classify({"usage": "sprite", "frame": [100, 100]}, "q/z.png", None)
    assert unknown == ("DECORATION", 0.1, [])


def test_tie_break_follows_table_order() -> None:
    facets = {"usage": "sprite", "frame": [16, 24], "animations": {"walk_down": {}}}
    role, _, _ = classifier.classify(facets, "characters/hero.png", None)
    assert role == "PLAYER"  # PLAYER precedes NPC in the table


def test_audio_duration_for_wav(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 8000 * 3)
    assert classifier.audio_duration(path) == pytest.approx(3.0)
    assert classifier.audio_duration(tmp_path / "missing.wav") is None
    garbage = tmp_path / "x.ogg"
    garbage.write_bytes(b"not audio")
    assert classifier.audio_duration(garbage) is None


def _panel(w: int = 48, h: int = 40, border: int = 6) -> np.ndarray:
    a = np.zeros((h, w, 4), dtype=np.uint8)
    a[..., 3] = 255
    a[...] = (60, 60, 160, 255)
    # varied border art
    for i in range(border):
        a[i, :, :3] = (10 + i * 20, 10, 10)
        a[h - 1 - i, :, :3] = (10, 10 + i * 20, 10)
        a[:, i, :3] = (10, 10, 10 + i * 20)
        a[:, w - 1 - i, :3] = (200 - i * 20, 200, 200)
    # transparent rounded corners
    a[0, 0, 3] = 0
    a[0, w - 1, 3] = 0
    return a


def test_nine_slice_detection() -> None:
    assert image_facts.detect_nine_slice(_panel()) == [6, 6, 6, 6]
    assert image_facts.detect_nine_slice(_panel(60, 30, 4)) == [4, 4, 4, 4]


def test_nine_slice_rejects_non_panels() -> None:
    opaque = _panel()
    opaque[..., 3] = 255
    assert image_facts.detect_nine_slice(opaque) is None  # needs alpha
    assert image_facts.detect_nine_slice(_panel(16, 16, 2)) is None  # too small
    flat = np.zeros((32, 32, 4), dtype=np.uint8)
    assert image_facts.detect_nine_slice(flat) is None  # no borders
    noise = np.random.default_rng(1).integers(0, 256, size=(32, 32, 4), dtype=np.uint8)
    noise[0, 0, 3] = 0
    assert image_facts.detect_nine_slice(noise) is None


def test_a_monsters_name_counts_for_more_than_a_folder_of_characters() -> None:
    """A walking sheet in a folder that says only *characters* is a villager, unless its own
    name says it is a monster or a boss; the hero there stays the hero."""
    walking = {"usage": "sprite", "frame": [16, 16], "animations": {"walk_down": {}}}
    role, confidence, alt = classifier.classify(walking, "characters/slime.png", None)
    assert role == "ENEMY" and alt[0][0] == "NPC", "the walking sheet still speaks for a villager"
    assert confidence > alt[0][1]
    assert classifier.classify(walking, "characters/villager_mason.png", None)[0] == "NPC"
    assert classifier.classify(walking, "characters/mason.png", None)[0] == "NPC"
    assert classifier.classify(walking, "characters/hero.png", None)[0] == "PLAYER"
    assert classifier.classify(walking, "character/dragon_boss.png", None)[0] == "BOSS"
    # a folder that names villagers is no folder of "somebody": it still decides
    assert classifier.classify(walking, "npcs/guard_wolf.png", None)[0] == "NPC"
