from __future__ import annotations

import re
from pathlib import Path

from rpggen import paths

PATHS_GD = Path(__file__).resolve().parents[2] / "godot_templates" / "builder" / "lib" / "paths.gd"
CONST_RE = re.compile(r'const (\w+) := "res://([^"]*)"')


def _python_constants() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(paths).items()
        if name.isupper() and isinstance(value, str)
    }


def test_paths_gd_matches_paths_py() -> None:
    gd = dict(CONST_RE.findall(PATHS_GD.read_text(encoding="utf-8")))
    assert gd, "no constants parsed from paths.gd"
    assert gd == _python_constants()
