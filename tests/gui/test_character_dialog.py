"""Audit → Compose LPC character… (M16): the dialog, the menu entries and the undo."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, config, inventory, lpc_compose
from rpggen.gui.dialogs.character_dialog import CharacterDialog
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "test_packs" / "synthetic" / "lpc_parts"
BODY = "lpc_parts.spritesheets.body.bodies.male.walk"
HAIR = "lpc_parts.spritesheets.hair.afro.adult.walk"
RED = "lpc_parts.spritesheets.torso.clothes.shirt.male.walk.red"
BLUE = "lpc_parts.spritesheets.torso.clothes.shirt.male.walk.blue"
AUTO = "lpc_parts.lpc_character.male"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _state() -> WizardState:
    opened = archive.open_pack(PACK, set(), pack_id="lpc_parts")
    inv = inventory.build_inventory(opened)
    state = WizardState()
    state.opened_packs = [opened]
    state.inventories = [inv]
    state.catalog = catalog.assemble([(opened, inv)], None, [])[0]
    state.config = config.default_for("L", [config.pack_ref_from_source(PACK, "lpc_parts")])
    return state


def _page(qtbot) -> tuple[AuditPage, WizardState]:
    state = _state()
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.enter(state)
    page.show()
    page.grid.chips["chipAll"].click()
    return page, state


def _dialog(qtbot, definition=None) -> CharacterDialog:  # noqa: ANN001
    state = _state()
    roots = {p.pack_id: Path(p.root) for p in state.opened_packs}
    dialog = CharacterDialog(state.catalog, state.catalog.asset(BODY), roots, definition)
    qtbot.addWidget(dialog)
    return dialog


def test_the_dialog_offers_the_layers_that_fit_by_part_and_shows_the_character(qtbot) -> None:
    dialog = _dialog(qtbot)
    assert sorted(dialog.combos) == ["hair", "torso"]
    hair, torso = dialog.combos["hair"], dialog.combos["torso"]
    assert [hair.itemData(i) for i in range(hair.count())] == ["", HAIR]
    assert [torso.itemData(i) for i in range(torso.count())] == ["", BLUE, RED]
    assert hair.currentData() == HAIR, "one candidate: it is on"
    assert torso.currentData() == "", "two candidates: somebody chooses"
    assert hair.itemText(1) == "hair/afro/adult" and torso.itemText(2).endswith("shirt/male/red")
    assert dialog.name_edit.text() == "Male" and dialog.layers() == [HAIR]
    before = dialog.preview.pixmap().toImage()
    assert not dialog.preview.pixmap().isNull() and "1 layer" in dialog.note.text()
    torso.setCurrentIndex(torso.findData(RED))
    assert dialog.layers() == [HAIR, RED] and "2 layer" in dialog.note.text()
    assert dialog.preview.pixmap().toImage() != before, "the shirt is drawn in the preview"
    made = dialog.definition()
    assert made == {
        "id": "lpc_parts.lpc_character.male_2",  # the automatic one has the plain id
        "name": "Male",
        "body": BODY,
        "layers": [HAIR, RED],
    }
    dialog.name_edit.setText("  ")
    assert not dialog.buttons.button(dialog.buttons.StandardButton.Ok).isEnabled()
    for widget in (dialog.name_edit, hair, torso):
        assert widget.toolTip()


def test_an_existing_character_opens_with_its_layers_and_keeps_its_id(qtbot) -> None:
    mine = {"id": "lpc_parts.lpc_character.guard", "name": "Guard", "body": BODY, "layers": [BLUE]}
    dialog = _dialog(qtbot, mine)
    assert dialog.name_edit.text() == "Guard"
    assert dialog.combos["torso"].currentData() == BLUE
    assert dialog.combos["hair"].currentData() == "", "what was not chosen stays off"
    assert dialog.definition() == mine


def test_a_character_is_composed_from_the_menu_and_undone(qtbot) -> None:
    page, _state_ = _page(qtbot)
    session = page.session
    assert session.catalog.asset(AUTO) is not None, "the pack's own character"
    page.grid.select_ids([AUTO])
    assert page.selected_character() == AUTO and page.character_body().id == BODY

    def choose(dialog: CharacterDialog) -> bool:
        assert dialog.combos["hair"].currentData() == HAIR  # opened with what it has
        dialog.combos["torso"].setCurrentIndex(dialog.combos["torso"].findData(RED))
        dialog.name_edit.setText("Knight")
        return True

    page.run_character_dialog = choose  # type: ignore[method-assign]
    old = session.catalog.asset(AUTO).sha256
    assert page.compose_character() == AUTO, "the selected character is changed, not doubled"
    changed = session.catalog.asset(AUTO)
    assert changed.sha256 != old and lpc_compose.is_character(changed)
    (definition,) = session.catalog.characters
    assert definition == {"id": AUTO, "name": "Knight", "body": BODY, "layers": [HAIR, RED]}
    assert page.grid.selected_ids() == [AUTO]
    assert page.grid.model.resolver(changed) == lpc_compose.cached_file(changed.sha256)
    session.undo_stack.undo()
    assert session.catalog.asset(AUTO).sha256 == old
    assert session.catalog.characters[0]["layers"] == [HAIR]
    session.undo_stack.redo()
    assert session.catalog.asset(AUTO).sha256 == changed.sha256


def test_a_second_character_from_the_body_and_a_removal(qtbot) -> None:
    page, _state_ = _page(qtbot)
    session = page.session
    page.grid.select_ids([BODY])
    assert page.selected_character() is None and page.character_body().id == BODY

    def choose(dialog: CharacterDialog) -> bool:
        dialog.combos["hair"].setCurrentIndex(0)
        dialog.combos["torso"].setCurrentIndex(dialog.combos["torso"].findData(BLUE))
        dialog.name_edit.setText("Villager")
        return True

    page.run_character_dialog = choose  # type: ignore[method-assign]
    made = page.compose_character()
    assert made == "lpc_parts.lpc_character.villager"
    characters = [a.id for a in session.catalog.assets if lpc_compose.is_character(a)]
    assert characters == [AUTO, made]
    page.grid.select_ids([made])
    assert page.remove_character()
    assert [a.id for a in session.catalog.assets if lpc_compose.is_character(a)] == [AUTO]
    assert lpc_compose.definition_of(session.catalog, made) is None
    assert session.catalog.asset(BODY).status == "UNUSED", "still in the other character"
    page.grid.select_ids([AUTO])
    assert page.remove_character()
    assert not [a for a in session.catalog.assets if lpc_compose.is_character(a)]
    assert session.catalog.asset(BODY).status != "UNUSED", "its body is free again"
    page.run_character_dialog = lambda dialog: False  # type: ignore[method-assign]
    page.grid.select_ids([BODY])
    assert page.compose_character() is None  # cancelled: nothing is added
    page.grid.select_ids([HAIR])
    assert page.character_body() is None and not page.remove_character()
