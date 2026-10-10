from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from rpggen import paths  # noqa: E402
from rpggen.gui import app as gui_app  # noqa: E402
from rpggen.gui import translations  # noqa: E402


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return paths.cache_dir()


@pytest.fixture(autouse=True)
def _delete_closed_widgets(qapp):
    """pytest-qt closes a test's widgets and asks for their deletion, but no event loop runs
    between tests to carry it out, so every window of the session stayed alive. With the
    stylesheet of M15 that is slow: a theme change restyles every widget there is. This runs
    after qtbot's own teardown (it is set up first) and deletes what was asked to go."""
    yield
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(scope="session", autouse=True)
def _styled_app(qapp):
    gui_app.create_app()
    # the tests read English texts, whatever the machine's language or saved choice (T12.56)
    translations.install("en")
    return qapp
