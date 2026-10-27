from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import app_settings


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return paths.config_dir()  # where settings.json lives


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
    assert app_settings.load().theme == "system"
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
    assert (s.godot_exe, s.theme, s.thumb_size) == ("", "system", 96)
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
    folders[5].rmdir()  # the folder disappears (an unplugged drive looks the same)
    kept = [r.target for r in app_settings.load().recent_projects]
    assert str(folders[5]) in kept  # nothing is dropped behind the user's back
    app_settings.save(app_settings.load())
    assert str(folders[5]) in [r.target for r in app_settings.load().recent_projects]


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


# ------------------------------------------------------------------------ the store (T12.11)


def test_two_stores_that_change_different_keys_both_keep_their_changes(_cache: Path) -> None:
    path = app_settings.settings_path()
    a = app_settings.SettingsStore(path)
    b = app_settings.SettingsStore(path)
    a.get()
    b.get()  # both started from the same (empty) file
    a.update(theme="light")
    b.update(godot_exe="godot.exe", thumb_size=128)
    on_disk = app_settings.load()
    assert (on_disk.theme, on_disk.godot_exe, on_disk.thumb_size) == ("light", "godot.exe", 128)
    assert b.get().theme == "light"  # b learned of a's change when it merged


def test_the_process_that_changed_a_key_wins_for_that_key(_cache: Path) -> None:
    path = app_settings.settings_path()
    a, b = app_settings.SettingsStore(path), app_settings.SettingsStore(path)
    a.get()
    b.get()
    a.update(thumb_size=64)
    b.update(thumb_size=192)
    assert app_settings.load().thumb_size == 192


def test_recent_projects_merge_by_folder_newest_first(tmp_path: Path, _cache: Path) -> None:
    path = app_settings.settings_path()
    a, b = app_settings.SettingsStore(path), app_settings.SettingsStore(path)
    a.get()
    b.get()

    def add(name: str, when: str):
        def fn(s: app_settings.AppSettings) -> None:
            s.recent_projects.insert(
                0, app_settings.RecentProject(str(tmp_path / name), name, "arpg", when)
            )

        return fn

    a.update(add("one", "2026-10-01T10:00:00"))
    b.update(add("two", "2026-10-02T10:00:00"))  # b had not seen "one"
    a.update(add("three", "2026-10-03T10:00:00"))
    names = [r.name for r in app_settings.load().recent_projects]
    assert names == ["three", "two", "one"]


def test_removing_a_recent_project_sticks_when_another_window_saves(
    tmp_path: Path, _cache: Path
) -> None:
    path = app_settings.settings_path()
    s = app_settings.AppSettings()
    for name in ("keep", "drop"):
        app_settings.add_recent(s, tmp_path / name, name, "arpg")
    app_settings.save(s)
    a, b = app_settings.SettingsStore(path), app_settings.SettingsStore(path)
    a.get()
    b.get()
    a.update(
        lambda x: setattr(x, "recent_projects", [p for p in x.recent_projects if p.name != "drop"])
    )
    b.update(theme="light")  # b still lists "drop" in memory but did not change the list
    assert [r.name for r in app_settings.load().recent_projects] == ["keep"]


def test_get_does_no_file_io_after_the_first_call(_cache: Path, monkeypatch) -> None:
    import builtins
    import io

    store = app_settings.store()
    store.get()

    def refuse(*_a, **_k):
        raise AssertionError("the settings file was touched")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(io, "open", refuse)
    monkeypatch.setattr(Path, "read_text", refuse)
    for _ in range(100):
        assert app_settings.get().theme == "system"


def test_the_store_belongs_to_the_settings_file(tmp_path: Path, monkeypatch) -> None:
    first = app_settings.store()
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "elsewhere"))
    assert app_settings.store() is not first
    assert app_settings.store() is app_settings.store()


def test_scheduled_writes_are_held_back_merged_and_flushed(_cache: Path, monkeypatch) -> None:
    monkeypatch.setattr(app_settings, "WRITE_DELAY_S", 5.0)  # the timer must not fire here
    app_settings.schedule(thumb_size=64)
    app_settings.schedule(thumb_size=128)
    app_settings.schedule(splitters={"audit": [10, 20]})
    assert app_settings.get().thumb_size == 128  # in memory at once
    assert not app_settings.settings_path().exists()  # nothing written yet
    app_settings.store().flush()
    on_disk = app_settings.load()
    assert on_disk.thumb_size == 128 and on_disk.splitters == {"audit": [10, 20]}


def test_a_scheduled_write_happens_by_itself_after_the_delay(_cache: Path, monkeypatch) -> None:
    import time

    monkeypatch.setattr(app_settings, "WRITE_DELAY_S", 0.05)
    app_settings.schedule(thumb_size=192)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and app_settings.load().thumb_size != 192:
        time.sleep(0.02)
    assert app_settings.load().thumb_size == 192


def test_an_update_after_a_schedule_takes_the_scheduled_change_along(
    _cache: Path, monkeypatch
) -> None:
    monkeypatch.setattr(app_settings, "WRITE_DELAY_S", 5.0)
    app_settings.schedule(thumb_size=64)
    app_settings.update(theme="light")
    on_disk = app_settings.load()
    assert (on_disk.thumb_size, on_disk.theme) == (64, "light")


def test_unknown_fields_are_refused() -> None:
    with pytest.raises(AttributeError):
        app_settings.update(nonsense=1)


def test_available_marks_a_slow_folder_without_waiting_for_it() -> None:
    import time

    def is_dir(target: str) -> bool:
        if target == "slow":
            time.sleep(3)
        return target != "gone"

    started = time.monotonic()
    result = app_settings.available(["here", "gone", "slow"], timeout_s=0.3, is_dir=is_dir)
    assert time.monotonic() - started < 1.5  # the slow one did not hold the others up
    assert result == {"here": True, "gone": False, "slow": False}


