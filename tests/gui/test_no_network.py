"""Gate: no network call happens without a click (M11 T11.30, point 3).

The whole wizard runs on the sample pack with every way to open a socket made to raise: starting
the program and the welcome view's Godot check, the sample, generation and the results page."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from rpggen.core import godot
from rpggen.gui import state as state_mod
from rpggen.gui.pages.generate_page import GeneratePage
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.wizard import MainWindow, default_pages

pytestmark = pytest.mark.slow


def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    attempts: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        attempts.append(repr(args)[:80])
        raise AssertionError("a network call was made without a click")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return attempts


def test_the_whole_flow_on_the_sample_pack_opens_no_socket(
    qtbot, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [godot_exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir()
    attempts = _forbid_network(monkeypatch)

    window = MainWindow(state_mod.WizardState(), default_pages(), show_welcome=True)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: "found" in window.welcome.godot_status.text(), timeout=60_000)
    assert window.welcome_visible

    window.welcome.sample_card.click()  # walks to the Generate page and starts (T15.22)
    qtbot.waitUntil(lambda: isinstance(window.current_page, GeneratePage), timeout=120_000)
    generate = window.current_page
    assert isinstance(generate, GeneratePage)
    qtbot.waitUntil(lambda: not generate.running, timeout=300_000)
    result = window.state.run_result
    assert result is not None and result.ok, [(i.code, i.message) for i in result.issues]
    window.next_button.click()
    assert isinstance(window.current_page, ResultsPage)
    assert attempts == []
