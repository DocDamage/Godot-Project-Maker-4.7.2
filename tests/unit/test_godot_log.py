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
    assert (
        godot_log.strip_ansi("\x1b[90m\x1b[1mERROR:\x1b[0m bad \x1b[?25hthing")
        == "ERROR: bad thing"
    )
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
            [sys.executable, "-c", code],
            timeout_s=30,
            env=dict(__import__("os").environ),
            on_line=seen.append,
            log_file=fh,
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


# ------------------------------------------------------------------ the first error (T15.21)


def test_first_error_of_a_script_error_names_the_file_and_the_line() -> None:
    found = godot_log.first_error(DIRTY)
    assert found is not None
    assert found.message == "Parse Error: Expected parameter name."
    assert (found.path, found.line) == ("res://x.gd", 3)  # read from the "at:" line under it
    assert found.sentence() == "Parse Error: Expected parameter name. (line 3 of res://x.gd)"


def test_first_error_of_an_engine_error_and_of_a_scene_parse_error() -> None:
    engine = godot_log.first_error(
        "Godot Engine v4.7.2\n"
        "WARNING: harmless\n"
        "ERROR: Failed loading resource: res://generated/objects/house.tscn.\n"
        "   at: _load (core/io/resource_loader.cpp:343)\n"
    )
    assert engine is not None and engine.path == "res://generated/objects/house.tscn"
    assert engine.line is None and engine.message.startswith("Failed loading resource")
    assert engine.sentence() == engine.message  # the path is in the message already
    scene = godot_log.first_error(
        "ERROR: Parse Error: Expected '=' [Resource file res://generated/maps/town.tscn:12]\n"
    )
    assert scene is not None and (scene.path, scene.line) == ("res://generated/maps/town.tscn", 12)
    parser = godot_log.first_error("Parser Error: Unexpected token at res://a.gd:7\nERROR: later")
    assert parser is not None and (parser.path, parser.line) == ("res://a.gd", 7)
    plain = godot_log.first_error("ERROR: out of memory\n   at: alloc (core/os/memory.cpp:77)\n")
    assert plain is not None and plain.path is None and plain.sentence() == "out of memory"


def test_a_log_without_an_error_has_no_first_error() -> None:
    assert godot_log.first_error(CLEAN) is None
    assert godot_log.first_error("") is None


def test_the_tail_is_the_last_lines_without_colour_codes() -> None:
    esc = chr(27)
    text = "\n".join(f"{esc}[31mline {n}{esc}[0m" for n in range(100))
    assert godot_log.tail(text, 3) == "line 97\nline 98\nline 99"
    assert len(godot_log.tail(text).splitlines()) == godot_log.TAIL_LINES
