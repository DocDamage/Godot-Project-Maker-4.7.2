from __future__ import annotations

import pytest

from rpggen.core import godot_log

CLEAN = """Godot Engine v4.7.2.stable.official - https://godotengine.org
[rpggen] INFO build finished ok=true
WARNING: something harmless
"""

DIRTY = """Godot Engine v4.7.2.stable.official
SCRIPT ERROR: Parse Error: Expected parameter name.
   at: GDScript::reload (res://x.gd:3)
ERROR: Failed to load script "res://x.gd" with error "Parse error".
ERROR: [RPG-PLAYER] visual_path does not point to an AnimatedSprite2D
"""


def test_clean_log_has_no_issues() -> None:
    assert godot_log.scan(CLEAN) == []
    assert godot_log.scan("") == []


def test_dirty_log_yields_val013_per_line() -> None:
    issues = godot_log.scan(DIRTY)
    assert [i.code for i in issues] == ["VAL-013"] * 3
    assert "Parse Error" in issues[0].detail["line"]
    assert "[RPG-PLAYER]" in issues[2].message
    assert all(i.severity.value == "error" for i in issues)


def test_ignore_patterns_are_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(godot_log, "IGNORED_ERROR_PATTERNS", ["Failed to load script"])
    assert [i.detail["line"] for i in godot_log.scan(DIRTY)] == [
        "SCRIPT ERROR: Parse Error: Expected parameter name.",
        "ERROR: [RPG-PLAYER] visual_path does not point to an AnimatedSprite2D",
    ]


def test_ignore_list_starts_empty() -> None:
    assert godot_log.IGNORED_ERROR_PATTERNS == []
