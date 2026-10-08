from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from rpggen.core import archive, catalog, config, inventory, orchestrator, report
from rpggen.errors import Issue, Severity
from rpggen.gui import workers
from rpggen.gui.pages.generate_page import ICON_DONE, ICON_FAILED, PHASES, GeneratePage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.log_view import LogView

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _catalog() -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / "basic16", set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


def _state(tmp_path: Path) -> WizardState:
    ref = config.PackRef("basic16", str(SYNTH / "basic16"), "0" * 64, "folder")
    return WizardState(
        target=tmp_path / "out",
        godot_exe=tmp_path / "godot.exe",
        config=config.default_for("T", [ref]),
        catalog=_catalog(),
    )


def _ok_result(tmp_path: Path, issues: list[Issue] | None = None) -> orchestrator.RunResult:
    target = tmp_path / "out"
    (target / "generated").mkdir(parents=True)
    (target / "generated" / "a.tscn").write_text("", encoding="utf-8")
    (target / report.REPORT_MD).write_text("# Generation Report\n\nhello", encoding="utf-8")
    return orchestrator.RunResult(
        True, target, issues or [], None, None, catalog=_catalog(), cfg=None
    )


def _fail_result(tmp_path: Path) -> orchestrator.RunResult:
    failed = tmp_path / "out" / ".rpggen_failed" / "x"
    (failed / "rpggen" / "logs").mkdir(parents=True)
    (failed / "rpggen" / "logs" / "build.log").write_text("boom line", encoding="utf-8")
    issue = Issue("BUILD-002", Severity.ERROR, "Recipe x failed.", "See the log.")
    return orchestrator.RunResult(
        False, tmp_path / "out", [issue], None, failed, failed_phase="build"
    )


# ------------------------------------------------------------------------ log view


def test_log_view_caps_lines_and_follows_the_end(qtbot) -> None:
    view = LogView(max_lines=50)
    qtbot.addWidget(view)
    view.resize(300, 100)
    view.show()
    assert view.isReadOnly() and view.maximumBlockCount() == 50
    for i in range(200):
        view.append_line(f"line {i}")
    assert view.lines() <= 51
    assert view.at_bottom()
    assert view.toPlainText().splitlines()[-1] == "line 199"


def test_log_view_does_not_scroll_when_the_user_scrolled_up(qtbot) -> None:
    view = LogView()
    qtbot.addWidget(view)
    view.resize(300, 100)
    view.show()
    for i in range(100):
        view.append_line(f"line {i}")
    bar = view.verticalScrollBar()
    bar.setValue(0)
    view.append_line("new")
    assert bar.value() == 0


# ------------------------------------------------------------------------ report


def test_report_markdown_is_deterministic_and_has_the_sections() -> None:
    cat = _catalog()
    issues = [
        Issue("ASSET-014", Severity.WARNING, "Missing NPC.", "Add one."),
        Issue("ADAPT-003", Severity.INFO, "Profile matched.", ""),
    ]
    one = report.build_markdown(None, cat, issues, True, godot_version="4.7.2")
    two = report.build_markdown(None, cat, issues, True, godot_version="4.7.2")
    assert one == two
    for heading in (
        "# Generation Report",
        "## What to review",
        "## Packs and licenses",
        "## Summary",
    ):
        assert heading in one
    assert "Result: SUCCESS" in one and "ASSET-014" in one and "Add one." in one
    failed = report.build_markdown(None, cat, issues, False, failed_phase="build")
    assert "Result: FAILED" in failed and "Failed in phase: build" in failed


def test_counts(tmp_path: Path) -> None:
    result = _ok_result(tmp_path, [Issue("W", Severity.WARNING, "w", "")])
    numbers = report.counts(result.catalog, result.issues, result.target)
    assert numbers["scenes"] == 1 and numbers["warnings"] == 1 and numbers["errors"] == 0
    assert numbers["assets"] == len([a for a in result.catalog.assets if a.status != "UNUSED"])


# ------------------------------------------------------------------------ the orchestrator


def test_run_in_memory_stops_in_preflight_without_godot(tmp_path: Path) -> None:
    state = _state(tmp_path)
    result = orchestrator.run_in_memory(
        state.config, state.catalog, state.target, tmp_path / "missing" / "godot.exe"
    )
    assert not result.ok
    assert result.failed_phase == "preflight"
    assert [i.code for i in result.issues] == ["ENV-001"]


def test_run_in_memory_builds_on_the_given_catalog(tmp_path: Path, monkeypatch) -> None:
    seen: dict = {}

    def capture(state) -> None:
        seen["catalog_in"] = state.catalog_in
        seen["cfg"] = state.cfg

    monkeypatch.setattr(orchestrator, "PHASES_M1", ["catalog"])
    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "catalog", capture)
    cat = _catalog()
    state = _state(tmp_path)
    result = orchestrator.run_in_memory(state.config, cat, state.target, state.godot_exe)
    assert result.ok and seen["catalog_in"] is cat and seen["cfg"] is state.config


# ------------------------------------------------------------------------ the generate page


