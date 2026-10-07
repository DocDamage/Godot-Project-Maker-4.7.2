from __future__ import annotations

import importlib.util
from pathlib import Path

from rpggen import godot_target
from rpggen.core import config, godot, godot_fetch, staging

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bump_godot", REPO / "tools" / "bump_godot.py")
assert spec and spec.loader
bump_godot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump_godot)


def test_everything_reads_the_single_version() -> None:
    assert godot.SUPPORTED_VERSION == godot_target.SUPPORTED
    assert godot_fetch.DEFAULT_VERSION == godot_target.VERSION
    assert config.GODOT_VERSION == godot_target.VERSION
    assert f'("{godot_target.MAJOR_MINOR}")' in staging.minimal_project_godot("x")


def test_workflows_and_error_texts_agree_with_the_single_version() -> None:
    assert bump_godot.check() == []


def test_a_patch_bump_changes_only_the_full_version() -> None:
    text = "Godot {found} is not supported: builds projects for Godot 4.7. Use 4.7.2 or 4.7.x"
    assert bump_godot.rewrite_spec(text, "4.7.2", "4.7.3") == (
        "Godot {found} is not supported: builds projects for Godot 4.7. Use 4.7.3 or 4.7.x"
    )


def test_a_minor_bump_changes_the_series_too_but_not_other_numbers() -> None:
    text = "builds projects for Godot 4.7. Use 4.7.2 or 4.7.x; need 14.7 MB, 4.70 stays"
    got = bump_godot.rewrite_spec(text, "4.7.2", "4.8.1")
    assert got == "builds projects for Godot 4.8. Use 4.8.1 or 4.8.x; need 14.7 MB, 4.70 stays"
