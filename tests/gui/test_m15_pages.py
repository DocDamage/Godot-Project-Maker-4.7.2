"""M15, Part B: what the page cards promise beyond the look (T15.11 – T15.17, T15.21)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QWidget

from rpggen import dev
from rpggen.core import orchestrator
from rpggen.errors import Issue, Severity
from rpggen.gui import fixes, theme, workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.pages.generate_page import (
    ICON_DONE,
    ICON_FAILED,
    ICON_RUNNING,
    PHASES,
    GeneratePage,
)
from rpggen.gui.pages.mapping_page import MappingPage
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.widgets import buttons, card, stepper
from rpggen.gui.wizard import MainWindow, default_pages
from tests.gui.test_generate_results import _fail_result, _ok_result, _state

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def _no_godot_scan(monkeypatch):
    monkeypatch.setattr(workers, "find_working_godot", lambda *, callbacks: None)


def _window(qtbot, tmp_path, size: tuple[int, int]) -> MainWindow:
    if dev.ensure_real_font() is None:
        pytest.skip("no real font on this machine")
    window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    return window


def _page_of(window: MainWindow, kind: type) -> QWidget:
    page = next(p for p in window.pages if isinstance(p, kind))
    window.show_page(window.pages.index(page))
    for _ in range(3):
        QApplication.processEvents()
    return page


def _rect_in(widget: QWidget, ancestor: QWidget) -> QRect:
    return QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())


# ------------------------------------------------------------------ T15.11: Project


def test_the_empty_pack_list_is_a_drop_zone_with_the_sample_link(qtbot, tmp_path) -> None:
    page = ProjectPage()
    qtbot.addWidget(page)
    page.resize(830, 480)
    page.show()
    form = page.form
    assert not form.drop_zone.isHidden() and page.pack_list.isHidden()
    assert form.drop_zone.height() == 96
    assert not page.sample_button.isHidden() and page.sample_button.property("kind") == "quiet"
    assert page.sample_button.parentWidget() is form.drop_zone  # on the drop zone's line
    assert page.add_zip_button.parentWidget() is form.drop_zone
    assert page.remove_button.isHidden()
    pack = tmp_path / "pack"
    pack.mkdir()
    page.pack_list.add_path(pack)
    assert form.drop_zone.isHidden() and not page.pack_list.isHidden()
    assert page.sample_button.isHidden()  # adding a pack hides it
    assert not page.remove_button.isHidden() and not page.add_zip_button.isHidden()
    one = page.pack_list.height()
    for n in range(4):
        page.pack_list.add_path(tmp_path / f"p{n}")
    assert page.pack_list.height() == 3 * (one - 4) + 4  # grows to three cards, then scrolls
    # a dropped folder reaches the page from the drop zone as from the list
    page.pack_list.clear()
    dropped: list[list[Path]] = []
    form.drop_zone.on_paths_dropped = dropped.append
    form.drop_zone.on_paths_dropped([pack])
    assert dropped == [[pack]] and not form.drop_zone.isHidden()
    # the hints are placeholders; the label column is 140 px
    assert page.target_edit.placeholderText() == "Where the Godot project will be created"
    assert page.name_edit.placeholderText() == "1 to 64 characters"


def test_the_project_page_fits_the_smallest_window_until_the_third_pack(
    qtbot, tmp_path, monkeypatch
) -> None:
    from rpggen.core import godot
    from tests.gui.test_project_page import _settled

    if dev.ensure_real_font() is None:
        pytest.skip("no real font on this machine")
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    window = MainWindow(pages=default_pages())
    qtbot.addWidget(window)
    window.resize(880, 540)
    window.show()
    page = window.pages[0]
    assert isinstance(page, ProjectPage)
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "out" / "My Game"))
    _settled(qtbot, page)
    assert page.validate(window.state) == []
    for _ in range(3):
        QApplication.processEvents()
    bar = page.scroll_area.verticalScrollBar()
    assert bar.maximum() == 0  # one pack: nothing to scroll
    page.add_sources([SYNTH / "gutter32"])
    _settled(qtbot, page)
    for _ in range(3):
        QApplication.processEvents()
    assert page.pack_list.count() == 2 and bar.maximum() == 0  # two packs: still nothing


def test_the_godot_version_is_a_chip_beside_its_label(qtbot) -> None:
    from rpggen.gui.models.forms import FieldStatus

    page = ProjectPage()
    qtbot.addWidget(page)
    page.show()
    page.form.show_godot_chip(FieldStatus("Godot 4.7.2.stable", "ok"))
    chip = page.form.godot_chip
    assert chip.text() == "4.7.2.stable" and chip.property("kind") == "success"
    assert not chip.isHidden()
    page.form.show_godot_chip(FieldStatus("This is Godot 4.8.", "error"))
    assert chip.text() == "not usable" and chip.property("kind") == "danger"
    page.form.show_godot_chip(FieldStatus("Checking…"))
    assert chip.isHidden()


# ------------------------------------------------------------------ T15.12: Audit


@pytest.mark.parametrize("size", [(1100, 720), (880, 540)])
def test_the_audit_filter_row_wraps_and_profile_is_inside_the_page(qtbot, tmp_path, size) -> None:
    window = _window(qtbot, tmp_path, size)
    page = _page_of(window, AuditPage)
    grid = page.grid
    profile = _rect_in(page.profile_button, page)
    assert page.rect().contains(profile), (profile, page.rect())  # never clipped again
    assert page.tabs.cornerWidget() is None  # it left the tab strip
    row = [grid.chips[name] for name in ("chipAttention", "chipAuto", "chipConfirmed", "chipAll")]
    row += [grid.role_combo, grid.pack_combo, grid.search, grid.group_button, page.profile_button]
    lines = sorted({_rect_in(w, page).top() for w in row})
    # two lines in the default window with the font of Windows; the wider fallback font of the
    # offscreen platform on Linux needs a third there too
    two = size[0] >= 1100 and sys.platform == "win32"
    assert 1 <= len(lines) <= (2 if two else 3), lines
    # the footer under the grid: the queue line, the keys, Shortcuts (quiet)
    assert grid.queue_label.text() and "C Confirm" in grid.keys_label.text()
    assert grid.help_button.text() == "Shortcuts" and grid.help_button.property("kind") == "quiet"
    assert _rect_in(grid.help_button, grid).top() > _rect_in(grid.view, grid).bottom()
    # the folder toggle is an icon button whose words are its tooltip
    assert grid.group_button.text() == "" and grid.group_button.toolTip().startswith("Group by")
    assert grid.group_button.accessibleName() == "Group by folder"
    # the review line, its bar and Review mode are in the header
    assert page.review_button.parentWidget() is page.page_header
    assert page.progress_bar.width() == 200
    for name in ("chipAttention", "chipAuto", "chipConfirmed", "chipUnused"):
        assert not grid.chips[name].icon().isNull()  # the status dot, beside the word


def test_the_audit_detail_panel_has_four_sections(qtbot, tmp_path) -> None:
    window = _window(qtbot, tmp_path, (1100, 720))
    page = _page_of(window, AuditPage)
    page.grid.chips["chipAll"].click()
    model = page.grid.view.model()
    page.grid.view.setCurrentIndex(model.index(0, 0))
    QApplication.processEvents()
    detail = page.detail
    assert detail is not None and detail.objectName() == "assetDetail"
    assert list(detail.section_labels) == ["picture", "what", "how", "actions"]
    assert all(label.property("role") == "section" for label in detail.section_labels.values())
    assert detail.confirm_button.property("kind") == buttons.PRIMARY
    assert not detail.confirm_button.icon().isNull() and not detail.exclude_button.icon().isNull()
    assert detail.show_folder_button.toolTip() == "Show in folder"
    assert detail.show_folder_button.text() == ""  # an icon button on the path line
    assert detail.path_label.toolTip() == detail.path_label.text() != ""


# ------------------------------------------------------------------ T15.13: Mapping


def test_the_mapping_rows_are_compact_and_keep_their_controls(qtbot, tmp_path) -> None:
    window = _window(qtbot, tmp_path, (1100, 720))
    page = _page_of(window, MappingPage)
    assert len(page.rows) >= 9 and page.group_cards
    assert all(isinstance(c, card.Card) for c in page.group_cards.values())
    for role, row in page.rows.items():
        assert row.height() <= 64, (role, row.height())  # 85 px before
        for button in (row.choose_button, row.clear_button, row.audit_button):
            assert button.property("kind") == "quiet" and button.text() == ""
            assert button.toolTip() and button.accessibleName()
        assert row.choose_button.objectName() == f"choose_{role}"
        assert row.clear_button.objectName() == f"clear_{role}"
        assert row.audit_button.objectName() == f"audit_{role}"
        assert row.asset_combo.objectName() == f"asset_{role}"
    # the summary and Undo are in the header
    assert page.undo_button.parentWidget() is page.page_header
    assert page.summary_label.parentWidget() is page.page_header
    assert "required roles assigned" in page.summary_label.text()
    # World and Characters are both in view without scrolling
    visible = page.scroll_area.viewport().rect()
    for group in list(page.group_cards)[:2]:
        box = _rect_in(page.group_cards[group], page.scroll_area.viewport())
        assert visible.contains(box), group
    # the sound card's buttons are in its heading row
    sound = page.sound_section
    assert sound.property("card") is True
    assert _rect_in(sound.edit_button, sound).top() == _rect_in(sound.add_button, sound).top() or (
        sound.add_button.isHidden()
    )


def test_a_missing_role_has_a_warning_edge_and_the_placeholder_choice(qtbot) -> None:
    from tests.gui.test_mapping_page import _page

    page, _state_ = _page(qtbot, "basic16")
    missing = [row for row in page.rows.values() if not row.fallback_box.isHidden()]
    assigned = [row for row in page.rows.values() if row.fallback_box.isHidden()]
    assert missing and assigned
    for row in missing:
        assert row.property("edge") == "warning"
        assert row.status_label.text()[:1] in "⚠✖"  # said in words and a glyph too
    for row in assigned:
        assert row.property("edge") is None and "assigned" in row.status_label.text()


# ------------------------------------------------------------------ T15.14: Options


def test_the_options_page_puts_the_feature_cards_side_by_side(qtbot, tmp_path) -> None:
    window = _window(qtbot, tmp_path, (1100, 720))
    page = _page_of(window, OptionsPage)
    assert page.two_columns
    first, second = page.features.groups[0], page.features.groups[1]
    a, b = _rect_in(first, page), _rect_in(second, page)
    assert a.top() == b.top() and a.right() < b.left()
    assert a.width() >= 400 and abs(a.width() - b.width()) <= 2
    assert _rect_in(page.summary, page).bottom() < a.top()  # the summary stays on top
    assert page.presets.parentWidget() is page.page_header
    assert page.features_reset.parentWidget() is page.page_header
    assert page.features_reset.property("kind") == "quiet"
    assert page.features_reset.objectName() == "resetFeatures"
    window.resize(880, 540)
    for _ in range(3):
        QApplication.processEvents()
    assert not page.two_columns
    assert _rect_in(first, page).left() == _rect_in(second, page).left()  # one column
    assert page.advanced.objectName() == "advanced" and not page.advanced.header.icon().isNull()
    assert page.advanced.header.text() == "Advanced"


# ------------------------------------------------------------------ T15.15: Generate


def test_the_phase_rows_show_the_state_of_the_run(qtbot) -> None:
    page = GeneratePage()
    qtbot.addWidget(page)
    page.show()
    delegate = page.phase_list.itemDelegate()
    assert isinstance(delegate, stepper.StepDelegate) and delegate.compact

    def states() -> list[str]:
        return [page.phase_list.item(i).data(stepper.StateRole) for i in range(len(PHASES))]

    assert set(states()) == {stepper.PENDING}
    page.running = True
    build = PHASES.index("build")
    page._on_progress("build", build + 1, len(PHASES))
    assert states()[:build] == [stepper.DONE] * build
    assert states()[build] == stepper.RUNNING and states()[build + 1] == stepper.PENDING
    assert page.phase_list.item(build).data(stepper.LabelRole)  # the plain name beside it
    assert page.percent_label.text() == f"{round(100 * build / len(PHASES))} %"
    assert not page.progress.isTextVisible()
    # a check that did not run: the dash and the word, never a tick
    page._skipped["smoke"] = "VAL-021"
    page._set_icons({p: ICON_DONE for p in PHASES})
    smoke = page.phase_list.item(PHASES.index("smoke"))
    assert smoke.data(stepper.StateRole) == stepper.SKIPPED
    assert "skipped" in smoke.data(stepper.LabelRole)
    # a failure: the cross on the failed phase
    page._skipped.clear()
    page._durations = {"import": 3.0}
    icons = {p: ICON_DONE for p in PHASES[:build]}
    icons["build"] = ICON_FAILED
    page._set_icons(icons)
    assert states()[build] == stepper.ERROR
    assert page.phase_list.item(PHASES.index("import")).data(stepper.NoteRole) == "3 s"
    # the turning ring stands still with reduce motion and when nothing runs
    page._set_icons({"build": ICON_RUNNING})
    assert page._spinner.isActive() != theme.reduce_motion()
    page._set_icons({})
    assert not page._spinner.isActive()
    page.running = False
    # details: a quiet toggle, the log in a card
    assert page.details_button.property("kind") == "quiet" and page.log_card.isHidden()
    page.details_button.click()
    assert not page.log_card.isHidden() and page.details_button.text() == "Hide details"
    assert page.log_view.parentWidget() is page.log_card
    assert page.elapsed_label.parentWidget() is page.page_header


# ------------------------------------------------------------------ T15.17, T15.21: Results


def _results(qtbot, state) -> ResultsPage:
    page = ResultsPage()
    qtbot.addWidget(page)
    page.resize(900, 640)
    page.show()
    page.enter(state)
    return page


def _primaries(page: QWidget) -> list[str]:
    from PySide6.QtWidgets import QAbstractButton

    return [
        b.objectName()
        for b in page.findChildren(QAbstractButton)
        if b.property("kind") == buttons.PRIMARY and b.isVisibleTo(page)
    ]


def test_a_success_has_a_banner_the_main_action_and_stat_tiles(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path)
    state.run_result.run_id = "3f9a1c2e"
    page = _results(qtbot, state)
    assert page.banner.kind == card.SUCCESS and "generated" in page.header.text()
    assert page.run_label.text() == "Run 3f9a1c2e"
    assert _primaries(page) == ["openGodot"]  # one main action
    assert page.failure_row.isHidden() and page.log_card.isHidden()
    assert isinstance(page.picture_card, card.Card)
    for key, tile in page.count_tiles.items():
        assert isinstance(tile, card.Card) and page.count_labels[key].objectName() == f"count_{key}"
        assert page.count_labels[key].property("stat") is True
    assert page.bundle_button.parentWidget() is not page.failure_row  # with the other buttons
    assert page.page_header.title() == "Results"


def test_a_failure_shows_the_cause_the_log_tail_and_the_fix_buttons(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    result = _fail_result(tmp_path)
    logs = result.failed_staging / "rpggen" / "logs"
    lines = [f"line {n}" for n in range(60)] + ["ERROR: Failed loading resource: res://a.tscn."]
    (logs / "godot_build.log").write_text("\n".join(lines), encoding="utf-8")
    (logs / "godot_import.log").write_text("the import was fine", encoding="utf-8")
    issue = result.issues[0]
    issue.detail.update(
        {
            "cause": "Failed loading resource: res://a.tscn.",
            "log": "godot_build.log",
            "file": "res://assets/packs/basic16/tiles/ground.png",
        }
    )
    state.run_result = result
    page = _results(qtbot, state)
    assert page.banner.kind == card.DANGER and "failed" in page.header.text().lower()
    assert "build" in page.phase_label.text() and not page.phase_label.isHidden()
    assert _primaries(page) == []  # nothing is the main action after a failure
    # the action row is right under the banner
    assert not page.failure_row.isHidden()
    for button in (page.failed_button, page.logs_button, page.bundle_button):
        assert button.parentWidget() is page.failure_row and not button.icon().isNull()
    assert [b.objectName() for b in (page.failed_button, page.logs_button, page.bundle_button)] == [
        "openFailed",
        "viewLogs",
        "exportBundle",
    ]
    # the cause is under the issue's message
    assert "Godot said: Failed loading resource: res://a.tscn." in page.issue_list.item(0).text()
    # the last 30 lines of the failed phase's log (not of another phase)
    assert not page.log_card.isHidden() and page.shown_log == logs / "godot_build.log"
    shown = page.log_tail.toPlainText().splitlines()
    assert (
        len(shown) == 30 and shown[-1].startswith("ERROR: Failed loading") and shown[0] == "line 31"
    )
    assert "godot_build.log" in page.log_title.text()
    # the first problem is selected at once: its fix and its buttons are there without a click
    assert page.issue_list.currentRow() == 0 and page.fix_label.text() == "See the log."
    names = [b.objectName() for b in page.fix_buttons]
    assert names == ["fix_open_log", "fix_open_failed_folder"]  # no asset is named ground.png
    assert not page.fix_box.isHidden()
    viewed: list[str] = []
    page.run_viewer = lambda viewer: viewed.append(viewer.windowTitle())  # type: ignore[method-assign]
    page.fix_buttons[0].click()
    assert viewed == ["godot_build.log"]
    page.log_more_button.click()  # Show more: the whole file
    assert viewed == ["godot_build.log"] * 2
    opened: list[Path] = []
    page.open_path = opened.append  # type: ignore[method-assign]
    page.fix_buttons[1].click()
    assert opened == [result.failed_staging]


def test_the_detail_fixes_need_the_detail(qtbot, tmp_path) -> None:
    plain = Issue("BUILD-002", Severity.ERROR, "Recipe x failed.", "See the log.")
    assert fixes.fixes_for_issue(plain, names_asset=True, has_failed_folder=True) == ()
    logged = Issue("BUILD-002", Severity.ERROR, "m", "f", detail={"log": "godot_build.log"})
    assert fixes.fixes_for_issue(logged) == (fixes.OPEN_LOG,)
    assert fixes.fixes_for_issue(logged, has_failed_folder=True) == (
        fixes.OPEN_LOG,
        fixes.OPEN_FAILED_FOLDER,
    )
    named = Issue("VAL-013", Severity.ERROR, "m", "f", detail={"file": "res://x.png"})
    assert fixes.fixes_for_issue(named) == ()  # the file is not an asset of the catalog
    assert fixes.fixes_for_issue(named, names_asset=True) == (fixes.SHOW_ASSET,)
    # a code's own buttons come first
    both = Issue("ASSET-010", Severity.ERROR, "m", "f", detail={"role": "NPC", "log": "a.log"})
    assert [f.action for f in fixes.fixes_for_issue(both)] == ["use_placeholder", "open_log"]


def test_show_this_asset_lands_on_the_asset(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    asset = state.catalog.assets[0]
    result = _fail_result(tmp_path)
    result.issues[0].detail.update({"log": "build.log", "file": f"res://{asset.path}"})
    state.run_result = result
    page = _results(qtbot, state)
    assert page.asset_of_file(f"res://{asset.path}") == asset.id
    assert page.asset_of_file("res://generated/nothing_like_it.tscn") is None
    assert page.asset_of_file(None) is None
    shown: list[list[str]] = []
    page.showAssets.connect(shown.append)
    button = next(b for b in page.fix_buttons if b.objectName() == "fix_show_asset")
    assert button.text() == "Show this asset in the audit"
    button.click()
    assert shown == [[asset.id]]


def test_a_cancelled_run_has_an_info_banner(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    state.run_result = orchestrator.RunResult(
        False, tmp_path / "out", [], None, None, failed_phase="build", cancelled=True
    )
    page = _results(qtbot, state)
    assert page.banner.kind == card.INFO and "cancelled" in page.header.text()
    assert page.log_card.isHidden() and _primaries(page) == []
    state.run_result = None
    page.enter(state)
    assert page.banner.kind == card.INFO and "Nothing" in page.header.text()
