from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def godot_exe() -> Path:
    exe = os.environ.get("RPGGEN_GODOT")
    if not exe:
        pytest.skip("RPGGEN_GODOT is not set")
    return Path(exe)
