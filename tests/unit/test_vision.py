"""The local vision step (T17.34), without a model: the words of an answer read as a role, and
the step changes a picture only where the measurement said it helps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import catalog, vision
from rpggen.core.vision.llama import LlamaConfig

CONFIG = LlamaConfig(Path("server"), Path("model"), Path("projector"))


@pytest.mark.parametrize(
    ("raw", "role"),
    [
        ("Harvester vehicle", "VEHICLE"),
        ("Wooden house with door", "BUILDING"),
        ("Pixel Art Dragon", "ENEMY"),
        ("Blue Slime", "ENEMY"),
        ("Golden Key", "ITEM"),
        ("Pixel art girl in overalls", vision.PERSON),
        ("pliers", "TOOL"),
        ("Brown and green striped ground", "GROUND"),
        ("", None),
    ],
)
def test_the_strongest_word_of_an_answer_says_its_role(raw: str, role: str | None) -> None:
    assert vision.role_of(raw) == role


def _asset(name: str, role: str, confidence: float = 0.4, **extra) -> catalog.Asset:
    detected = {"usage": "sprite", "role": role}
    return catalog.Asset(f"pack.{name}", "pack", f"assets/packs/pack/{name}.png", "0" * 64,
                         "image", "NEEDS_REVIEW", detected, confidence=confidence, **extra)  # fmt: skip


@pytest.fixture
def rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "vision_rules.json"
    monkeypatch.setattr(vision, "RULES", path)
    return path


def _files(tmp_path: Path, assets: list[catalog.Asset]) -> dict[str, Path]:
    out = {}
    for a in assets:
        out[a.id] = tmp_path / f"{a.id}.png"
        out[a.id].write_bytes(a.id.encode())  # a picture of its own: its own hash
    return out


def test_without_rules_nothing_is_asked(tmp_path: Path, rules: Path) -> None:
    rules.write_text(json.dumps({"version": vision.RULES_VERSION, "roles": {}}))
    assets = [_asset("barn", "DECORATION")]
    files = _files(tmp_path, assets)

    def ask(*_args):
        raise AssertionError("asked")

    assert vision.apply(assets, lambda a: files[a.id], CONFIG, 0.75, ask) == 0


def test_only_a_role_measured_to_help_is_given(tmp_path: Path, rules: Path) -> None:
    rules.write_text(json.dumps({"version": vision.RULES_VERSION, "roles": {"BUILDING": {}}}))
    barn, cow, sure = (
        _asset("barn", "DECORATION"),
        _asset("cow", "DECORATION"),
        _asset("mill", "DECORATION", confidence=0.9),
    )
    user = _asset("shed", "DECORATION", overrides={"role": "DECORATION"})
    unused = _asset("copy", "NONE")
    assets = [barn, cow, sure, user, unused]
    files = _files(tmp_path, assets)
    answers = {"barn": "Wooden barn", "cow": "Spotted cow", "mill": "Windmill", "shed": "Shed",
               "copy": "Wooden barn"}  # fmt: skip
    asked: list[str] = []

    def ask(_config, pictures):
        out = {}
        for sha, file in pictures:
            name = file.stem.split(".", 1)[1]
            asked.append(name)
            out[sha] = vision.parse(answers[name])
        return out

    assert vision.apply(assets, lambda a: files[a.id], CONFIG, 0.75, ask) == 1
    assert sorted(asked) == ["barn", "cow"]  # not the sure one, the user's or the set-aside
    assert barn.detected["role"] == "BUILDING" and barn.detected_by == "vision"
    assert any(t.startswith(vision.VISION_TAG) for t in barn.detected["tags"])
    assert barn.confidence == 0.4  # still unsure: still reviewed
    assert cow.detected["role"] == "DECORATION"  # ANIMAL was not measured to help
