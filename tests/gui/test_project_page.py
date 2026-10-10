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
    assert nxt.isEnabled()  # empty fields do not disable Next: pressing it says what is missing
    page = win.pages[0]
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "game"))
    qtbot.waitUntil(lambda: nxt.isEnabled() and not win.issues, timeout=10000)


def test_download_button_shows_for_missing_and_unsupported_godot_only(
    qtbot, tmp_path, monkeypatch
) -> None:
    exe = tmp_path / "g.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    versions = {"v": (4, 8, 0, "stable")}
    monkeypatch.setattr(godot, "detect_version", lambda p: versions["v"])
    page, _state = _page(qtbot)
    page.show()
    page.add_sources([SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "o"))
    _settled(qtbot, page)
    assert page.download_godot_button.isVisible()  # a fake 4.8
    versions["v"] = (4, 7, 1, "stable")
    page.godot_combo.setCurrentText(str(exe) + " ")  # same exe, forces a new check
    page._start_check()
    qtbot.waitUntil(lambda: not page.download_godot_button.isVisible(), timeout=10000)
    page.godot_combo.setCurrentText("")
    assert page.download_godot_button.isVisible()  # nothing selected


def test_download_godot_selects_the_downloaded_copy(qtbot, tmp_path, monkeypatch) -> None:
    from rpggen.core import godot_fetch

    page, _state = _page(qtbot)
    got = tmp_path / "Godot_console.exe"
    got.write_text("x")
    monkeypatch.setattr(godot_fetch, "fetch", lambda *a, **k: got)
    page.confirm_godot_download = lambda dest: False  # type: ignore[method-assign]
    assert page.download_godot() is None
    page.confirm_godot_download = lambda dest: True  # type: ignore[method-assign]
    assert page.download_godot() == got
    assert page.godot_combo.currentText() == str(got)


def _errors(page: ProjectPage) -> list[str]:
    return [
        label.objectName()
        for label in page.findChildren(QLabel)
        if label.property("state") == "error"
    ]


def test_a_fresh_page_shows_hints_not_errors(qtbot, fake_godot) -> None:
    page, _state = _page(qtbot)
    assert _errors(page) == []
    assert page.packs_status.property("state") == "hint"
    assert "Where the Godot project will be created" in _text(page, "targetStatus")


def test_next_on_an_empty_page_reveals_the_three_errors_and_focuses_the_packs(
    qtbot, fake_godot, monkeypatch
) -> None:
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: Path("C:/nowhere"))
    win = MainWindow(pages=default_pages())
    qtbot.addWidget(win)
    win.show()
    page = win.pages[0]
    assert win.problem_label.isHidden()  # no duplicate of the page's own lines
    win.next_button.click()
    assert win.current_index == 0
    assert set(_errors(page)) >= {"packsStatus", "targetStatus", "nameStatus"}
    # the empty pack list is the drop zone: the focus is on its first button (T15.11)
    assert win.focusWidget() is page.add_zip_button
    assert win.problem_label.isHidden()


def test_the_name_and_folder_are_suggested_from_the_first_pack_until_edited(
    qtbot, fake_godot, tmp_path
) -> None:
    page, _state = _page(qtbot)
    page.documents_dir = lambda: tmp_path / "Documents"  # type: ignore[method-assign]
    page.add_sources([SYNTH / "basic16"])
    assert page.name_edit.text() == "Basic16"
    assert page.target() == tmp_path / "Documents" / "rpggen" / "Basic16"
    page.name_edit.setText("My Game")
    page.name_edit.textEdited.emit("My Game")  # the user typed
    page.add_sources([SYNTH / "gutter32"])
    assert page.name_edit.text() == "My Game"  # no longer suggested
    page.target_edit.setText(str(tmp_path / "mine"))
    page.target_edit.textEdited.emit("x")
    page.remove_selected()
    assert page.target() == tmp_path / "mine"


def test_prefill_name_is_title_cased_and_safe() -> None:
    from rpggen.gui.pages.project_page import format_size, prefill_name

    assert prefill_name(Path("C:/packs/fantasy_tiles-v2")) == "Fantasy Tiles V2"
    assert prefill_name(Path("C:/packs/a<b>c")) == "Abc"
    assert prefill_name(Path("C:/packs/___")) == "My Game"
    assert len(prefill_name(Path("x" * 200))) <= 64
    assert format_size(1536) == "1.5 KB" and format_size(10) == "10 B"


def test_pack_rows_show_kind_count_and_size_once_known(qtbot, fake_godot, tmp_path) -> None:
    page, _state = _page(qtbot)
    page.add_sources([SYNTH / "basic16"])
    _settled(qtbot, page)
    text = page.pack_list.item(0).text()
    assert "folder" in text and "files" in text
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    page.add_sources([broken])
    qtbot.waitUntil(lambda: page.pack_list.item(1).text().startswith("⚠"), timeout=10000)


def test_the_empty_pack_list_says_what_to_drop(qtbot) -> None:
    page = ProjectPage()
    qtbot.addWidget(page)
    assert "Drop asset packs here" in page.pack_list.EMPTY_TEXT


def test_the_default_config_hashes_no_pack_on_the_gui_thread(qtbot, tmp_path, monkeypatch) -> None:
    import hashlib
    import threading

    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers

    state = state_mod.WizardState(pack_sources=[SYNTH / "basic16", SYNTH / "zipped.zip"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = ProjectPage()
    qtbot.addWidget(page)
    seen: list[threading.Thread] = []
    real = hashlib.sha256

    def recording(*args, **kwargs):
        seen.append(threading.current_thread())
        return real(*args, **kwargs)

    monkeypatch.setattr(hashlib, "sha256", recording)
    cfg = page._default_config(state)
    assert seen == []  # not one SHA-256 on this thread
    assert [p.source_sha256 for p in cfg.packs] == [
        state.inventories[0].source_sha256,
        state.opened_packs[1].source_sha256,
    ]


def test_pack_cards_show_the_format_the_licence_and_errors(qtbot, fake_godot, tmp_path) -> None:
    from rpggen.gui.pages.project_page import CARD_ROLE

    page, _state = _page(qtbot)
    page.add_sources([SYNTH / "rpgmaker_like", tmp_path / "gone"])
    qtbot.waitUntil(lambda: page.pack_list.item(1).data(CARD_ROLE)["error"] != "", timeout=10000)
    card = page.pack_list.item(0).data(CARD_ROLE)
    texts = [t for t, _kind in card["chips"]]
    assert card["name"] == "rpgmaker_like" and "folder" in card["detail"]
    assert "RPG Maker · 48 px" in texts and "Licence found" in texts
    missing = page.pack_list.item(1).data(CARD_ROLE)
    assert "does not exist" in missing["error"] and not missing["chips"]


def test_the_cross_on_a_card_removes_the_pack(qtbot, fake_godot) -> None:
    page, _state = _page(qtbot)
    page.add_sources([SYNTH / "basic16", SYNTH / "mixed"])
    delegate = page.pack_list.card_delegate
    delegate.removeRequested.emit(0)
    assert [p.name for p in page.sources()] == ["mixed"]
    page.remove_row(7)  # out of range: nothing happens
    assert len(page.sources()) == 1