def _wait(qtbot, page: GeneratePage) -> None:
    qtbot.waitUntil(lambda: not page.running, timeout=5000)
    QCoreApplication.processEvents()


def test_generate_runs_the_worker_and_shows_progress(qtbot, tmp_path, monkeypatch) -> None:
    state = _state(tmp_path)
    seen: dict = {}

    def fake(cfg, cat, target, godot, placeholders, git_message=None, force=False, *, callbacks):
        seen["args"] = (cfg, cat, target, godot, placeholders)
        seen["extra"] = (git_message, force)
        for i, name in enumerate(PHASES, start=1):
            callbacks.on_phase(name, i, len(PHASES))
            callbacks.on_log(f"phase {name}")
        return _ok_result(tmp_path)

    monkeypatch.setattr(workers, "generate", fake)
    state.placeholders = {"PLAYER"}
    page = GeneratePage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    assert page.running and not page.allow_next and not page.allow_back
    assert page.leave(state) is False  # cannot leave while running
    _wait(qtbot, page)
    assert seen["args"][1] is state.catalog and seen["args"][4] == ["PLAYER"]
    assert seen["args"][0] is not state.config  # a snapshot, not the live config
    assert state.run_result is not None and state.run_result.ok
    assert page.allow_next and not page.allow_back
    assert page.progress.value() == len(PHASES)
    assert page.phase_list.item(0).text().startswith(ICON_DONE)
    assert "phase smoke" in page.log_view.toPlainText()
    page.enter(state)  # coming back after success does not run again
    assert not page.running


def test_generate_failure_marks_the_failing_phase(qtbot, tmp_path, monkeypatch) -> None:
    state = _state(tmp_path)
    monkeypatch.setattr(workers, "generate", lambda *a, callbacks: _fail_result(tmp_path))
    page = GeneratePage()
    qtbot.addWidget(page)
    page.enter(state)
    _wait(qtbot, page)
    assert not state.run_result.ok
    index = PHASES.index("build")
    assert page.phase_list.item(index).text().startswith(ICON_FAILED)
    assert page.allow_back and page.allow_next


def test_a_crashing_worker_becomes_a_gui_error(qtbot, tmp_path, monkeypatch) -> None:
    state = _state(tmp_path)

    def boom(*a, callbacks):
        raise ValueError("kaput")

    monkeypatch.setattr(workers, "generate", boom)
    page = GeneratePage()
    qtbot.addWidget(page)
    page.enter(state)
    _wait(qtbot, page)
    assert [i.code for i in state.run_result.issues] == ["GUI-001"]
    assert "kaput" in state.run_result.issues[0].message


def test_cancel_stops_without_a_result(qtbot, tmp_path, monkeypatch) -> None:
    state = _state(tmp_path)

    def slow(cfg, cat, target, godot, placeholders, git_message=None, force=False, *, callbacks):
        callbacks.on_phase(PHASES[0], 1, len(PHASES))
        deadline = time.time() + 5
        while not callbacks.is_cancelled() and time.time() < deadline:
            time.sleep(0.01)
        return orchestrator.RunResult(False, target, [], None, None)

    monkeypatch.setattr(workers, "generate", slow)
    page = GeneratePage()
    qtbot.addWidget(page)
    page.enter(state)
    qtbot.waitUntil(lambda: page.progress.value() == 0 and "Phase 1" in page.status_label.text())
    page.cancel_button.click()
    _wait(qtbot, page)
    assert state.run_result is None
    assert "cancelled" in page.status_label.text()
    assert page.allow_back and not page.allow_next


