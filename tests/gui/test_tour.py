"""The first-run tour of the Audit page (T13.09)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from rpggen import dev
from rpggen.core import app_settings
from rpggen.gui.pages import audit_page as audit_mod
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.widgets.tour import GAP, Tour, TourStep, place
from rpggen.gui.wizard import MainWindow, default_pages


def _window(
    qtbot, tmp_path: Path, size: tuple[int, int] = (1100, 720)
) -> tuple[MainWindow, AuditPage]:
    window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    audit = next(p for p in window.pages if isinstance(p, AuditPage))
    return window, audit


def _show_audit(window: MainWindow, audit: AuditPage) -> None:
    window.show_page(window.pages.index(audit))
    for _ in range(3):
        QApplication.processEvents()


def test_the_callout_steps_forwards_and_backwards_and_esc_skips(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(700, 500)
    layout = QVBoxLayout(host)
    first, second = QPushButton("first"), QLabel("second")
    layout.addWidget(first)
    layout.addStretch(1)
    layout.addWidget(second)
    host.show()
    tour = Tour(host, [TourStep(first, "One", "About the first."), TourStep(second, "Two", "End.")])
    ended: list[bool] = []
    tour.finished.connect(ended.append)
    assert not Tour(host, []).start()
    assert tour.start() and tour.isVisible() and tour.running
    assert "One" in tour.title_label.text() and tour.text_label.text() == "About the first."
    assert tour.count_label.text() == "1 of 2" and not tour.back_button.isEnabled()
    assert tour.accessibleName() == "One. About the first."
    # below the widget it is about, inside the host; the page under it is not covered by a dim
    assert tour.y() >= first.geometry().bottom() and host.rect().contains(tour.geometry())
    assert first.isEnabled() and tour.width() < host.width() // 2
    tour.next_button.click()
    assert tour.count_label.text() == "2 of 2" and tour.next_button.text() == "Done"
    assert tour.geometry().bottom() <= second.geometry().top(), "above a widget at the bottom"
    tour.back_button.click()
    assert tour.index == 0 and tour.next_button.text() == "Next"
    # the keyboard: Next has the focus, Tab reaches the others, Esc skips
    assert tour.next_button.isDefault()
    for button in (tour.skip_button, tour.back_button, tour.next_button):
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
    qtbot.keyClick(tour, Qt.Key.Key_Escape)
    assert ended == [True] and not tour.isVisible() and not tour.running
    # to the end
    assert tour.start()
    tour.next()
    tour.next()
    assert ended == [True, False] and not tour.isVisible()


def test_a_callout_is_placed_beside_its_widget_and_inside_the_window() -> None:
    host = QRect(0, 0, 800, 600)
    size = (320, 120)
    below = place(QRect(100, 50, 200, 30), size, host)
    assert below == QPoint(100, 50 + 30 - 1 + GAP)
    above = place(QRect(100, 560, 200, 30), size, host)
    assert above.y() + size[1] <= 560
    right_edge = place(QRect(700, 50, 90, 30), size, host)
    assert right_edge.x() + size[0] <= 800
    tall = place(QRect(0, 0, 300, 600), size, host)  # as tall as the window: to its right
    assert tall.x() >= 300 and tall.y() + size[1] <= 600
    for anchor in (QRect(0, 0, 800, 600), QRect(500, 0, 300, 600), QRect(-50, -50, 10, 10)):
        spot = place(anchor, size, host)
        assert host.contains(QRect(spot, QPoint(spot.x() + size[0] - 1, spot.y() + size[1] - 1)))


def test_the_tour_starts_once_and_is_seen_when_skipped(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_mod, "TOUR_DELAY_MS", 0)
    window, audit = _window(qtbot, tmp_path)
    assert app_settings.get().tours_seen == []
    _show_audit(window, audit)
    qtbot.waitUntil(lambda: audit.tour is not None and audit.tour.running, timeout=3000)
    tour = audit.tour
    assert tour is not None and tour.isVisible() and len(tour.steps) == 5
    assert "detected" in tour.title_label.text()
    # the page under it stays usable
    audit.grid.chips["chipAll"].click()
    assert audit.grid.visible_ids()
    tour.skip_button.click()
    assert not tour.isVisible()
    assert app_settings.load().tours_seen == ["audit"]
    # shown again: no tour
    window.show_page(0)
    _show_audit(window, audit)
    qtbot.wait(50)
    assert not audit.maybe_start_tour()
    assert audit.tour is None, "the finished tour went with the page; none started"


def test_walking_through_the_page_starts_no_tour_and_leaving_does_not_mark_it(
    qtbot, tmp_path, monkeypatch
) -> None:
    window, audit = _window(qtbot, tmp_path)
    # the sample's path: the page is entered and left at once on the way to the options
    window.show_page(window.pages.index(audit))
    window.show_page(window.pages.index(audit) + 1)
    assert not audit.maybe_start_tour(), "the page is not shown any more"
    assert audit.tour is None and app_settings.get().tours_seen == []
    # a tour that was running when the page was left comes back the next time
    _show_audit(window, audit)
    assert audit.start_tour()
    window.show_page(0)
    assert audit.tour is None
    assert app_settings.get().tours_seen == []
    # going through all five steps marks it seen as well
    _show_audit(window, audit)
    assert audit.maybe_start_tour()
    for _ in range(5):
        audit.tour.next_button.click()
    assert app_settings.load().tours_seen == ["audit"]


def test_help_show_the_tour_again_restarts_it(qtbot, tmp_path, monkeypatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: said.append(a[2]))
    app_settings.update(tours_seen=["audit", "other"])
    window, audit = _window(qtbot, tmp_path)
    assert window.tour_action.text() == "Show the tour again"
    # elsewhere: it is promised for the next visit of the Audit page
    window.show_page(0)
    assert not window.show_tour_again() and said and "next time" in said[0]
    assert app_settings.load().tours_seen == ["other"]
    # on the Audit page: at once
    app_settings.update(tours_seen=["audit"])
    monkeypatch.setattr(audit_mod, "TOUR_DELAY_MS", 10_000)
    _show_audit(window, audit)
    assert audit.tour is None
    window.tour_action.trigger()
    assert audit.tour is not None and audit.tour.running and audit.tour.index == 0
    assert app_settings.load().tours_seen == []


@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
def test_every_anchor_exists_at_the_minimum_window_size(qtbot, tmp_path, theme_name) -> None:
    from rpggen.gui import theme

    theme.apply_theme(theme_name, remember=False)
    try:
        window, audit = _window(qtbot, tmp_path, min(dev.layout_sizes().values()))
        _show_audit(window, audit)
        assert audit.start_tour()
        tour = audit.tour
        assert tour is not None
        for index, step in enumerate(tour.steps):
            tour.go(index)
            assert step.widget.isVisibleTo(audit), step.title
            assert step.widget.width() > 0 and step.widget.height() > 0, step.title
            assert step.title and step.text
            assert audit.rect().contains(tour.geometry()), f"{step.title}: {tour.geometry()}"
    finally:
        theme.apply_theme("dark", remember=False)
