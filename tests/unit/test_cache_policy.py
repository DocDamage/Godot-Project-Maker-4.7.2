from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import archive, cache_policy

# an old file time that every file system can hold: FAT32 (the F: drive of the owner's machine)
# keeps none before 1980, and only every other second
OLD = 400_000_000  # 1982-09-05


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "root"))
    return tmp_path / "root"


def _blob(path: Path, size: int, age_days: float = 0.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    when = time.time() - age_days * 86400
    os.utime(path, (when, when))
    return path


def _extracted(name: str, size: int, age_days: float) -> Path:
    folder = paths.cache_dir() / "extracted" / name
    _blob(folder / "a.png", size)
    _blob(folder.with_name(name + cache_policy.STAMP_SUFFIX), 0, age_days)
    return folder


# ------------------------------------------------------------------------ migration


def _legacy_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("RPGGEN_CACHE_DIR")
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(paths.sys, "platform", platform)
    return home


def test_migration_moves_settings_and_data_and_never_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _legacy_home(tmp_path, monkeypatch, "linux")
    old = home / ".cache" / "rpggen"  # everything lived here before M12
    _blob(old / "settings.json", 10)
    _blob(old / "drafts" / "a.json", 20)
    _blob(old / "profiles" / "p.rpgprofile.json", 30)
    _blob(old / "godot" / "4.7.2" / "godot.exe", 40)
    _blob(old / "extracted" / "abc" / "x.png", 50)
    _blob(old / "analysis" / "ab" / "x.json", 60)
    existing = _blob(home / ".local" / "share" / "rpggen" / "profiles" / "mine.json", 5)
    moved = cache_policy.migrate()
    assert len(moved) == 3 and all("->" in m for m in moved)  # settings, drafts, godot
    assert (home / ".config" / "rpggen" / "settings.json").is_file()
    assert (home / ".local" / "share" / "rpggen" / "drafts" / "a.json").is_file()
    assert (home / ".local" / "share" / "rpggen" / "godot" / "4.7.2" / "godot.exe").is_file()
    # the profiles folder of the new place exists: the old one stays and nothing is merged
    assert existing.is_file() and (old / "profiles" / "p.rpgprofile.json").is_file()
    assert (old / "extracted" / "abc" / "x.png").is_file()  # a cache stays where it is on Linux
    assert cache_policy.migrate() == []  # once


def test_on_macos_the_caches_move_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _legacy_home(tmp_path, monkeypatch, "darwin")
    old = home / ".cache" / "rpggen"
    _blob(old / "extracted" / "abc" / "x.png", 50)
    _blob(old / "settings.json", 10)
    cache_policy.migrate()
    assert (home / "Library" / "Caches" / "rpggen" / "extracted" / "abc" / "x.png").is_file()
    assert (home / "Library" / "Application Support" / "rpggen" / "settings.json").is_file()


def test_nothing_is_migrated_when_the_program_is_isolated() -> None:
    assert paths.legacy_cache_dir() is None and cache_policy.migrate() == []


# ------------------------------------------------------------------------ pruning


def test_the_least_recently_used_archives_go_first_and_the_one_in_use_stays() -> None:
    oldest = _extracted("aaa", 1000, age_days=30)
    middle = _extracted("bbb", 1000, age_days=10)
    newest = _extracted("ccc", 1000, age_days=1)
    removed = cache_policy.prune_extracted(2500, keep=[oldest])
    assert removed == ["bbb"]  # the oldest is in use: the next one goes
    assert oldest.is_dir() and newest.is_dir() and not middle.is_dir()
    assert not cache_policy.stamp_path(middle).exists()  # its stamp goes with it
    assert cache_policy.prune_extracted(10_000) == []  # within the limit: nothing happens


def test_without_a_stamp_the_folder_time_counts_and_partials_are_left_alone() -> None:
    folder = _extracted("old", 100, 40)
    cache_policy.stamp_path(folder).unlink()
    os.utime(folder, (time.time() - 40 * 86400,) * 2)
    _extracted("new", 100, 1)
    partial = paths.cache_dir() / "extracted" / "half.partial"
    _blob(partial / "a.png", 100)
    assert cache_policy.prune_extracted(150) == ["old"]
    assert partial.is_dir()


def test_a_stamp_without_its_folder_is_removed() -> None:
    orphan = cache_policy.stamp_path(paths.cache_dir() / "extracted" / "gone")
    _blob(orphan, 0)
    _extracted("here", 10, 1)
    cache_policy.prune_extracted(10_000)
    assert not orphan.exists()


def test_analysis_inventories_and_thumbnails_share_one_cap() -> None:
    old = _blob(paths.cache_dir() / "analysis" / "a.json", 600, age_days=9)
    mid = _blob(paths.cache_dir() / "inventories" / "b.json", 600, age_days=5)
    new = _blob(paths.cache_dir() / "thumbs" / "c.png", 600, age_days=1)
    freed = cache_policy.prune_small_caches(cap_bytes=1300)
    assert freed == 600 and not old.exists() and mid.exists() and new.exists()


def test_a_download_left_for_a_week_is_dropped_and_a_fresh_one_resumes() -> None:
    stale = _blob(paths.data_dir() / "godot" / "x.zip.part", 10, age_days=8)
    stale_info = _blob(paths.data_dir() / "godot" / "x.zip.part.json", 10, age_days=8)
    fresh = _blob(paths.data_dir() / "godot" / "y.zip.part", 10, age_days=2)
    finished = _blob(paths.data_dir() / "godot" / "4.7.2" / "godot.exe", 10, age_days=30)
    assert cache_policy.prune_partial_downloads() == 2
    assert not stale.exists() and not stale_info.exists()
    assert fresh.exists() and finished.exists()


def test_prune_reports_what_it_did_and_uses_the_limit_in_gb() -> None:
    _extracted("aaa", 1000, 30)
    result = cache_policy.prune(limit_gb=0.0000001)  # about 107 bytes
    assert result["extracted"] == 1


def test_opening_an_archive_stamps_it(tmp_path: Path) -> None:
    source = tmp_path / "p.zip"
    with zipfile.ZipFile(source, "w") as zf:
        zf.writestr("a.txt", "x")
    pack = archive.open_pack(source, set())
    stamp = cache_policy.stamp_path(pack.root)
    assert stamp.is_file()
    os.utime(stamp, (OLD, OLD))
    archive.open_pack(source, set())  # a cache hit counts as a use
    assert stamp.stat().st_mtime > OLD + 86_400


# ------------------------------------------------------------------------ sizes and clearing


def test_sizes_per_category_and_clearing() -> None:
    _blob(paths.cache_dir() / "thumbs" / "a.png", 100)
    _blob(paths.data_dir() / "drafts" / "d.json", 7)
    sizes = cache_policy.category_sizes()
    assert sizes["thumbs"] == 100 and sizes["drafts"] == 7 and sizes["extracted"] == 0
    assert cache_policy.clear("thumbs") == 100
    assert not (paths.cache_dir() / "thumbs").exists()
    with pytest.raises(KeyError):
        cache_policy.clear("settings")
    assert set(cache_policy.DATA_LOSSES) == set(cache_policy.DATA_ITEMS)
