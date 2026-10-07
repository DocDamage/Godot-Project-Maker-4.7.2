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
    result.issues.append(Issue("ENV-002", Severity.ERROR, "Godot 4.2 is not supported.", "Download."))
    state.run_result = result
    page = _results(qtbot, state)
    assert page.phase_label.text().startswith("Godot could not build the game.")
    assert not page.project_button.isHidden()
    assert page.another_button.isHidden() and page.options_button.isHidden()
    goto: list[bool] = []
    page.goToProject.connect(lambda: goto.append(True))
    page.project_button.click()
    assert goto == [True]


def test_every_phase_has_a_plain_label_and_the_page_shows_durations(qtbot, tmp_path, monkeypatch) -> None:
    assert set(PHASE_LABELS) == set(PHASES)
    state = _state(tmp_path)

    def quick(cfg, cat, target, godot, placeholders, git_message=None, force=False, *, callbacks):
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


def test_the_estimate_needs_a_full_history_and_a_failure_opens_the_log(qtbot, tmp_path, monkeypatch) -> None:
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


def test_a_notification_only_when_the_window_is_not_active(qtbot, tmp_path: Path, monkeypatch) -> None:
    page = GeneratePage()
    qtbot.addWidget(page)
    sent: list[str] = []
    page.show_notification = lambda title, text: sent.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr("rpggen.gui.pages.generate_page.QApplication.activeWindow", staticmethod(lambda: None))
    page.notify("rpggen", "done")
    assert sent == ["done"]
    monkeypatch.setattr("rpggen.gui.pages.generate_page.QApplication.activeWindow", staticmethod(lambda: page))
    page.notify("rpggen", "again")
    assert sent == ["done"]
    assert orchestrator is not None
