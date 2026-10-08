from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import paths


def test_glob_match() -> None:
    assert paths.glob_match("Characters/Enemies/bat.png", "characters/enemies/**")
    assert not paths.glob_match("a/b", "*")
    assert paths.glob_match("a", "*")
    assert paths.glob_match("x.png", "**/*.png")
    assert paths.glob_match("a/b/c/x.png", "**/*.png")
    assert not paths.glob_match("a/x.jpg", "**/*.png")
    assert paths.glob_match("a/b.png", "a/?.png")
    assert not paths.glob_match("a/bb.png", "a/?.png")
    assert not paths.glob_match("a//.png", "a/?.png")


def test_posix_rel_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "assets" / "x.png"
    rel = paths.to_posix_rel(p, tmp_path)
    assert rel == "assets/x.png"
    assert paths.from_posix_rel(rel, tmp_path) == p


def test_to_posix_rel_outside_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        paths.to_posix_rel(tmp_path.parent / "other", tmp_path)


@pytest.mark.parametrize("bad", ["../x", "a/../b", "/abs", "C:/x", "a\\b", ""])
def test_from_posix_rel_rejects(bad: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        paths.from_posix_rel(bad, tmp_path)


def test_local_cache_dir_is_absolute() -> None:
    assert paths.local_cache_dir().is_absolute()


# ------------------------------------------------------------------------ three folders (T12.10)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake home folder, no override and no XDG variables."""
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: folder))
    for name in ("RPGGEN_CACHE_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)
    return folder


def test_windows_keeps_three_folders_below_localappdata(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    root = tmp_path / "Local" / "rpggen"
    assert paths.config_dir() == root / "config"
    assert paths.data_dir() == root / "data"
    assert paths.cache_dir() == root / "cache"
    assert paths.log_dir() == root / "data" / "logs"
    assert paths.legacy_cache_dir() == root / "cache"  # where everything used to live


def test_linux_follows_the_xdg_folders(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths.sys, "platform", "linux")
    assert paths.config_dir() == home / ".config" / "rpggen"
    assert paths.data_dir() == home / ".local" / "share" / "rpggen"
    assert paths.cache_dir() == home / ".cache" / "rpggen"
    assert paths.legacy_cache_dir() == home / ".cache" / "rpggen"
    for variable, folder in (
        ("XDG_CONFIG_HOME", "c"),
        ("XDG_DATA_HOME", "d"),
        ("XDG_CACHE_HOME", "k"),
    ):
        monkeypatch.setenv(variable, str(tmp_path / folder))
    assert paths.config_dir() == tmp_path / "c" / "rpggen"
    assert paths.data_dir() == tmp_path / "d" / "rpggen"
    assert paths.cache_dir() == tmp_path / "k" / "rpggen"
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/is/ignored")  # the spec says absolute only
    assert paths.cache_dir() == home / ".cache" / "rpggen"


def test_macos_uses_application_support_and_caches(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    support = home / "Library" / "Application Support" / "rpggen"
    assert paths.config_dir() == support and paths.data_dir() == support
    assert paths.cache_dir() == home / "Library" / "Caches" / "rpggen"


def test_the_override_puts_the_three_folders_under_one_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "root"))
    root = tmp_path / "root"
    assert paths.config_dir() == root / "config"
    assert paths.data_dir() == root / "data"
    assert paths.cache_dir() == root / "cache" and paths.local_cache_dir() == paths.cache_dir()
    assert paths.legacy_cache_dir() is None  # nothing to migrate when isolated
