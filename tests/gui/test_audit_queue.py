from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget

from rpggen.core import catalog
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _page(qtbot, pack: str = "mixed", width: int = 1000) -> tuple[AuditPage, WizardState]:
    state = WizardState(pack_sources=[SYNTH / pack])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(width, 700)
    page.show()
    page.enter(state)
    return page, state


def _attention(page: AuditPage) -> list[str]:
    return page.grid.attention_ids()


def test_review_progress_counts_reviewed_and_attention(qtbot) -> None:
    page, state = _page(qtbot)
    done, attention, total = catalog.review_progress(state.catalog)
    assert total == len(state.catalog.assets) and done + attention <= total
    assert page.progress_label.text() == f"{done} of {total} reviewed - {attention} need attention"
    assert page.progress_bar.value() == done and page.progress_bar.maximum() == total


def test_chips_carry_counts_that_follow_edits_and_undo(qtbot) -> None:
    page, state = _page(qtbot)
    attention = len(_attention(page))
    assert page.grid.chips["chipAttention"].text() == f"Needs attention {attention}"
    assert page.grid.chips["chipAll"].text() == f"All {len(state.catalog.assets)}"
    first = _attention(page)[0]
    page.session.confirm([first])
    assert page.grid.chips["chipAttention"].text() == f"Needs attention {attention - 1}"
    assert "Confirmed" in page.grid.chips["chipConfirmed"].text()
    page.session.undo_stack.undo()
    assert page.grid.chips["chipAttention"].text() == f"Needs attention {attention}"
    done, att, total = catalog.review_progress(page.session.catalog)
    assert str(att) in page.progress_label.text()


def test_n_cycles_only_through_assets_that_need_attention(qtbot) -> None:
    page, _state = _page(qtbot)
    page.grid.chips["chipAll"].click()
    queue = _attention(page)
    assert len(queue) >= 2
    seen = []
    for _ in range(len(queue) + 1):
        page._on_quick_key("N")
        selected = page.grid.selected_ids()
        assert len(selected) == 1 and selected[0] in queue
        seen.append(selected[0])
    assert seen[: len(queue)] == queue  # in the order of the grid
    assert seen[-1] == queue[0]  # and it wraps
    page._on_quick_key("SHIFT+N")
    assert page.grid.selected_ids() == [queue[-1]]


def test_confirm_advances_to_the_next_asset_that_needs_attention(qtbot) -> None:
    page, _state = _page(qtbot)
    queue = _attention(page)
    assert len(queue) >= 2
    page.grid.select_ids([queue[0]])
    page._on_quick_key("C")
    assert page.session.catalog.asset(queue[0]).status == "CONFIRMED"
    assert page.grid.selected_ids() == [queue[1]]
    page._on_quick_key("X")
    assert page.session.catalog.asset(queue[1]).status == "UNUSED"
    if len(queue) > 2:
        assert page.grid.selected_ids() == [queue[2]]


def test_confirm_all_auto_detected_is_one_undo_step(qtbot) -> None:
    page, _state = _page(qtbot)
    auto = [a.id for a in page.session.catalog.assets if a.status == "AUTO_DETECTED"]
    assert auto
    assert page.grid.confirm_auto_button.isHidden()
    page.grid.chips["chipAuto"].click()
    assert not page.grid.confirm_auto_button.isHidden()
    before = page.session.undo_stack.count()
    page.grid.confirm_auto_button.click()
    assert page.session.undo_stack.count() == before + 1
    assert not [a for a in page.session.catalog.assets if a.status == "AUTO_DETECTED"]
    page.session.undo_stack.undo()
    assert len([a for a in page.session.catalog.assets if a.status == "AUTO_DETECTED"]) == len(auto)


def test_finishing_the_queue_says_so_and_points_at_next(qtbot) -> None:
    page, _state = _page(qtbot)
    pointed: list[bool] = []
    page.focus_next.connect(lambda: pointed.append(True))
    assert page.done_label.isHidden()
    page.session.confirm(_attention(page))
    assert not page.done_label.isHidden()
    assert "Everything that needed attention is done" in page.done_label.text()
    assert pointed == [True]


def test_selection_states_explain_themselves(qtbot) -> None:
    page, _state = _page(qtbot)
    assert "Select an asset to see and correct" in page.empty_label.text()
    page.grid.chips["chipAll"].click()
    ids = page.grid.visible_ids()[:5]
    page.grid.select_ids(ids)
    assert page.bulk.count_label.text() == "5 assets selected"
    page.grid.select_ids([])
    assert page.side.currentWidget() is page.empty_label


def test_the_detail_panel_shows_friendly_roles_and_a_why_line(qtbot) -> None:
    page, _state = _page(qtbot, "basic16")
    page.grid.chips["chipAll"].click()
    hero = next(a.id for a in page.session.catalog.assets if a.id.endswith("hero"))
    page.grid.select_ids([hero])
    detail = page.detail
    assert detail.role_combo.currentText() == "Player"
    assert detail.role_combo.currentData() == "PLAYER"
    assert detail.role_help.text() == "The character you control."
    assert detail.why_label.text().startswith("Why: ")
    assert "hero" in detail.why_label.text()


def test_no_toolbar_widget_is_squeezed_below_its_size_hint_at_1000_px(qtbot) -> None:
    page, _state = _page(qtbot, width=1000)
    page.resize(1000, 700)
    qtbot.wait(50)  # let the layouts settle
    for widget in (
        *page.grid.chips.values(),
        page.grid.role_combo,
        page.grid.pack_combo,
        page.grid.search,
        page.grid.thumb_slider,
        page.profile_button,
    ):
        if widget.isHidden():
            continue
        assert widget.width() >= widget.minimumSizeHint().width(), widget.objectName()
    assert page.profile_button.isVisible()
    assert page.grid.search.width() >= 160


def test_thumbnail_size_is_remembered_and_changes_the_grid(qtbot) -> None:
    from rpggen.core import app_settings

    page, _state = _page(qtbot)
    page.set_thumb_size(128)
    assert app_settings.get().thumb_size == 128
    app_settings.store().flush()  # the write waits a moment for the next change
    assert app_settings.load().thumb_size == 128
    assert page.grid.thumb_slider.value() == 2
    assert page.grid.view.gridSize().width() == 128 + 16
    assert page.grid.model.thumb_size == 128


def test_the_shortcut_sheet_lists_the_current_roles(qtbot) -> None:
    page, _state = _page(qtbot)
    sheet = page.shortcut_sheet()
    assert "N / Shift+N" in sheet and "1  Ground tiles" in sheet and "C  confirm" in sheet
    assert isinstance(page.grid.help_button.parent(), QWidget)


# ------------------------------------------------------------------------ layout (T12.14)


def test_the_grid_gets_the_spare_height_not_the_done_label(qtbot) -> None:
    from PySide6.QtWidgets import QApplication

    page, _state = _page(qtbot, width=900)
    # everything reviewed: the done label shows, and still the splitter takes the room
    for asset in page.session.catalog.assets:
        if asset.status != "CONFIRMED":
            page.session.confirm([asset.id])
    assert not page.done_label.isHidden()
    QApplication.processEvents()
    layout = page.layout()
    margins = layout.contentsMargins()
    spacing = layout.spacing() if layout.spacing() >= 0 else 6
    taken = page.done_label.height() + page.progress_label.height() + 4  # the progress row
    taken += 2 * spacing + margins.top() + margins.bottom()
    assert page.splitter.height() >= page.height() - taken - 8
    assert page.done_label.height() <= page.done_label.sizeHint().height() + 8
