from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QLabel, QPushButton

from rpggen.core import godot
from rpggen.errors import RpgGenError
from rpggen.gui import state as state_mod
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.wizard import MainWindow, default_pages

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture
def fake_godot(tmp_path, monkeypatch):
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    return exe


def _page(qtbot, state=None) -> tuple[ProjectPage, state_mod.WizardState]:
    state = state or state_mod.WizardState()
    page = ProjectPage()
    qtbot.addWidget(page)
    page.enter(state)
    return page, state


def _settled(qtbot, page: ProjectPage) -> None:
    qtbot.waitUntil(lambda: page._current_check() is not None, timeout=10000)


def _text(page: ProjectPage, name: str) -> str:
    return page.findChild(QLabel, name).text()


def test_empty_page_is_invalid(qtbot, fake_godot) -> None:
    page, state = _page(qtbot)
    messages = [i.message for i in page.validate(state)]
    assert any("at least one asset pack" in m for m in messages)
    assert any("output folder" in m for m in messages)


def test_valid_inputs_are_all_green(qtbot, fake_godot, tmp_path) -> None:
    page, state = _page(qtbot)
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "out" / "My Game"))
    _settled(qtbot, page)
    assert page.validate(state) == []
    assert page.name_edit.text() == "My Game"  # defaults to the output folder name
    assert "Godot 4.7.2.stable" in _text(page, "godotStatus")
    assert page.godot_status.property("state") == "ok"
    assert page.target_status.property("state") == "ok"


def test_godot_errors_show_in_the_field(qtbot, tmp_path, monkeypatch) -> None:
    exe = tmp_path / "g.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 2, 0, "stable"))
    page, state = _page(qtbot)
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "o"))
    _settled(qtbot, page)
    assert "not supported" in _text(page, "godotStatus")
    assert page.godot_status.property("state") == "error"
    assert any("not supported" in i.message for i in page.validate(state))

    def missing(p):
        raise RpgGenError("ENV-001", path=str(p))

    monkeypatch.setattr(godot, "detect_version", missing)
    page.godot_combo.setCurrentText(str(tmp_path / "nope.exe"))
    _settled(qtbot, page)
    assert "not found" in _text(page, "godotStatus")


def test_output_inside_the_pack_and_non_empty_folder(qtbot, fake_godot, tmp_path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "a.png").write_bytes(b"x")
    page, state = _page(qtbot)
    page.add_sources([pack])
    page.target_edit.setText(str(pack / "out"))
    _settled(qtbot, page)
    assert "inside the asset pack" in _text(page, "targetStatus")
    assert page.target_status.property("state") == "error"
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "file.txt").write_text("x")
    page.target_edit.setText(str(busy))
    qtbot.waitUntil(lambda: "not empty" in _text(page, "targetStatus"), timeout=10000)


def test_unreadable_zip_and_name_length(qtbot, fake_godot, tmp_path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    page, state = _page(qtbot)
    page.add_sources([bad])
    page.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page)
    assert "cannot be opened" in _text(page, "packsStatus")
    page.name_edit.setText("x" * 65)
    assert any("1 to 64" in i.message for i in page.validate(state))
    assert page.name_status.property("state") == "error"
    page.name_edit.setText("")
    assert any("1 to 64" in i.message for i in page.validate(state))


def test_drag_and_drop_adds_a_pack(qtbot, fake_godot) -> None:
    page, state = _page(qtbot)
    mime = QMimeData()
    mime.setUrls(
        [
            QUrl.fromLocalFile(str(SYNTH / "basic16")),
            QUrl.fromLocalFile(str(SYNTH / "zipped.zip")),
        ]
    )
    event = QDropEvent(
        QPoint(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    page.pack_list.dropEvent(event)
    assert [p.name for p in page.sources()] == ["basic16", "zipped.zip"]
    page.add_sources([SYNTH / "basic16"])  # duplicates are ignored
    assert page.pack_list.count() == 2
    page.pack_list.setCurrentRow(0)
    page.remove_selected()
    assert [p.name for p in page.sources()] == ["zipped.zip"]


def test_leaving_the_page_analyzes_the_packs(qtbot, fake_godot, tmp_path) -> None:
    page, state = _page(qtbot)
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page)
    assert page.leave(state) is True
    assert state.catalog is not None and state.catalog.assets
    assert state.config is not None and state.config.packs[0].pack_id == "basic16"
    assert state.target == tmp_path / "out" and state.project_name == "out"


def test_resuming_a_draft_keeps_overrides(qtbot, fake_godot, tmp_path) -> None:
    page, state = _page(qtbot)
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page)
    page.leave(state)
    asset = state.catalog.assets[0]
    asset.overrides = {"role": "WALL"}
    asset.status = "CONFIRMED"
    state_mod.save_draft(state)

    page2, state2 = _page(qtbot)
    page2.ask_resume = lambda: True  # type: ignore[method-assign]
    page2.add_sources([SYNTH / "basic16"])
    page2.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page2)
    page2.leave(state2)
    again = state2.catalog.asset(asset.id)
    assert again.overrides == {"role": "WALL"} and again.status == "CONFIRMED"

    page3, state3 = _page(qtbot)
    page3.ask_resume = lambda: False  # type: ignore[method-assign]
    page3.add_sources([SYNTH / "basic16"])
    page3.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page3)
    page3.leave(state3)
    assert state3.catalog.asset(asset.id).overrides == {}


def test_window_next_enabled_when_page_valid(qtbot, fake_godot, tmp_path) -> None:
    win = MainWindow(pages=default_pages())
    qtbot.addWidget(win)
    win.show()
    nxt = win.findChild(QPushButton, "nextButton")
    assert not nxt.isEnabled()
    page = win.pages[0]
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "game"))
    qtbot.waitUntil(nxt.isEnabled, timeout=10000)
