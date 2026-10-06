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
