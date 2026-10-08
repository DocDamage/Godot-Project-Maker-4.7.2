from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import __version__, jsonio, schema
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
    cfg["base_tile_size"] = 7  # below 8 (the range is 8 to 256, T12.03)
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


# ------------------------------------------------------------------------ hashing (T12.02)


def test_a_known_hash_means_no_pack_file_is_opened(tmp_path: Path, monkeypatch) -> None:
    import builtins
    import io
    import zipfile

    archive_file = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive_file, "w") as zf:
        zf.writestr("a.png", b"x")
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "a.png").write_bytes(b"x")

    def refuse(*_args, **_kwargs):
        raise AssertionError("a pack file was opened")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(io, "open", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    zip_ref = config.pack_ref_from_source(archive_file, "z", known_sha256="a" * 64)
    folder_ref = config.pack_ref_from_source(folder, "f", known_sha256="b" * 64)
    assert zip_ref.source_sha256 == "a" * 64 and zip_ref.kind == "zip"
    assert folder_ref.source_sha256 == "b" * 64 and folder_ref.kind == "folder"


def test_an_archive_is_hashed_in_a_stream(tmp_path: Path) -> None:
    import hashlib
    import tracemalloc
    import zipfile

    big = tmp_path / "big.zip"
    block = bytes(range(256)) * 4096  # 1 MiB
    with zipfile.ZipFile(big, "w", zipfile.ZIP_STORED) as zf, zf.open("data.bin", "w") as out:
        for _ in range(50):
            out.write(block)
    expected = hashlib.sha256(big.read_bytes()).hexdigest()
    tracemalloc.start()
    ref = config.pack_ref_from_source(big, "big")
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert ref.source_sha256 == expected
    assert peak < 8 * 1024 * 1024, f"peak {peak} bytes"


def test_folder_identity_ignores_os_junk_and_equals_the_inventory(tmp_path: Path) -> None:
    from rpggen.core import archive, inventory

    folder = tmp_path / "pack"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "a.txt").write_text("a", encoding="utf-8")
    (folder / "b.txt").write_text("b", encoding="utf-8")
    before = config.folder_sha256(folder)
    (folder / "Thumbs.db").write_bytes(b"junk")
    (folder / "sub" / ".DS_Store").write_bytes(b"junk")
    assert config.folder_sha256(folder) == before
    inv = inventory.build_inventory(archive.open_pack(folder, set()))
    assert inv.source_sha256 == before  # the config and the catalog share one identity


# ------------------------------------------------------------------------ git (T12.12)


def test_the_pack_art_choice_round_trips_and_the_default_is_omitted() -> None:
    cfg = config.default_for("Demo", [PACK])
    assert cfg.pack_art == "commit" and "git" not in cfg.to_json()
    cfg.git["pack_art"] = "commit"  # the default written out loud is still left out
    assert "git" not in cfg.to_json()
    for choice in ("lfs", "ignore"):
        cfg.git = {"pack_art": choice}
        data = cfg.to_json()
        assert data["git"] == {"pack_art": choice}
        schema.validate("config", data)
        assert config.GeneratorConfig.from_json(data).pack_art == choice
    cfg.git = {"pack_art": "everything"}
    with pytest.raises(RpgGenError):
        schema.validate("config", cfg.to_json())