# ------------------------------------------------------------------------ phase times (T13.07)


def test_the_estimate_from_a_known_history_and_none_without_one() -> None:
    history = {
        "build": [[100, 20.0], [200, 50.0], [50, 5.0]],  # 0.2, 0.25 and 0.1 s an asset
        "preflight": [[100, 2.0], [900, 4.0], [10, 3.0]],
        "import": [[0, 12.0], [0, 8.0]],  # runs that never counted their assets
    }
    assert app_settings.estimate(history, "build", 400) == pytest.approx(0.2 * 400)
    assert app_settings.estimate(history, "build", 0) == 20.0, "no count: the median time"
    assert app_settings.estimate(history, "preflight", 5000) == 3.0, "it does not scale"
    assert app_settings.estimate(history, "import", 300) == 10.0, "no counted run: the median"
    assert app_settings.estimate(history, "smoke", 300) is None
    assert app_settings.estimate({}, "build", 300) is None
    assert app_settings.estimate_rest(history, ["preflight", "build"], 400) == pytest.approx(83.0)
    assert app_settings.estimate_rest(history, ["build", "smoke"], 400) is None
    assert app_settings.estimate_rest(history, [], 400) == 0.0


def test_the_history_keeps_ten_runs_and_survives_a_round_trip(_cache: Path) -> None:
    settings = app_settings.AppSettings()
    for run in range(14):
        app_settings.add_phase_times(settings, {"build": 10.0 + run, "report": 1.0}, 100 + run)
    assert len(settings.phase_history["build"]) == app_settings.HISTORY_LENGTH == 10
    assert settings.phase_history["build"][0] == [104.0, 14.0], "the oldest four are gone"
    assert settings.phase_history["build"][-1] == [113.0, 23.0]
    app_settings.add_phase_times(settings, {"smoke": float("nan")}, 5)  # not a time: no entry
    app_settings.save(settings)
    back = app_settings.load()
    assert back.phase_history["build"] == settings.phase_history["build"]
    assert back.phase_history["report"] == [[113.0, 1.0]] * 0 + settings.phase_history["report"]
    assert back.to_json() == settings.to_json()


def test_a_settings_file_from_1_0_and_a_damaged_history_load(_cache: Path) -> None:
    path = app_settings.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": "light", "phase_timings": {"build": 9.5}}), "utf-8")
    old = app_settings.load()
    assert old.phase_history == {} and old.theme == "light" and old.phase_timings == {"build": 9.5}
    damaged = {
        "phase_history": {
            "build": [[10, 2.0], "x", [1, 2, 3], [5, -1], [True, 3.0], [7, 3.5]],
            "report": "soon",
            "import": [],
        }
    }
    path.write_text(json.dumps(damaged), "utf-8")
    assert app_settings.load().phase_history == {"build": [[10.0, 2.0], [7.0, 3.5]]}
    path.write_text(json.dumps({"phase_history": []}), "utf-8")
    assert app_settings.load().phase_history == {}
    long = {"phase_history": {"build": [[i, 1.0] for i in range(40)]}}
    path.write_text(json.dumps(long), "utf-8")
    assert len(app_settings.load().phase_history["build"]) == 10


def test_a_settings_file_with_the_wizard_language_of_1_4_loads_and_drops_it(
    _cache: Path, caplog
) -> None:
    """The wizard's translation went in 1.5.0 (T18.01): the key is ignored, without a warning,
    and the next save no longer writes it."""
    path = app_settings.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": "light", "language": "pt_BR"}), "utf-8")
    with caplog.at_level("WARNING"):
        old = app_settings.load()
    assert old.theme == "light" and not caplog.records
    assert not hasattr(old, "language")
    app_settings.save(old)
    assert "language" not in json.loads(path.read_text("utf-8"))


def test_the_orchestrator_remembers_the_phases_that_finished(_cache: Path) -> None:
    from types import SimpleNamespace

    from rpggen.core import orchestrator

    state = SimpleNamespace(
        timings={"preflight": 1.5, "stage": 0.5, "import": 30.0},  # import was running: no entry
        phases_done=["preflight", "stage"],
        catalog=SimpleNamespace(assets=[object()] * 40),
    )
    orchestrator._remember_times(state)  # a failed run records what it finished
    assert app_settings.load().phase_history == {"preflight": [[40.0, 1.5]], "stage": [[40.0, 0.5]]}
    orchestrator._remember_times(SimpleNamespace(timings={}, phases_done=[], catalog=None))
    state.catalog = None  # stopped before the catalog phase: the count is unknown
    orchestrator._remember_times(state)
    assert app_settings.load().phase_history["stage"] == [[40.0, 0.5], [0.0, 0.5]]


def test_the_cli_says_how_long_a_phase_usually_takes() -> None:
    from rpggen import cli
    from rpggen.core.orchestrator import PHASES_M1

    history = {name: [[10, 4.0], [10, 6.0]] for name in PHASES_M1}
    line = cli.phase_estimate_line(history, f"phase 10/11: {PHASES_M1[9]}")
    assert line.strip() == "usually about 5 s (about 10 s left)"
    assert cli.phase_estimate_line({}, "phase 1/11: preflight") == "", "no history: no line"
    assert cli.phase_estimate_line(history, "[godot] phase 1/11: preflight") == ""
    assert cli.phase_estimate_line(history, "phase 1/11: nonsense") == ""
    del history["report"]
    assert cli.phase_estimate_line(history, "phase 10/11: promote").strip() == "usually about 5 s"
