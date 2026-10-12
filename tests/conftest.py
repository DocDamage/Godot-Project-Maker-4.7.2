from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The tests never read or write this computer's own rpggen folders: a generation records its
# phase times in the settings (T13.07), and a test run must not put its own into yours. CI sets
# the variable itself; a test that needs another folder sets it for itself.
_SESSION_DIR = ""
if not os.environ.get("RPGGEN_CACHE_DIR"):
    _SESSION_DIR = tempfile.mkdtemp(prefix="rpggen_tests_")
    os.environ["RPGGEN_CACHE_DIR"] = _SESSION_DIR
    atexit.register(shutil.rmtree, _SESSION_DIR, ignore_errors=True)

_EXIT_STATUS = 0


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _EXIT_STATUS  # noqa: PLW0603
    _EXIT_STATUS = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: pytest.Config) -> None:
    """A run that made a Qt application ends here, with the result it had. Python taking Qt
    down at its own exit now and then crashes after every test has passed (a segmentation
    fault on Linux with the newest PySide6: the CI run of 2026-10-09 on main, exit 139 after
    *1719 passed*), which fails a run that has nothing wrong. Everything pytest reports is
    written by now; what is skipped is the interpreter's own teardown."""
    widgets = sys.modules.get("PySide6.QtWidgets")
    if widgets is None or widgets.QApplication.instance() is None:
        return
    if _SESSION_DIR:
        shutil.rmtree(_SESSION_DIR, ignore_errors=True)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_EXIT_STATUS)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def godot_exe() -> Path:
    exe = os.environ.get("RPGGEN_GODOT")
    if not exe:
        pytest.skip("RPGGEN_GODOT is not set")
    return Path(exe)
