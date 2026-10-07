from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import app_settings


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def test_round_trip(tmp_path: Path) -> None:
    project = tmp_path / "game"
    project.mkdir()
    s = app_settings.AppSettings(godot_exe="g.exe", theme="light", thumb_size=128)
    s.window = {"x": 10, "y": 20, "w": 1200, "h": 800, "maximized": 0}
    s.splitters = {"audit": [600, 400]}
    s.option_presets = {"mine": {"resolution": [320, 180]}}
    s.quick_roles = ["GROUND", "WALL"]
    app_settings.add_recent(s, project, "Game", "arpg")
    app_settings.save(s)
    back = app_settings.load()
    assert back.to_json() == s.to_json()
    assert back.recent_projects[0].target == str(project)


def test_missing_and_corrupt_files_give_defaults(_cache: Path) -> None:
    assert app_settings.load().to_json() == app_settings.AppSettings().to_json()
    _cache.mkdir(parents=True)
    (_cache / app_settings.FILE_NAME).write_text("{not json", encoding="utf-8")
    assert app_settings.load().theme == "dark"
    (_cache / app_settings.FILE_NAME).write_text("[1, 2]", encoding="utf-8")
    assert app_settings.load().thumb_size == 96


def test_unknown_keys_and_wrong_types_are_ignored(_cache: Path) -> None:
    _cache.mkdir(parents=True)
    data = {
        "godot_exe": 5,
        "theme": "neon",
        "thumb_size": 77,
        "future_key": [1],
        "window": {"x": "a", "w": 5},
    }
    (_cache / app_settings.FILE_NAME).write_text(json.dumps(data), encoding="utf-8")
    s = app_settings.load()
    assert (s.godot_exe, s.theme, s.thumb_size) == ("", "dark", 96)
    assert s.window == {"w": 5}


def test_recent_projects_are_deduplicated_capped_and_pruned(tmp_path: Path) -> None:
    s = app_settings.AppSettings()
    folders = []
    for i in range(12):
        folder = tmp_path / f"p{i}"
        folder.mkdir()
        folders.append(folder)
        app_settings.add_recent(s, folder, f"P{i}", "turn_based")
    app_settings.add_recent(s, folders[5], "P5 again", "arpg")
    assert len(s.recent_projects) == app_settings.RECENT_MAX
    assert s.recent_projects[0].name == "P5 again"
    assert sum(1 for r in s.recent_projects if r.target == str(folders[5])) == 1
    app_settings.save(s)
    folders[5].rmdir()  # the folder disappears
    assert all(r.target != str(folders[5]) for r in app_settings.load().recent_projects)


def test_geometry_is_clamped_to_an_existing_screen() -> None:
    screens = [(0, 0, 1920, 1080)]
    off = {"x": 5000, "y": 4000, "w": 1100, "h": 720}
    assert app_settings.clamp_geometry(off, screens, (1000, 640)) == (820, 360, 1100, 720)
    huge = {"x": -300, "y": 0, "w": 4000, "h": 3000}
    assert app_settings.clamp_geometry(huge, screens, (1000, 640)) == (0, 0, 1920, 1080)
    assert app_settings.clamp_geometry({}, screens, (1000, 640)) is None
    tiny = {"x": 0, "y": 0, "w": 100, "h": 100}
    assert app_settings.clamp_geometry(tiny, screens, (1000, 640))[2:] == (1000, 640)


def test_save_failure_never_raises(tmp_path: Path, monkeypatch) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(blocker / "sub"))  # a folder cannot be made there
    app_settings.save(app_settings.AppSettings())
