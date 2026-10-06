from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fetch_godot", REPO / "tools" / "fetch_godot.py")
assert spec and spec.loader
fetch_godot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_godot)


def test_names_and_urls() -> None:
    assert fetch_godot.zip_name("4.7.2") == "Godot_v4.7.2-stable_win64.exe.zip"
    assert fetch_godot.console_name("4.7.2") == "Godot_v4.7.2-stable_win64_console.exe"
    assert fetch_godot.release_url("4.7.2", "SHA512-SUMS.txt") == (
        "https://github.com/godotengine/godot/releases/download/4.7.2-stable/SHA512-SUMS.txt"
    )


def test_parse_sums() -> None:
    text = "ABC123  Godot_v4.7.2-stable_win64.exe.zip\ndef456 *other.zip\n\nbadline\n"
    assert fetch_godot.parse_sums(text) == {
        "Godot_v4.7.2-stable_win64.exe.zip": "abc123",
        "other.zip": "def456",
    }
