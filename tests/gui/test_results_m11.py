from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from rpggen.core import orchestrator
from rpggen.errors import Issue, Severity
from rpggen.gui import workers
from rpggen.gui.pages.generate_page import ICON_DONE, PHASE_LABELS, PHASES, GeneratePage
from rpggen.gui.pages.results_page import ResultsPage
from tests.gui.test_generate_results import _fail_result, _ok_result, _state


def _results(qtbot, state) -> ResultsPage:
    page = ResultsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page


def test_success_leads_with_the_picture_and_a_what_next_list(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path)
    results = state.run_result.target / "rpggen" / "results"
    results.mkdir(parents=True)
    Image.new("RGBA", (200, 120), (10, 120, 10, 255)).save(results / "starter_map.png")
    page = _results(qtbot, state)
    assert not page.success_box.isHidden()
    assert not page.map_picture.pixmap().isNull()
    text = page.what_next_label.text()
    assert "F5" in text and "game/maps/starter_map.tscn" in text and "README.md" in text
    opened: list[Path] = []
    page.open_path = opened.append  # type: ignore[method-assign]
    page._on_next_link("show:README.md")
    page.map_picture.clicked.emit()
    assert opened == [state.run_result.target / "README.md", results / "starter_map.png"]
    assert page.godot_button.property("primary") is True


def test_success_without_a_picture_says_so(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path)
    page = _results(qtbot, state)
    assert "No picture" in page.map_picture.text()


def test_warnings_show_their_fix_inline_and_the_ending_buttons_work(qtbot, tmp_path: Path) -> None:
    warning = Issue("ASSET-014", Severity.WARNING, "No NPC.", "Add an NPC sprite.")
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path, [warning])
    page = _results(qtbot, state)
    assert "Fix: Add an NPC sprite." in page.issue_list.item(0).text()
    seen: list[str] = []
    page.generateAnother.connect(lambda: seen.append("another"))
    page.changeOptions.connect(lambda: seen.append("options"))
    page.another_button.click()
    page.options_button.click()
    assert seen == ["another", "options"]
    assert page.project_button.isHidden()


def test_a_failure_leads_with_a_plain_sentence_and_an_env_problem_offers_the_project_page(
    qtbot, tmp_path: Path
) -> None:
    state = _state(tmp_path)
    result = _fail_result(tmp_path)
    result.issues.append(
        Issue("ENV-002", Severity.ERROR, "Godot 4.2 is not supported.", "Download.")
    )
    state.run_result = result
    page = _results(qtbot, state)
    assert page.phase_label.text().startswith("Godot could not build the game.")
    assert not page.project_button.isHidden()
    assert page.another_button.isHidden() and page.options_button.isHidden()
    goto: list[bool] = []
    page.goToProject.connect(lambda: goto.append(True))
    page.project_button.click()
    assert goto == [True]


def test_every_phase_has_a_plain_label_and_the_page_shows_durations(
    qtbot, tmp_path, monkeypatch
) -> None:
    assert set(PHASE_LABELS) == set(PHASES)
    state = _state(tmp_path)

    def quick(
        cfg,
        cat,
        target,
        godot,
        placeholders,
        git_message=None,
        force=False,
        accept=False,
        *,
        callbacks,
    ):
        for i, name in enumerate(PHASES, start=1):
            callbacks.on_phase(name, i, len(PHASES))
            time.sleep(0.002)
        result = _ok_result(tmp_path)
        result.timings = {name: 2.0 for name in PHASES}
        return result

    monkeypatch.setattr(workers, "generate", quick)
    page = GeneratePage()
    qtbot.addWidget(page)
    page.show_notification = lambda title, text: None  # type: ignore[method-assign]
    page.enter(state)
    qtbot.waitUntil(lambda: not page.running, timeout=20000)
    first = page.phase_list.item(0)
    assert first.text().startswith(ICON_DONE) and "Checking your setup" in first.text()
    assert "2 s" in first.text() and first.toolTip() == "preflight"
    assert page.log_view.isHidden()  # collapsed behind "Show details" on success
    from rpggen.core import app_settings

    assert app_settings.load().phase_timings["build"] == 2.0  # remembered for the next estimate
    assert "Finished in" in page.elapsed_label.text()


