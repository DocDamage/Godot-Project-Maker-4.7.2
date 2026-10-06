from __future__ import annotations

import os
from pathlib import Path

import pytest

from rpggen import jsonio


def test_keys_sorted_and_trailing_newline() -> None:
    text = jsonio.dumps({"b": 1, "a": {"z": 1, "y": 2}})
    assert text.index('"a"') < text.index('"b"')
    assert text.index('"y"') < text.index('"z"')
    assert text.endswith("\n")
    assert text.startswith('{\n  "a"')


def test_float_rounding() -> None:
    assert '"x": 0.3\n' in jsonio.dumps({"x": 0.1 + 0.2})
    assert jsonio.dumps([1.23456789]) == "[\n  1.234568\n]\n"


def test_tuples_become_lists_and_sets_raise() -> None:
    assert jsonio.dumps({"p": (1, 2)}) == jsonio.dumps({"p": [1, 2]})
    with pytest.raises(TypeError):
        jsonio.dumps({"s": {1, 2}})


def test_unicode_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "u.json"
    jsonio.write(path, {"name": "Árbol ✓"})
    assert "Árbol ✓" in path.read_text(encoding="utf-8")
    assert jsonio.read(path) == {"name": "Árbol ✓"}


def test_write_uses_lf_only(tmp_path: Path) -> None:
    path = tmp_path / "lf.json"
    jsonio.write(path, {"a": [1, 2]})
    assert b"\r" not in path.read_bytes()


def test_write_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "a.json"
    jsonio.write(path, {"v": 1})
    before = path.read_bytes()

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        jsonio.write(path, {"v": 2})
    assert path.read_bytes() == before


def test_read_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(Exception) as ei:  # noqa: B017 - ValueError until T1.03, then RpgGenError
        jsonio.read(path)
    assert "bad.json" in str(ei.value)
