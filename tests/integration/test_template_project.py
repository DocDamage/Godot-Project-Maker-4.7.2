from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rpggen.core import godot

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]


def test_template_project_imports(godot_exe: Path, tmp_path: Path) -> None:
    project = tmp_path / "templates"
    shutil.copytree(
        REPO / "godot_templates", project, ignore=shutil.ignore_patterns(".godot", "results.json")
    )
    run = godot.import_project(godot_exe, project, tmp_path / "logs")
    assert run.returncode == 0, run.stdout
    assert not run.timed_out
    errors = [ln for ln in run.stdout.splitlines() + run.stderr.splitlines() if "ERROR:" in ln]
    assert errors == []
    # Godot must not rewrite the hand-written starter project.godot.
    original = (REPO / "godot_templates" / "project.godot").read_text(encoding="utf-8")
    assert (project / "project.godot").read_text(encoding="utf-8") == original