def test_the_estimate_needs_a_full_history_and_a_failure_opens_the_log(
    qtbot, tmp_path, monkeypatch
) -> None:
    page = GeneratePage()
    qtbot.addWidget(page)
    timings = {name: 10.0 for name in PHASES}
    assert page.estimate_left({}, "build", 0.0) is None  # no history: no guess
    assert page.estimate_left(timings, "", 0.0) is None
    left = page.estimate_left(timings, "build", 4.0)
    assert left == 10.0 * len(PHASES[PHASES.index("build") + 1 :]) + 6.0
    assert page.format_seconds(75) == "1:15"
    state = _state(tmp_path)
    monkeypatch.setattr(workers, "generate", lambda *a, callbacks: _fail_result(tmp_path))
    page.show_notification = lambda title, text: None  # type: ignore[method-assign]
    page.enter(state)
    qtbot.waitUntil(lambda: not page.running, timeout=20000)
    assert page.details_button.isChecked() and not page.log_view.isHidden()


def test_a_notification_only_when_the_window_is_not_active(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    page = GeneratePage()
    qtbot.addWidget(page)
    sent: list[str] = []
    page.show_notification = lambda title, text: sent.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(
        "rpggen.gui.pages.generate_page.QApplication.activeWindow", staticmethod(lambda: None)
    )
    page.notify("rpggen", "done")
    assert sent == ["done"]
    monkeypatch.setattr(
        "rpggen.gui.pages.generate_page.QApplication.activeWindow", staticmethod(lambda: page)
    )
    page.notify("rpggen", "again")
    assert sent == ["done"]
    assert orchestrator is not None


def test_notes_list_the_info_issues_with_the_skipped_checks_first(qtbot, tmp_path: Path) -> None:
    from rpggen.errors import CODES

    state = _state(tmp_path)
    plain = Issue("ADAPT-003", Severity.INFO, "Pack profile x matched.", "")
    skipped = Issue("ENV-010", Severity.INFO, CODES["ENV-010"].message, CODES["ENV-010"].fix)
    state.run_result = _ok_result(tmp_path, [plain, skipped])
    state.run_result.skipped = {"export": "ENV-010"}
    page = _results(qtbot, state)
    assert not page.notes.isHidden()
    assert page.notes.header.text().endswith("Notes (2)")
    assert page.notes_list.item(0).text().startswith("– ENV-010")
    assert "Fix: Install export templates" in page.notes_list.item(0).text()
    assert page.notes_list.item(1).text().startswith("ℹ ADAPT-003")
    assert page.issue_list.count() == 0  # the notes are not warnings


def test_no_notes_no_section_and_a_failure_has_none(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path)
    assert _results(qtbot, state).notes.isHidden()
    state = _state(tmp_path)
    state.run_result = _fail_result(tmp_path)
    assert _results(qtbot, state).notes.isHidden()


def test_the_results_page_shows_the_run_number(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path)
    state.run_result.run_id = "3f9a1c2e"
    assert _results(qtbot, state).run_label.text() == "Run 3f9a1c2e"
    state = _state(tmp_path)
    state.run_result = _fail_result(tmp_path)
    state.run_result.run_id = "0badf00d"
    assert _results(qtbot, state).run_label.text() == "Run 0badf00d"


# ------------------------------------------------------------------------ T12.39


def _with_exes(tmp_path: Path, state) -> Path:
    (tmp_path / "godot.exe").write_text("x")
    console = tmp_path / "godot_console.exe"
    console.write_text("x")
    state.godot_exe = console
    return tmp_path / "godot.exe"


def test_the_gui_exe_is_the_non_console_sibling(tmp_path: Path) -> None:
    from rpggen.core import godot

    gui = tmp_path / "Godot_v4.7.2-stable_win64.exe"
    console = tmp_path / "Godot_v4.7.2-stable_win64_console.exe"
    console.write_text("x")
    assert godot.find_gui_exe(console) == console  # the sibling does not exist yet
    gui.write_text("x")
    assert godot.find_gui_exe(console) == gui
    assert godot.find_gui_exe(gui) == gui
    assert godot.find_console_exe(gui) == console  # the inverse


def test_play_and_open_starter_map_launch_the_gui_exe(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path)
    gui = _with_exes(tmp_path, state)
    page = _results(qtbot, state)
    launched: list[list[str]] = []
    page.launch = launched.append  # type: ignore[method-assign]
    target = str(state.run_result.target)
    page.godot_button.click()
    page.play_button.click()
    page.starter_button.click()  # no starter map file: just the editor
    scene = state.run_result.target / "game" / "maps" / "starter_map.tscn"
    scene.parent.mkdir(parents=True)
    scene.write_text("")
    page.starter_button.click()
    assert launched == [
        [str(gui), "--path", target, "--editor"],
        [str(gui), "--path", target],
        [str(gui), "--editor", "--path", target],
        [str(gui), "--editor", "--path", target, "res://game/maps/starter_map.tscn"],
    ]


def test_warnings_are_grouped_by_code_with_one_fix(qtbot, tmp_path: Path) -> None:
    many = [
        Issue("ASSET-001", Severity.WARNING, f"Tile size {i}.", "Confirm it.") for i in range(37)
    ]
    one = Issue("ASSET-014", Severity.WARNING, "No NPC.", "Add an NPC sprite.")
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path, [*many, one])
    page = _results(qtbot, state)
    assert page.issue_group_counts() == {"ASSET-001": 37, "ASSET-014": 1}
    assert page.issue_list.count() == 2
    text = page.issue_list.item(0).text()
    assert "ASSET-001 × 37" in text and text.count("Confirm it.") == 1
    page.issue_list.setCurrentRow(0)
    assert page.group_detail.count() == 37 and not page.group_detail.isHidden()
    page.issue_list.setCurrentRow(1)
    assert page.group_detail.isHidden()


