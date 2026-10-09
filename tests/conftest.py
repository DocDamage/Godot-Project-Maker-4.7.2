from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The tests never read or write this computer's own rpggen folders: a generation records its
# phase times in the settings (T13.07), and a test run must not put its own into yours. CI sets
# the variable itself; a test that needs another folder sets it for itself.
if not os.environ.get("RPGGEN_CACHE_DIR"):
    _SESSION_DIR = tempfile.mkdtemp(prefix="rpggen_tests_")
    os.environ["RPGGEN_CACHE_DIR"] = _SESSION_DIR
    atexit.register(shutil.rmtree, _SESSION_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def godot_exe() -> Path:
    exe = os.environ.get("RPGGEN_GODOT")
    if not exe:
        pytest.skip("RPGGEN_GODOT is not set")
    return Path(exe)
