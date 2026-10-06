from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import __version__, jsonio
from rpggen.core import config
from rpggen.errors import RpgGenError

PACK = config.PackRef("basic16", "C:/packs/basic16", "a" * 64, "folder")


def test_defaults() -> None:
    cfg = config.default_for("Demo", [PACK])
    data = cfg.to_json()
    assert data["config_version"] == 1
    assert data["generator_version"] == __version__
    assert data["godot_version"] == "4.7.2"
    assert data["archetype"] == "turn_based"
    assert data["resolution"] == [640, 360]
    assert data["window_size"] == [1280, 720]
    assert data["seed"] == 12345
    assert data["map_layers"] == ["Ground", "GroundDetails", "Walls", "Props", "Overhead"]
    assert data["validation"] == {"smoke_test": True}
    assert data["features"]["navigation"] is False
    assert all(v for k, v in data["features"].items() if k != "navigation")
    assert set(data["features"]) == set(config.FEATURE_KEYS)


def test_default_input_tables() -> None:
    tb = config.default_input("turn_based")
    assert set(tb) == {
        "move_up",
        "move_down",
        "move_left",
        "move_right",
        "interact",
        "confirm",
        "cancel",
        "menu",
    }
    assert tb["move_up"]["joy_axes"] == [[1, -1.0]]
    arpg = config.default_input("arpg")
    assert {"attack", "secondary_attack", "dodge", "quick_item"} <= set(arpg)
    assert arpg["attack"]["mouse_buttons"] == [1]
    # defaults are independent copies
    tb["move_up"]["keys"].append("X")
    assert "X" not in config.default_input("turn_based")["move_up"]["keys"]


def test_save_load_roundtrip(tmp_path: Path) -> None:
    cfg = config.default_for("Demo", [PACK], archetype="arpg")
    path = tmp_path / "cfg.json"
    config.save(cfg, path)
    loaded = config.load(path)
    assert loaded == cfg
    assert "attack" in loaded.input
    # saving twice gives identical bytes
    before = path.read_bytes()
    config.save(loaded, path)
    assert path.read_bytes() == before


def test_load_rejects_invalid(tmp_path: Path) -> None:
    cfg = config.default_for("Demo", [PACK]).to_json()
    cfg["base_tile_size"] = 15
    path = tmp_path / "bad.json"
    jsonio.write(path, cfg)
    with pytest.raises(RpgGenError) as ei:
        config.load(path)
    assert ei.value.code == "CAT-002"


def test_folder_hash_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    h1 = config.folder_sha256(tmp_path)
    assert h1 == config.folder_sha256(tmp_path)
    (tmp_path / "b.txt").write_text("c", encoding="utf-8")
    assert config.folder_sha256(tmp_path) != h1


def test_pack_ref_from_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(RpgGenError) as ei:
        config.pack_ref_from_folder(tmp_path / "nope", "nope")
    assert ei.value.code == "ARCH-001"