def test_double_clicking_a_code_opens_the_lookup_at_that_code(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _ok_result(
        tmp_path, [Issue("ASSET-014", Severity.WARNING, "No NPC.", "Add an NPC sprite.")]
    )
    page = _results(qtbot, state)
    opened: list[str] = []
    page.run_viewer = lambda dialog: opened.append(dialog.search.text())  # type: ignore[method-assign]
    page.issue_list.itemDoubleClicked.emit(page.issue_list.item(0))
    assert opened == ["ASSET-014"]


def test_show_these_assets_switches_to_audit_filtered(qtbot, tmp_path: Path) -> None:
    from rpggen.gui.wizard import AUDIT_INDEX, MainWindow, default_pages

    state = _state(tmp_path)
    names = [a for a in state.catalog.assets if a.kind == "image"][:2]
    issues = [
        Issue("ASSET-002", Severity.WARNING, f"Cannot decode {a.path}.", "Replace it.", file=a.path)
        for a in names
    ]
    state.run_result = _ok_result(tmp_path, issues)
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.show()
    window.show_page(6)
    results = window.current_page
    assert isinstance(results, ResultsPage)
    results.issue_list.setCurrentRow(0)
    assert not results.show_assets_button.isHidden()
    results.show_assets_button.click()
    assert window.current_index == AUDIT_INDEX
    grid = window.current_page.grid
    assert grid.proxy.only_ids == {a.id for a in names}
    assert grid.proxy.rowCount() == 2
    grid.chips["chipAll"].click()  # any other chip puts the usual filters back
    assert grid.proxy.only_ids is None


# ------------------------------------------------------------------------ T12.41


class _Nav:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def go_to_project(self) -> None:
        self.calls.append("project")

    def generate_again(self) -> None:
        self.calls.append("generate")

    def show_help(self, anchor: str) -> None:
        self.calls.append(("help", anchor))

    def open_folder(self) -> None:
        self.calls.append("folder")


def _issue(code: str, severity: Severity = Severity.ERROR, **detail) -> Issue:  # type: ignore[no-untyped-def]
    return Issue(code, severity, f"{code} happened.", "Fix it.", detail=detail)


def test_only_registered_codes_get_buttons() -> None:
    from rpggen.gui import fixes

    assert set(fixes.FIXES) == {
        "ENV-001",
        "ENV-002",
        "ENV-009",
        "ENV-010",
        "ASSET-010",
        "REGEN-006",
        "REGEN-001",
    }
    assert [f.label for f in fixes.fixes_for("ENV-001")] == [
        "Download Godot 4.7.2",
        "Choose Godot…",
    ]
    assert fixes.fixes_for("BUILD-002") == () and fixes.fixes_for("") == ()


def test_each_action_leaves_the_expected_state(tmp_path: Path) -> None:
    from rpggen.gui import fixes

    state = _state(tmp_path)
    nav = _Nav()
    download, choose = fixes.fixes_for("ENV-002")
    assert fixes.apply(download, _issue("ENV-002"), state, nav)
    assert state.project_focus == "downloadGodotButton" and nav.calls == ["project"]
    assert fixes.apply(choose, _issue("ENV-001"), state, nav)
    assert state.project_focus == "browseGodotButton"
    (output,) = fixes.fixes_for("ENV-009")
    fixes.apply(output, _issue("ENV-009"), state, nav)
    assert state.project_focus == "browseTargetButton"
    (templates,) = fixes.fixes_for("ENV-010")
    fixes.apply(templates, _issue("ENV-010"), state, nav)
    assert nav.calls[-1] == ("help", fixes.EXPORT_HELP_ANCHOR)
    ok = _ok_result(tmp_path)
    state.run_result = ok
    (placeholder,) = fixes.fixes_for("ASSET-010")
    assert not fixes.apply(placeholder, _issue("ASSET-010"), state, nav)  # no role: no action
    assert state.run_result is not None
    assert fixes.apply(placeholder, _issue("ASSET-010", role="PLAYER"), state, nav)
    assert state.placeholders == {"PLAYER"} and state.run_result is None
    assert nav.calls[-1] == "generate"
    state.run_result = ok
    (upgrade,) = fixes.fixes_for("REGEN-006")
    fixes.apply(upgrade, _issue("REGEN-006"), state, nav)
    assert state.accept_runtime_upgrade is True and state.run_result is None
    (conflicts,) = fixes.fixes_for("REGEN-001")
    fixes.apply(conflicts, _issue("REGEN-001"), state, nav)
    assert nav.calls[-1] == "folder"


def test_the_results_row_shows_buttons_only_for_registered_codes(qtbot, tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.run_result = _fail_result(tmp_path)
    state.run_result.issues = [
        _issue("ASSET-010", role="PLAYER"),
        _issue("BUILD-002"),
    ]
    page = _results(qtbot, state)
    page.issue_list.setCurrentRow(0)
    assert [b.objectName() for b in page.fix_buttons] == ["fix_use_placeholder"]
    assert not page.fix_box.isHidden()
    page.issue_list.setCurrentRow(1)
    assert page.fix_buttons == [] and page.fix_box.isHidden()
    page.issue_list.setCurrentRow(0)
    again: list[bool] = []
    page.generateAgain.connect(lambda: again.append(True))
    page.fix_buttons[0].click()
    assert state.placeholders == {"PLAYER"} and again == [True]


def test_a_note_offers_its_fix_too_and_regen_001_opens_the_folder(qtbot, tmp_path: Path) -> None:
    note = _issue("ENV-010", Severity.INFO)
    conflict = _issue("REGEN-001", Severity.WARNING, file="generated/x.tres")
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path, [note, conflict])
    page = _results(qtbot, state)
    helps: list[str] = []
    page.showHelp.connect(helps.append)
    page.notes_list.setCurrentRow(0)
    assert [b.objectName() for b in page.fix_buttons] == ["fix_export_help"]
    page.fix_buttons[0].click()
    assert helps == ["1. Install"]
    page.issue_list.setCurrentRow(0)
    opened: list[Path] = []
    page.open_path = opened.append  # type: ignore[method-assign]
    page.fix_buttons[0].click()
    assert opened == [state.run_result.target]


def test_the_wizard_runs_the_generation_again_after_a_fix(qtbot, tmp_path: Path) -> None:
    from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

    state = _state(tmp_path)
    state.run_result = _fail_result(tmp_path)
    state.run_result.issues = [_issue("REGEN-006")]
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.show()
    started: list[bool] = []
    window.pages[OPTIONS_INDEX + 1].start = lambda: started.append(True)  # type: ignore[method-assign]
    window.show_page(6)
    results = window.current_page
    results.issue_list.setCurrentRow(0)
    results.fix_buttons[0].click()
    assert window.current_index == OPTIONS_INDEX + 1 and started == [True]
    assert state.accept_runtime_upgrade is True