def test_missing_godot_is_reported_not_started(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    state.godot_exe = None
    page = GeneratePage()
    qtbot.addWidget(page)
    page.enter(state)
    assert not page.running
    assert state.run_result is not None and state.run_result.issues[0].code == "GUI-001"


# ------------------------------------------------------------------------ the results page


def _results(qtbot, state: WizardState) -> ResultsPage:
    page = ResultsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page


def test_success_shows_counts_warnings_and_buttons(qtbot, tmp_path) -> None:
    warning = Issue("ASSET-014", Severity.WARNING, "No NPC.", "Add an NPC sprite.")
    state = _state(tmp_path)
    state.run_result = _ok_result(tmp_path, [warning])
    page = _results(qtbot, state)
    assert "generated" in page.header.text()
    assert page.count_labels["warnings"].text() == "1"
    assert page.count_labels["scenes"].text() == "1"
    assert page.issue_list.count() == 1
    page.issue_list.setCurrentRow(0)
    assert page.fix_label.text() == "Add an NPC sprite."
    assert not page.restore_button.isEnabled()
    assert page.failed_button.isHidden() and not page.godot_button.isHidden()

    launched: list[list[str]] = []
    opened: list[Path] = []
    page.launch = launched.append  # type: ignore[method-assign]
    page.open_path = opened.append  # type: ignore[method-assign]
    page.godot_button.click()
    assert launched == [[str(state.godot_exe), "--path", str(state.run_result.target), "--editor"]]
    page.folder_button.click()
    assert opened == [state.run_result.target]
    viewers = []
    page.run_viewer = viewers.append  # type: ignore[method-assign]
    page.report_button.click()
    assert "hello" in viewers[0].browser.toPlainText()


def test_failure_has_no_deliver_anyway_and_shows_the_phase(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    state.run_result = _fail_result(tmp_path)
    page = _results(qtbot, state)
    assert "failed" in page.header.text().lower()
    assert "build" in page.phase_label.text()
    assert page.issue_list.count() == 1
    page.issue_list.setCurrentRow(0)
    assert page.fix_label.text() == "See the log."
    texts = {b.text().lower() for b in page.findChildren(type(page.godot_button))}
    assert not any("anyway" in t for t in texts)
    assert page.godot_button.isHidden() and page.report_button.isHidden()
    assert not page.failed_button.isHidden() and not page.logs_button.isHidden()
    viewers = []
    page.run_viewer = viewers.append  # type: ignore[method-assign]
    page.logs_button.click()
    assert "boom line" in viewers[0].browser.toPlainText()
    opened: list[Path] = []
    page.open_path = opened.append  # type: ignore[method-assign]
    page.failed_button.click()
    assert opened == [state.run_result.failed_staging]


def test_results_without_a_run_say_so(qtbot, tmp_path) -> None:
    page = _results(qtbot, _state(tmp_path))
    assert "Nothing" in page.header.text()


# ------------------------------------------------------------------------ live output (T12.19)


def test_log_view_keeps_5000_lines_takes_batches_and_says_when_it_dropped(qtbot) -> None:
    from rpggen.gui.widgets.log_view import MAX_LINES

    assert MAX_LINES == 5000
    view = LogView(max_lines=100)
    qtbot.addWidget(view)
    view.resize(300, 100)
    view.show()
    dropped: list[bool] = []
    view.truncated.connect(lambda: dropped.append(True))
    view.append_lines([f"a{i}" for i in range(100)])  # exactly full: nothing dropped yet
    assert not view.dropped and dropped == []
    view.append_lines(["b0", "b1"])
    assert view.dropped and dropped == [True]
    view.append_lines(["b2"])
    assert dropped == [True]  # said once
    assert view.lines() <= 101 and view.toPlainText().splitlines()[-1] == "b2"
    assert view.at_bottom()
    view.clear()
    assert not view.dropped and view.lines() <= 1


def test_a_batch_follows_the_end_unless_the_user_scrolled_up(qtbot) -> None:
    view = LogView()
    qtbot.addWidget(view)
    view.resize(300, 100)
    view.show()
    view.append_lines([f"line {i}" for i in range(200)])
    assert view.at_bottom()
    view.verticalScrollBar().setValue(0)
    view.append_lines(["new one", "new two"])
    assert view.verticalScrollBar().value() == 0  # the user is reading: no jump
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    view.append_lines(["follow"])
    assert view.at_bottom()


def test_the_generate_page_shows_what_the_running_phase_is_doing(
    qtbot, tmp_path, monkeypatch
) -> None:
    state = _state(tmp_path)

    def fake(cfg, cat, target, godot, placeholders, git_message=None, force=False, *, callbacks):
        callbacks.on_phase("build", 6, len(PHASES))
        callbacks.on_step("build", 7, 31, "tileset")
        callbacks.on_log("[godot] one\n[godot] two")
        callbacks.on_phase("validate", 7, len(PHASES))
        callbacks.on_step("validate", 3, 12, "dependencies")
        return _ok_result(tmp_path)

    monkeypatch.setattr(workers, "generate", fake)
    page = GeneratePage()
    qtbot.addWidget(page)
    page.show_notification = lambda title, text: None  # type: ignore[method-assign]
    shown: list[str] = []
    real = page._on_step
    page._on_step = lambda *a: (real(*a), shown.append(page.step_label.toolTip()))  # type: ignore[method-assign]
    page.enter(state)
    qtbot.waitUntil(lambda: not page.running, timeout=20000)
    assert "Building tileset (7 of 31)" in shown and "Checking dependencies (3 of 12)" in shown
    assert page.step_label.text() == ""  # nothing is "running" any more
    assert "[godot] two" in page.log_view.toPlainText()


def test_the_sub_line_of_the_import_is_the_last_line_godot_printed(qtbot) -> None:
    page = GeneratePage()
    qtbot.addWidget(page)
    assert page.step_text("import", 0, 0, "Importing a.png") == "Importing a.png"
    assert page.step_text("build", 7, 31, "tileset") == "Building tileset (7 of 31)"
    assert page.step_text("validate", 1, 12, "scripts") == "Checking scripts (1 of 12)"
    page.current_phase = "import"
    page.resize(300, 200)
    page._on_step("import", 0, 0, "x" * 500)
    assert len(page.step_label.text()) < 500 and page.step_label.toolTip() == "x" * 500  # elided
    page._on_step("build", 1, 2, "late line of the phase before")
    assert page.step_label.toolTip() == "x" * 500  # ignored: not the running phase
