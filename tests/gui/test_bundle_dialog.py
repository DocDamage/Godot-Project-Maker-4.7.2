"""T16.22: a bundle of packs: the checklist, the packs it adds to the Project page, and the
pack card's words (T16.02, T16.21)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from rpggen import dev, paths
from rpggen.core import archive, godot, pack_sniff
from rpggen.core import config as config_mod
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import state as state_mod
from rpggen.gui import theme, workers
from rpggen.gui.dialogs.bundle_dialog import BundleDialog
from rpggen.gui.models import project_model as model_mod
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.widgets import buttons
from rpggen.gui.widgets.pack_list import CARD_ROLE, GROUP_ROLE
from rpggen.gui.wizard import MIN_WINDOW

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
BUNDLE = SYNTH / "bundle.zip"
THREE = ["Cyberpunk City Tileset", "Medieval Fantasy Town Tileset", "Pirate Cove Tileset"]


def _packs(count: int) -> tuple[pack_sniff.BundlePack, ...]:
    """A bundle of ``count`` pack folders, from a listing of names alone."""
    names = [
        f"Big/Place {n:02d} Tileset Pack/{sheet}.png" for n in range(count) for sheet in (1, 2)
    ]
    sizes = dict.fromkeys(names, 600_000)
    found = pack_sniff.find_bundle(names, sizes)
    assert len(found) == count
    return found


def _dialog(qtbot, packs=None, ticked=None) -> BundleDialog:
    dialog = BundleDialog("bundle.zip", packs or pack_sniff.sniff(BUNDLE).bundle, ticked)
    qtbot.addWidget(dialog)
    return dialog


# ------------------------------------------------------------------ the checklist


def test_twelve_rows_all_ticked_and_none_for_a_large_bundle(qtbot) -> None:
    dialog = _dialog(qtbot)
    assert dialog.table.rowCount() == 12
    assert len(dialog.chosen()) == 12 and dialog.add_button.isEnabled()
    town = next(r for r, p in enumerate(dialog.packs) if p.name == THREE[1])
    assert dialog.table.item(town, 1).text() == "5"  # its pictures, from the listing
    assert dialog.table.item(town, 2).text().endswith("B")
    large = _dialog(qtbot, _packs(25))
    assert large.table.rowCount() == 25 and large.chosen() == []
    assert not large.add_button.isEnabled()  # Add with nothing ticked
    assert _dialog(qtbot, _packs(20)).chosen() != []  # twenty are still all ticked


def test_search_narrows_the_rows_and_keeps_the_ticks_of_hidden_rows(qtbot) -> None:
    dialog = _dialog(qtbot)
    dialog.search.setText("pixel art")
    shown = dialog.shown_rows()
    assert 0 < len(shown) < 12
    assert all("Pixel Art" in dialog.packs[row].name for row in shown)
    dialog.set_shown(False)  # Select none: the rows that are shown
    assert len(dialog.chosen()) == 12 - len(shown)
    assert all("Pixel Art" not in name for name in dialog.chosen())
    dialog.search.setText("no such pack")
    assert dialog.shown_rows() == [] and not dialog.empty_label.isHidden()
    dialog.search.clear()
    assert len(dialog.shown_rows()) == 12 and len(dialog.chosen()) == 12 - len(shown)
    dialog.all_button.click()
    assert len(dialog.chosen()) == 12


def test_the_total_follows_the_ticks_and_add_needs_one(qtbot) -> None:
    dialog = _dialog(qtbot, _packs(25))
    assert dialog.total_label.text() == "0 of 25 packs · 0 images · 0.0 MB"
    for row in (0, 3, 7):
        dialog.set_ticked(row, True)
    # two pictures of 600 000 bytes a pack
    assert dialog.total_label.text() == "3 of 25 packs · 6 images · 3.4 MB"
    assert dialog.add_button.isEnabled()
    dialog.none_button.click()
    assert not dialog.add_button.isEnabled() and dialog.chosen() == []
    dialog.cancel_button.click()
    assert dialog.result() == BundleDialog.DialogCode.Rejected


def test_the_present_choice_is_ticked_when_the_dialog_comes_back(qtbot) -> None:
    dialog = _dialog(qtbot, ticked=set(THREE))
    assert dialog.chosen() == THREE


# ------------------------------------------------------------------ size and keyboard


@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
def test_the_dialog_fits_the_smallest_window_and_has_one_main_button(
    qtbot, theme_name: str
) -> None:
    from tests.gui.test_layout_fit import layout_problems

    original = QApplication.font()
    if dev.ensure_real_font() is None:
        pytest.skip("no real font on this machine")
    try:
        theme.apply_theme(theme_name, remember=False)
        theme.install_focus_ring(QApplication.instance())  # type: ignore[arg-type]
        dialog = _dialog(qtbot, _packs(78))
        dialog.show()
        QApplication.processEvents()
        assert dialog.width() <= MIN_WINDOW[0] and dialog.height() <= MIN_WINDOW[1]
        assert layout_problems(dialog) == []
        hint = dialog.minimumSizeHint()
        assert hint.width() <= MIN_WINDOW[0] and hint.height() <= MIN_WINDOW[1]
        primaries = [
            b
            for b in dialog.findChildren(QAbstractButton)
            if b.property("kind") == buttons.PRIMARY and b.isVisibleTo(dialog)
        ]
        assert primaries == [dialog.add_button]
    finally:
        QApplication.setFont(original)
        theme.apply_theme("dark", remember=False)


def test_the_dialog_by_keyboard_alone(qtbot) -> None:
    from tests.gui.test_theme_a11y import _interactive, _labelled, _tab_stops

    dialog = _dialog(qtbot)
    dialog.show()
    qtbot.waitExposed(dialog)
    QApplication.processEvents()
    assert dialog.focusWidget() is dialog.search  # typing searches at once
    # Tab reaches every control, and each says what it is
    chain: set[QWidget] = set()
    widget: QWidget = dialog.search
    for _ in range(200):
        widget = widget.nextInFocusChain()
        if widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.isEnabled():
            chain.add(widget)
        if widget is dialog.search:
            break
    stops = _tab_stops(dialog)
    assert {dialog.search, dialog.table, dialog.add_button, dialog.cancel_button} <= set(stops)
    assert [s.objectName() for s in stops if s not in chain] == []
    unnamed = [w for w in dialog.findChildren(QWidget) if _interactive(w) and not _labelled(w)]
    assert unnamed == []
    # Enter in the search field goes to the first row shown: it does not add
    dialog.search.setText("pirate")
    qtbot.keyClick(dialog.search, Qt.Key.Key_Return)
    assert dialog.result() != BundleDialog.DialogCode.Accepted and dialog.isVisible()
    row = dialog.table.currentRow()
    assert dialog.packs[row].name == "Pirate Cove Tileset" and dialog.is_ticked(row)
    qtbot.keyClick(dialog.table, Qt.Key.Key_Space)  # Space clears and ticks the row
    assert not dialog.is_ticked(row) and len(dialog.chosen()) == 11
    qtbot.keyClick(dialog.table, Qt.Key.Key_Space)
    assert dialog.is_ticked(row)
    qtbot.keyClick(dialog.table, Qt.Key.Key_Escape)
    assert dialog.result() == BundleDialog.DialogCode.Rejected


# ------------------------------------------------------------------ the Project page


@pytest.fixture
def fake_godot(tmp_path, monkeypatch):
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    return exe


class _Choices:
    """Stands in for the user at the checklist and at the confirmation."""

    def __init__(self, page: ProjectPage) -> None:
        self.tick: list[str] | None = THREE  # None: Cancel
        self.opened_with: list[list[str]] = []
        self.asked: list[list[str]] = []
        self.confirm = True
        page.run_bundle_dialog = self.run  # type: ignore[method-assign]
        page.confirm_remove_packs = self.ask  # type: ignore[method-assign]

    def run(self, dialog: BundleDialog) -> bool:
        self.opened_with.append(dialog.chosen())
        if self.tick is None:
            return False
        for row, pack in enumerate(dialog.packs):
            dialog.set_ticked(row, pack.name in self.tick)
        return True

    def ask(self, names: list[str]) -> bool:
        self.asked.append(names)
        return self.confirm


def _page(qtbot, state=None) -> tuple[ProjectPage, state_mod.WizardState, _Choices]:
    state = state or state_mod.WizardState()
    page = ProjectPage()
    qtbot.addWidget(page)
    choices = _Choices(page)
    page.enter(state)
    return page, state, choices


def _settled(qtbot, page: ProjectPage) -> None:
    qtbot.waitUntil(lambda: page._current_check() is not None, timeout=10000)


def _cards(page: ProjectPage) -> list[dict]:
    page._refresh_cheap()
    return [page.pack_list.item(r).data(CARD_ROLE) for r in range(page.pack_list.count())]


def test_cancel_adds_nothing(qtbot, fake_godot) -> None:
    page, _state, choices = _page(qtbot)
    choices.tick = None
    page.add_sources([BUNDLE])
    assert len(choices.opened_with[0]) == 12  # the checklist opened, all ticked
    assert page.sources() == [] and page.pack_list.count() == 0
    assert page.choose_packs_button.isHidden()


def test_three_ticked_folders_become_three_packs_under_the_archive(
    qtbot, fake_godot, tmp_path, cache_dir
) -> None:
    page, state, choices = _page(qtbot)
    page.add_sources([BUNDLE])
    assert [p.name for p in page.sources()] == THREE  # each named by its folder
    assert page.pack_list.count() == 4  # the row of the archive, then its packs
    assert page.pack_list.item(0).data(GROUP_ROLE) == str(BUNDLE)
    assert not page.choose_packs_button.isHidden()
    page.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page)
    group, *packs = _cards(page)
    assert group["name"] == "bundle.zip" and group["detail"] == "3 of 12 packs"
    assert group["action"] == "Choose packs…" and not group["error"]
    # the licence is said once, on the group
    assert group["chips"] == [("Licence found", "ok")]
    assert [c["name"] for c in packs] == THREE
    assert all(c["chips"] == [] and not c["error"] for c in packs)
    assert packs[1]["detail"].startswith("5 images · ")
    assert page.validate(state) == []
    # only the ticked folders are unpacked
    page.model.store(state, page.inputs())
    result = workers.analyze_packs(state, callbacks=Callbacks())
    workers.apply_analysis(state, result)
    assert [o.pack_id for o in state.opened_packs] == [
        "cyberpunk_city_tileset",
        "medieval_fantasy_town_tileset",
        "pirate_cove_tileset",
    ]
    extracted = sorted(p for p in (cache_dir / "extracted").iterdir() if p.is_dir())
    assert len(extracted) == 3
    files = sorted(f.name for f in state.opened_packs[1].root.iterdir())
    assert files == [
        archive.COMPLETE_MARKER,
        "1.png",
        "2.png",
        "3.png",
        "5.png",
        "6.png",
        "LICENSE.txt",
    ]
    unpacked = [f for root in extracted for f in root.rglob("*.png")]
    assert len(unpacked) == 2 + 5 + 2
    # the bundle's licence is each pack's
    assert all(pack.license_files for pack in state.catalog.packs)
    town = [a for a in state.catalog.assets if a.pack_id == "medieval_fantasy_town_tileset"]
    assert any("town" in a.detected.get("tags", []) for a in town)  # its folder's words


def test_reopening_shows_the_choice_and_clearing_one_asks_first(qtbot, fake_godot) -> None:
    page, _state, choices = _page(qtbot)
    page.add_sources([BUNDLE])
    choices.tick = [*THREE[:2], "Space Station Pixel Art Tileset Pack"]
    choices.confirm = False
    assert not page.choose_packs_at(0)  # *Choose packs…* on the group
    assert choices.opened_with[-1] == THREE  # the present choice was ticked
    assert choices.asked == [[THREE[2]]]  # the pack that would go
    assert [p.name for p in page.sources()] == THREE  # declined: nothing changed
    choices.confirm = True
    page.pack_list.setCurrentRow(2)
    page.choose_packs_button.click()  # the button under the list: the current row's bundle
    assert [p.name for p in page.sources()] == [
        *THREE[:2],
        "Space Station Pixel Art Tileset Pack",
    ]
    assert len(choices.asked) == 2
    # dropping the archive again opens the checklist too, with the choice ticked
    choices.tick = THREE[:1]
    page.add_sources([BUNDLE])
    assert len(choices.opened_with[-1]) == 3
    assert [p.name for p in page.sources()] == THREE[:1]
    # the cross on the group takes its packs, after the confirmation
    page.remove_row(0)
    assert choices.asked[-1] == THREE[:1]
    assert page.sources() == [] and page.pack_list.count() == 0


def test_the_last_pack_of_a_group_takes_the_group_with_it(qtbot, fake_godot) -> None:
    page, _state, choices = _page(qtbot)
    choices.tick = THREE[:2]
    page.add_sources([SYNTH / "basic16", BUNDLE])
    assert page.pack_list.count() == 4 and len(page.sources()) == 3
    page.remove_row(2)  # the cross on one pack of the bundle
    assert [p.name for p in page.sources()] == ["basic16", THREE[1]]
    page.pack_list.setCurrentRow(2)
    page.pack_list.item(2).setSelected(True)
    page.remove_selected()
    assert [p.name for p in page.sources()] == ["basic16"] and page.pack_list.count() == 1
    assert page.choose_packs_button.isHidden()


def test_the_choice_survives_save_and_load_of_the_project(qtbot, fake_godot, tmp_path) -> None:
    page, state, _choices = _page(qtbot)
    page.add_sources([BUNDLE])
    page.model.store(state, page.inputs())
    state.project_name = "Bundled"
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    cfg = model_mod.default_config(state)
    saved = tmp_path / "generator_config.json"
    config_mod.save(cfg, saved)  # the schema takes ``folders``
    loaded = config_mod.load(saved)
    assert [(p.source, p.folders) for p in loaded.packs] == [
        (str(BUNDLE.resolve()), (name,)) for name in THREE
    ]
    assert loaded.to_json()["config_version"] == 1
    assert [p.pack_id for p in loaded.packs] == [o.pack_id for o in state.opened_packs]
    # a regeneration finds the same packs, and the page shows them under their archive
    again = state_mod.WizardState(pack_sources=[p.path for p in loaded.packs], config=loaded)
    other, _state, choices = _page(qtbot, again)
    assert [p.name for p in other.sources()] == THREE and other.pack_list.count() == 4
    choices.tick = None
    other.choose_packs_at(0)
    assert choices.opened_with[-1] == THREE
    result = workers.analyze_packs(again, callbacks=Callbacks())
    assert [o.pack_id for o in result.opened] == [p.pack_id for p in loaded.packs]


def _bundle_without_licence(tmp_path: Path) -> Path:
    path = tmp_path / "Loose Packs.zip"
    with zipfile.ZipFile(BUNDLE) as src, zipfile.ZipFile(path, "w") as out:
        for info in src.infolist():
            if not info.is_dir() and "LICENSE" not in info.filename:
                out.writestr(info.filename.split("/", 1)[1], src.read(info))  # no top folder
    return path


def test_no_licence_in_the_bundle_is_said_once_on_the_group(qtbot, fake_godot, tmp_path) -> None:
    bundle = _bundle_without_licence(tmp_path)
    page, _state, _choices = _page(qtbot)
    page.add_sources([bundle])
    page.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page)
    cards = _cards(page)
    said = [text for card in cards for text, _kind in card["chips"]]
    assert said == ["Licence: not found in the bundle"]
    assert cards[0]["name"] == "Loose Packs.zip" and cards[0]["chips"][0][1] == "warn"


def test_a_folder_that_is_a_bundle_adds_its_folders_as_plain_packs(
    qtbot, fake_godot, tmp_path
) -> None:
    root = tmp_path / "unpacked"
    with zipfile.ZipFile(BUNDLE) as src:
        src.extractall(root)
    page, _state, choices = _page(qtbot)
    page.add_sources([root])
    assert len(choices.opened_with[0]) == 12
    assert page.sources() == [root / "Bundle" / name for name in THREE]
    assert all(source.is_dir() for source in page.sources())
    assert page.pack_list.count() == 3  # folders of their own: no group


# ------------------------------------------------------------------ the pack card's words


def test_the_pack_card_says_what_detection_found(qtbot, fake_godot, tmp_path) -> None:
    page, state, _choices = _page(qtbot)
    shooter = paths.sample_pack_dir("sample_pack_shmup")
    racer = paths.sample_pack_dir("sample_pack_race")
    page.add_sources([SYNTH / "multi_engine", shooter, racer, SYNTH / "basic16"])
    page.target_edit.setText(str(tmp_path / "out"))
    _settled(qtbot, page)
    engines, shmup, racing, plain = _cards(page)
    assert engines["detail"].endswith("art for 5 engines: Godot's is used")
    assert shmup["detail"].endswith("Looks like a shooter pack")
    assert racing["detail"].endswith("Looks like a racing pack")
    assert "Looks like" not in plain["detail"] and "engines" not in plain["detail"]
    # after the analysis the catalog's own words are the card's
    page.model.store(state, page.inputs())
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page.model.load(state)
    assert page.model.catalog_marks[str(shooter)] == ("view:shmup",)
    assert _cards(page)[0]["detail"].endswith("art for 5 engines: Godot's is used")


def test_a_bundle_that_is_in_the_list_whole_says_it_is_one(qtbot, fake_godot, tmp_path) -> None:
    # a project made before the checklist has the archive as one pack
    state = state_mod.WizardState(pack_sources=[BUNDLE], target=tmp_path / "out")
    page, _state, choices = _page(qtbot, state)
    assert choices.opened_with == [] and page.sources() == [BUNDLE]
    _settled(qtbot, page)
    assert ("Bundle of 12 packs", "format") in _cards(page)[0]["chips"]
