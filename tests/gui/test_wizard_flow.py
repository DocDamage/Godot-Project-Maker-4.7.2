"""The whole wizard on the sample pack: open -> Try -> Generate -> Results (needs Godot)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import godot
from rpggen.gui import state as state_mod
from rpggen.gui.pages.generate_page import GeneratePage
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

pytestmark = pytest.mark.slow


def test_try_generate_and_results_on_the_sample_pack(
    qtbot, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [godot_exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir()
    window = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(window)
    window.show()

    window.pages[0].sample_button.click()  # Try with sample pack
    assert window.current_index == OPTIONS_INDEX
    assert window.next_button.text() == "Generate"

    window.next_button.click()  # Generate
    generate = window.current_page
    assert isinstance(generate, GeneratePage) and generate.running
    qtbot.waitUntil(lambda: not generate.running, timeout=240_000)
    result = window.state.run_result
    assert result is not None
    assert result.ok, [(i.code, i.message) for i in result.issues]
    assert window.next_button.isEnabled()

    window.next_button.click()  # Show results
    results = window.current_page
    assert isinstance(results, ResultsPage)
    assert "generated" in results.header.text()
    assert results.count_labels["errors"].text() == "0"
    assert int(results.count_labels["assets"].text()) >= 14
    assert int(results.count_labels["scenes"].text()) >= 1

    target = window.state.target
    assert (target / "GENERATION_REPORT.md").is_file()
    assert (target / "project.godot").is_file()
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "Result: SUCCESS" in report and "sample_pack" in report
