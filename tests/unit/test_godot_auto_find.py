"""T12.63: auto_find_godot looks in the usual places of each OS."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import godot, godot_fetch


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """No PATH, no RPGGEN_GODOT, no managed copy, a home of our own."""
    monkeypatch.delenv("RPGGEN_GODOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("PATH", "")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(godot_fetch, "managed_dir", lambda version=None: tmp_path / "managed")
    monkeypatch.setattr(godot, "MAC_APP_DIRS", (tmp_path / "Applications",))
    return tmp_path


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    path.chmod(0o755)
    return path


def test_linux_looks_in_local_bin_and_path(isolated: Path, monkeypatch) -> None:
    local = _touch(isolated / "home/.local/bin/Godot_v4.7.2-stable_linux.x86_64")
    on_path = _touch(isolated / "bin/godot4")
    _touch(isolated / "home/.local/bin/other")
    monkeypatch.setenv("PATH", str(isolated / "bin"))
    assert godot.auto_find_godot("linux") == sorted(
        [local, on_path], key=lambda p: str(p).casefold()
    )


def test_macos_looks_in_applications(isolated: Path) -> None:
    exe = _touch(isolated / "Applications/Godot.app/Contents/MacOS/Godot")
    _touch(isolated / "Applications/Other.app/Contents/MacOS/Other")
    assert godot.auto_find_godot("macos") == [exe]


def test_windows_looks_in_local_programs(isolated: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(isolated / "local"))
    exe = _touch(isolated / "local/Programs/Godot/Godot_v4.7.2-stable_win64_console.exe")
    _touch(isolated / "home/.local/bin/godot")  # a Linux place: not searched on Windows
    assert godot.auto_find_godot("windows") == [exe]


def test_the_managed_copy_of_this_platform_comes_first(isolated: Path) -> None:
    managed = _touch(isolated / "managed" / godot_fetch.console_name("4.7.2", "macos"))
    other = _touch(isolated / "Applications/Godot.app/Contents/MacOS/Godot")
    assert godot.auto_find_godot("macos") == [managed, other]
