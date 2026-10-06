from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import dev

pytestmark = pytest.mark.integration


def test_godot_unit_tests_pass(godot_exe: Path) -> None:
    assert dev.godot_test(godot_exe) == 0
