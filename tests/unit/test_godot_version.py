from __future__ import annotations

import os
from pathlib import Path

import pytest

from rpggen.core import godot
from rpggen.errors import RpgGenError


def test_parse_version_examples() -> None:
    assert godot.parse_version("4.7.2.stable.official.abc123") == (4, 7, 2, "stable")
    assert godot.parse_version("4.7.stable.official.x") == (4, 7, 0, "stable")
    assert godot.parse_version("\n\n4.7.1.stable.official.a13da4feb\n") == (4, 7, 1, "stable")
    assert godot.parse_version("4.8.dev1.custom_build") == (4, 8, 0, "dev1")


def test_parse_version_garbage() -> None:
    with pytest.raises(RpgGenError) as ei:
        godot.parse_version("not a version at all, really not, nope nope nope nope")
    assert ei.value.code == "ENV-002"
    assert ei.value.detail["found"] == "not a version at all, really not, nope n"


def test_check_version() -> None:
    assert godot.check_version((4, 7, 2, "stable")) == []
    issues = godot.check_version((4, 7, 1, "stable"))
    assert [i.code for i in issues] == ["ENV-003"]
    assert issues[0].severity.value == "warning"
    for bad in [(4, 6, 2, "stable"), (4, 7, 2, "rc1"), (3, 5, 0, "stable"), (4, 7, 0, "dev1")]:
        with pytest.raises(RpgGenError) as ei:
            godot.check_version(bad)
        assert ei.value.code == "ENV-002"


def test_find_console_exe(tmp_path: Path) -> None:
    gui = tmp_path / "Godot_v4.7.2-stable_win64.exe"
    gui.write_bytes(b"")
    assert godot.find_console_exe(gui) == gui
    console = tmp_path / "Godot_v4.7.2-stable_win64_console.exe"
    console.write_bytes(b"")
    assert godot.find_console_exe(gui) == console
    assert godot.find_console_exe(console) == console
    other = tmp_path / "godot"
    other.write_bytes(b"")
    assert godot.find_console_exe(other) == other


def test_detect_version_missing_exe(tmp_path: Path) -> None:
    with pytest.raises(RpgGenError) as ei:
        godot.detect_version(tmp_path / "nope.exe")
    assert ei.value.code == "ENV-001"


def test_auto_find_godot_uses_env_and_sorts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = tmp_path / "b" / "godot_b.exe"
    b = tmp_path / "a" / "Godot_a.exe"
    for p in (a, b):
        p.parent.mkdir(parents=True)
        p.write_bytes(b"")
    monkeypatch.setenv("RPGGEN_GODOT", str(a))
    monkeypatch.setenv("PATH", f"{a.parent}{os.pathsep}{b.parent}")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "none"))
    result = godot.auto_find_godot("windows")
    assert result == [b, a]


@pytest.mark.skipif(os.name != "nt", reason="uses a .cmd stand-in")
def test_run_godot_timeout_kills_and_logs(tmp_path: Path) -> None:
    fake = tmp_path / "fake_godot.cmd"
    fake.write_bytes(b"@echo off\r\necho started\r\nping -n 30 127.0.0.1 >nul\r\n")
    run = godot.run_godot(fake, tmp_path, [], timeout_s=2, log_name="t", log_dir=tmp_path / "logs")
    assert run.timed_out
    assert run.log_path == tmp_path / "logs" / "godot_t.log"
    assert run.log_path.exists()


@pytest.mark.skipif(os.name != "nt", reason="uses a .cmd stand-in")
def test_run_godot_nonzero_exit_does_not_raise(tmp_path: Path) -> None:
    fake = tmp_path / "fake_godot.cmd"
    fake.write_bytes(b"@echo off\r\necho boom\r\nexit /b 3\r\n")
    run = godot.run_godot(fake, tmp_path, [], timeout_s=20, log_name="x", log_dir=tmp_path)
    assert run.returncode == 3
    assert "boom" in run.log_path.read_text(encoding="utf-8")
    assert not run.timed_out


def test_run_godot_missing_exe(tmp_path: Path) -> None:
    with pytest.raises(RpgGenError) as ei:
        godot.run_godot(
            tmp_path / "nope.exe", tmp_path, [], timeout_s=5, log_name="x", log_dir=tmp_path
        )
    assert ei.value.code == "ENV-001"
