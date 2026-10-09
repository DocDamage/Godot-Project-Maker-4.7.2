"""Audit review mode (T13.01): one asset at a time over the page's own session and detail panel."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from rpggen import dev
from rpggen.core import catalog
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import app as gui_app
from rpggen.gui import theme, window_menus, workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.wizard import MainWindow, default_pages

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _page(qtbot, pack: str = "mixed") -> AuditPage:
    state = WizardState(pack_sources=[SYNTH / pack])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    page.enter(state)
    QApplication.processEvents()
    return page


def _shown(page: AuditPage) -> str | None:
    assert page.detail is not None
    return page.detail.asset_id


def test_entering_shows_the_first_of_the_queue_and_n_advances(qtbot) -> None:
    page = _page(qtbot)
    queue = page.grid.attention_ids()
    assert len(queue) >= 3
    assert not page.in_review_mode
    assert page.set_review_mode(True)
    assert page.in_review_mode and page.review_button.isChecked()
    assert _shown(page) == queue[0]
    assert page.review.counter_label.text() == f"1 of {len(queue)} need attention"
    # the same detail panel, moved beside the large preview; its own picture is off
    assert page.detail_scroll.parentWidget() is page.review
    assert page.detail is not None and not page.detail.preview.isVisible()
    assert (
        "C Confirm" in page.review.keys_label.text() and "N Next" in page.review.keys_label.text()
    )
    qtbot.keyClick(page.review, Qt.Key.Key_N)
    assert _shown(page) == queue[1]
    assert page.review.counter_label.text() == f"2 of {len(queue)} need attention"
    qtbot.keyClick(page.review, Qt.Key.Key_N, Qt.KeyboardModifier.ShiftModifier)
    assert _shown(page) == queue[0]


def test_c_confirms_and_advances_and_esc_returns_with_that_asset_selected(qtbot) -> None:
    page = _page(qtbot)
    queue = page.grid.attention_ids()
    page.set_review_mode(True)
    qtbot.keyClick(page.review, Qt.Key.Key_C)
    assert page.session is not None
    assert page.session.catalog.asset(queue[0]).status == "CONFIRMED"
    assert _shown(page) == queue[1], "the next one that needs attention"
    assert page.review.counter_label.text() == f"1 of {len(queue) - 1} need attention"
    qtbot.keyClick(page.review, Qt.Key.Key_Escape)
    assert not page.in_review_mode and not page.review_button.isChecked()
    assert page.grid.selected_ids() == [queue[1]]
    # the panel is back in the side stack, with its picture
    assert page.side.currentWidget() is page.detail_scroll
    assert page.detail is not None and page.detail.show_preview
    assert _shown(page) == queue[1]


def test_an_edit_in_review_mode_is_one_undo_step_also_after_leaving(qtbot) -> None:
    page = _page(qtbot)
    queue = page.grid.attention_ids()
    assert page.session is not None
    before = catalog.effective(page.session.catalog.asset(queue[0])).get("role")
    steps = page.session.undo_stack.count()
    page.set_review_mode(True)
    qtbot.keyClick(page.review, Qt.Key.Key_1)  # the first quick role
    after = catalog.effective(page.session.catalog.asset(queue[0])).get("role")
    assert after == page.quick_roles[0]
    assert page.session.undo_stack.count() == steps + 1
    page.set_review_mode(False)
    page.session.undo_stack.undo()
    assert catalog.effective(page.session.catalog.asset(queue[0])).get("role") == before
    assert page.session.undo_stack.count() == steps + 1 and page.session.undo_stack.index() == steps


def test_with_an_empty_queue_the_mode_walks_the_filter(qtbot) -> None:
    page = _page(qtbot)
    assert page.session is not None
    page.session.confirm([a.id for a in page.session.catalog.assets if a.status != "CONFIRMED"])
    assert page.grid.attention_ids() == []
    page.grid.chips["chipAll"].click()
    order = page.grid.visible_ids()
    page.set_review_mode(True)
    assert _shown(page) == order[0]
    assert page.review.counter_label.text() == f"Nothing needs attention · 1 of {len(order)} shown"
    qtbot.keyClick(page.review, Qt.Key.Key_N)
    assert _shown(page) == order[1]
    qtbot.keyClick(page.review, Qt.Key.Key_N, Qt.KeyboardModifier.ShiftModifier)
    qtbot.keyClick(page.review, Qt.Key.Key_N, Qt.KeyboardModifier.ShiftModifier)
    assert _shown(page) == order[-1], "it wraps"


def test_a_sound_has_a_note_instead_of_a_picture(qtbot) -> None:
    page = _page(qtbot, "audio_basic")
    assert page.session is not None
    sound = next(a for a in page.session.catalog.assets if a.kind == "audio")
    page.grid.chips["chipAll"].click()
    page.grid.select_ids([sound.id])
    page.session.confirm([a.id for a in page.session.catalog.assets if a.status != "CONFIRMED"])
    page.set_review_mode(True)
    assert _shown(page) == sound.id
    assert not page.review.preview.isVisible() and page.review.no_picture_label.isVisible()
    assert sound.path.rsplit("/", 1)[-1] in page.review.no_picture_label.text()


def test_leaving_the_page_leaves_the_mode(qtbot) -> None:
    page = _page(qtbot)
    page.set_review_mode(True)
    assert page.state is not None
    page.leave(page.state)
    assert not page.in_review_mode


def test_f7_is_in_the_view_menu_and_in_the_shortcut_lists(qtbot, tmp_path: Path) -> None:
    assert any(keys == "F7" for keys, _what in window_menus.SHORTCUTS)
    assert "F7" in window_menus.shortcuts_text()
    window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
    qtbot.addWidget(window)
    window.show()
    assert window.review_action.shortcut().toString() == "F7"
    audit = window._audit_page()
    assert "F7" in audit.shortcut_sheet()
    window.toggle_review_mode()  # not on the Audit page: nothing happens
    assert not audit.in_review_mode
    window.show_page(window.pages.index(audit))
    QApplication.processEvents()
    window.review_action.trigger()
    assert audit.in_review_mode
    window._sync_review_action()
    assert window.review_action.isChecked()
    window.review_action.trigger()
    assert not audit.in_review_mode


@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
def test_review_mode_fits_at_the_minimum_window_size(qtbot, tmp_path: Path, theme_name) -> None:
    from tests.gui.test_layout_fit import layout_problems

    gui_app.create_app()
    original = QApplication.font()
    if dev.ensure_real_font() is None:
        pytest.skip("no real font on this machine")
    try:
        theme.apply_theme(theme_name, remember=False)
        window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
        qtbot.addWidget(window)
        width, height = min(dev.layout_sizes().values())
        window.resize(width, height)
        window.show()
        audit = window._audit_page()
        window.show_page(window.pages.index(audit))
        for _ in range(3):
            QApplication.processEvents()
        assert audit.set_review_mode(True)
        for _ in range(3):
            QApplication.processEvents()
        assert layout_problems(audit) == []
    finally:
        QApplication.setFont(original)
        theme.apply_theme("dark", remember=False)
