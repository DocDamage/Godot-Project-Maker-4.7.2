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


def test_colour_codes_are_stripped() -> None:
    assert godot_log.strip_ansi("\x1b[90m\x1b[1mERROR:\x1b[0m bad \x1b[?25hthing") == "ERROR: bad thing"
    assert godot_log.strip_ansi("plain [90m text") == "plain [90m text"  # no escape: left alone


def test_a_coloured_line_is_plain_in_the_callback_the_log_and_the_output(tmp_path) -> None:
    import sys

    from rpggen.core import godot

    seen: list[str] = []
    code = (
        "import sys; e = chr(27); print(e + '[91mERROR:' + e + '[0m red'); "
        "print(e + '[1mbold' + e + '[0m', file=sys.stderr)"
    )
    log_path = tmp_path / "run.log"
    with open(log_path, "w", encoding="utf-8") as fh:
        _code, out, err, _t, _c = godot._run(
            [sys.executable, "-c", code], timeout_s=30, env=dict(__import__("os").environ),
            on_line=seen.append, log_file=fh,
        )
    assert out.strip() == "ERROR: red" and err.strip() == "bold"
    assert sorted(seen) == ["ERROR: red", "bold"]
    assert "\x1b" not in log_path.read_text(encoding="utf-8")


def test_godot_is_asked_not_to_colour(tmp_path, monkeypatch) -> None:
    from rpggen.core import godot

    got: dict[str, str] = {}

    def fake_run(cmd, *, env, **_kwargs):  # type: ignore[no-untyped-def]
        got.update(env)
        return 0, "", "", False, False

    monkeypatch.setattr(godot, "_run", fake_run)
    godot.run_godot(tmp_path / "godot", tmp_path, [], timeout_s=5, log_name="x", log_dir=tmp_path)
    assert got["NO_COLOR"] == "1" and got["RPGGEN"] == "1"
