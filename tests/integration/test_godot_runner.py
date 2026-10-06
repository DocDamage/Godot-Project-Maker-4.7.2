from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import godot

pytestmark = pytest.mark.integration


def test_detect_version(godot_exe: Path) -> None:
    v = godot.detect_version(godot_exe)
    assert v[:2] == (4, 7)
    assert v[3] == "stable"


def test_run_godot_quit(godot_exe: Path, tmp_path: Path) -> None:
    project = tmp_path / "empty"
    project.mkdir()
    # --quit hangs on a project without a main scene, so give it a minimal one.
    (project / "project.godot").write_text(
        'config_version=5\n\n[application]\n\nconfig/name="t"\nrun/main_scene="res://main.tscn"\n',
        encoding="utf-8",
    )
    (project / "main.tscn").write_text(
        '[gd_scene format=3]\n\n[node name="Main" type="Node"]\n', encoding="utf-8"
    )
    run = godot.run_godot(
        godot.find_console_exe(godot_exe),
        project,
        ["--quit"],
        timeout_s=60,
        log_name="quit",
        log_dir=tmp_path / "logs",
    )
    assert run.returncode == 0
    assert not run.timed_out
    assert run.log_path.exists()
