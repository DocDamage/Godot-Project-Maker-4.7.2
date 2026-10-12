"""T16.21: the colours a pack ships of one picture are one card in the audit, with a
*Variants (n)* row, and each of them a choice on the Mapping page."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QStyleOptionViewItem

from rpggen.core import catalog, config
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.dialogs.asset_picker import AssetPickerDialog
from rpggen.gui.pages.audit_page import AuditPage, make_resolver
from rpggen.gui.pages.mapping_page import MORE_DATA, NONE_DATA, MappingPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import asset_grid as ag

COLOURS = {"": (120, 120, 120), "red": (200, 30, 30), "blue": (30, 60, 200), "green": (20, 160, 60)}


def _car(path: Path, colour: tuple[int, int, int], wheels: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((4, 8, 19, 17), fill=(*colour, 255))
    for n in range(wheels):
        draw.rectangle((5 + 9 * n, 18, 8 + 9 * n, 20), fill=(10, 10, 10, 255))
    img.save(path)


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    root = tmp_path / "wheels"
    for colour, rgb in COLOURS.items():
        _car(root / "Cars" / f"Bug{'_' + colour if colour else ''}.png", rgb)
    _car(root / "Cars" / "Kart_pink.png", (230, 120, 180), wheels=1)
    _car(root / "Cars" / "Kart_cyan.png", (60, 200, 210), wheels=1)
    _car(root / "Props" / "Cone.png", (240, 140, 20), wheels=0)
    (root / "LICENSE.txt").write_text("CC0", encoding="utf-8")
    return root


def _state(pack: Path) -> WizardState:
    state = WizardState(pack_sources=[pack])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return state


def _audit(qtbot, pack: Path) -> tuple[AuditPage, WizardState]:
    state = _state(pack)
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    page.enter(state)
    page.grid.chips["chipAll"].click()
    return page, state


def _id(cat: catalog.Catalog, name: str) -> str:
    return next(a.id for a in cat.assets if a.path.endswith("/" + name))


def _status(page: AuditPage, asset_id: str) -> str:
    return page.session.catalog.asset(asset_id).status


def test_the_catalog_names_the_groups(pack: Path) -> None:
    cat = _state(pack).catalog
    bug, kart = _id(cat, "Bug.png"), _id(cat, "Kart_cyan.png")
    groups = catalog.colour_groups(cat)
    assert set(groups) == {bug, kart} and len(groups[bug]) == 3 and len(groups[kart]) == 1
    assert [catalog.colour_name(a) for a in catalog.colour_group(cat, _id(cat, "Bug_red.png"))] == [
        "", "blue", "green", "red",
    ]  # fmt: skip
    assert catalog.colour_group(cat, bug)[0].id == bug
    assert catalog.colour_group(cat, _id(cat, "Cone.png")) == []


def test_a_group_is_one_card_with_a_badge(qtbot, pack: Path) -> None:
    page, state = _audit(qtbot, pack)
    cat, grid = state.catalog, page.grid
    bug, kart, cone = _id(cat, "Bug.png"), _id(cat, "Kart_cyan.png"), _id(cat, "Cone.png")
    assert grid.model.rowCount() == 7, "every colour is still an asset"
    assert sorted(grid.visible_ids()) == sorted([bug, kart, cone]), "three cards for seven"
    assert len(grid.folded_colours(bug)) == 3 and grid.folded_colours(cone) == []
    index = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(bug), 0))
    assert index.data(ag.ColourCountRole) == 4 and index.data(ag.ColourOfRole) is None
    delegate = grid.view.card_delegate
    assert delegate.variant_badge(index) == f"{ag.VARIANT_GLYPH} 4"
    assert "4 colour variants" in index.data(Qt.ItemDataRole.ToolTipRole)
    assert "4 colour variants" in index.data(Qt.ItemDataRole.AccessibleTextRole)
    plain = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(cone), 0))
    assert delegate.variant_badge(plain) == ""
    # the badge is painted: the same card without the roles of a group looks different
    pictures = []
    for target in (index, plain):
        pixmap = QPixmap(ag.GRID_SIZE)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, ag.GRID_SIZE.width(), ag.GRID_SIZE.height())
        delegate.paint(painter, option, target)
        painter.end()
        pictures.append(pixmap.toImage().copy(11, 6, 30, 14))
    assert pictures[0] != pictures[1]


def test_the_variants_row_shows_and_selects_the_colours(qtbot, pack: Path) -> None:
    page, state = _audit(qtbot, pack)
    cat, grid, detail = state.catalog, page.grid, page.detail
    bug, red = _id(cat, "Bug.png"), _id(cat, "Bug_red.png")
    grid.select_ids([_id(cat, "Cone.png")])
    assert not detail.variants_box.isVisibleTo(detail), "a picture in one colour has no row"
    grid.select_ids([bug])
    assert detail.variants_box.isVisibleTo(detail)
    assert detail.variants_label.text() == "Variants (4)"
    assert detail.variants_names.text() == "plain, blue, green, red"
    assert detail.colour_variants()[0] == bug and len(detail.colour_variants()) == 4
    assert not detail.variants_show_button.isChecked()
    detail.variants_show_button.click()  # Show all: a card per colour
    assert grid.colours_shown(bug) and len(grid.visible_ids()) == 6
    assert grid.selected_ids() == [bug] and detail.variants_show_button.isChecked()
    grid.select_ids([red])  # a colour's own card has the row too, and the glyph without a number
    assert (
        detail.variants_label.text() == "Variants (4)" and detail.variants_show_button.isChecked()
    )
    index = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(red), 0))
    assert grid.view.card_delegate.variant_badge(index) == ag.VARIANT_GLYPH
    assert "a colour variant of " + bug in index.data(Qt.ItemDataRole.ToolTipRole)
    detail.variants_show_button.click()  # one card again: the selection goes to the card
    assert not grid.colours_shown(bug) and grid.selected_ids() == [bug]
    assert len(grid.visible_ids()) == 3
    detail.variants_select_button.click()  # Select all: the bulk panel has the four
    assert sorted(grid.selected_ids()) == sorted(
        detail_ids := [bug, *grid.model.colour_members(bug)]
    )
    assert page.side.currentWidget() is page.bulk_scroll and len(detail_ids) == 4


def test_confirm_exclude_and_a_role_go_to_every_colour_of_a_card(qtbot, pack: Path) -> None:
    page, state = _audit(qtbot, pack)
    cat, grid = state.catalog, page.grid
    bug, kart = _id(cat, "Bug.png"), _id(cat, "Kart_cyan.png")
    group = [bug, *grid.model.colour_members(bug)]
    grid.select_ids([bug])
    page._confirm_selection()
    assert [_status(page, i) for i in group] == ["CONFIRMED"] * 4
    assert len(grid.folded_colours(bug)) == 3, "still one card"
    page.session.undo_stack.undo()  # one step for the group
    assert "CONFIRMED" not in [_status(page, i) for i in group]
    grid.select_ids([kart])
    page._exclude_selection()
    pair = [kart, *grid.model.colour_members(kart)]
    assert [_status(page, i) for i in pair] == ["UNUSED", "UNUSED"]
    grid.select_ids([bug])
    page.detail._edit("role", "ENEMY")  # the panel's role combo
    roles = [catalog.effective(page.session.catalog.asset(i))["role"] for i in group]
    assert roles == ["ENEMY"] * 4 and len(grid.folded_colours(bug)) == 3
    assert page.session.undo_stack.count() == 2, "the exclusion and the role: a step each"
    page.session.undo_stack.undo()
    grid.select_ids([bug])
    page.detail._on_confirm()  # the panel's Confirm
    assert [_status(page, i) for i in group] == ["CONFIRMED"] * 4


def test_a_colour_that_differs_from_its_card_is_a_card_of_its_own(qtbot, pack: Path) -> None:
    page, state = _audit(qtbot, pack)
    cat, grid = state.catalog, page.grid
    bug, red, blue = (_id(cat, n) for n in ("Bug.png", "Bug_red.png", "Bug_blue.png"))
    page.session.set_override(red, "role", "ITEM")  # one colour gets a role of its own
    assert red in grid.visible_ids() and blue not in grid.visible_ids()
    assert sorted(grid.folded_colours(bug)) == sorted(
        i for i in grid.model.colour_members(bug) if i != red
    )
    page.session.undo_stack.undo()
    assert red not in grid.visible_ids()
    # a filter that leaves the card out shows the colours that pass it
    page.session.confirm([bug])
    assert len(grid.folded_colours(bug)) == 0 and red in grid.visible_ids()
    grid.chips["chipConfirmed"].click()
    assert grid.visible_ids() == [bug]
    page.session.undo_stack.undo()
    grid.chips["chipAll"].click()
    grid.search.setText("red")
    assert grid.visible_ids() == [red], "the card does not match the text: the colour does"
    grid.search.setText("")
    # selecting a colour its card stands for gives it a card (Show in audit, the Changes tab)
    page.show_asset(blue)
    assert grid.selected_ids() == [blue] and grid.colours_shown(bug)
    # a list of assets shows every one of them
    grid.show_colours(bug, False)
    grid.show_ids({red, blue})
    assert sorted(grid.visible_ids()) == sorted([red, blue])


def test_grouped_by_folder_a_colour_in_another_folder_keeps_its_card(qtbot, tmp_path: Path) -> None:
    root = tmp_path / "ranch"
    for colour, rgb in (("brown", (120, 80, 40)), ("black", (20, 20, 20))):
        _car(root / "cows" / colour / "cow.png", rgb)
    for colour, rgb in COLOURS.items():
        _car(root / "Cars" / f"Bug{'_' + colour if colour else ''}.png", rgb)
    (root / "LICENSE.txt").write_text("CC0", encoding="utf-8")
    page, state = _audit(qtbot, root)
    grid = page.grid
    assert len(grid.visible_ids()) == 2, "a card for the cows, one for the cars"
    grid.set_grouped(True)
    assert len(grid.visible_ids()) == 3, "each folder of cows shows its cow"
    counts = [grid.proxy.folder_counts(k)[2] for k in grid.header_keys()]
    assert sorted(counts) == [1, 1, 4], "a header counts assets, folded or not"


def test_the_mapping_page_offers_the_colours_of_a_choice(qtbot, pack: Path) -> None:
    state = _state(pack)
    cat = state.catalog
    bug, red = _id(cat, "Bug.png"), _id(cat, "Bug_red.png")
    for asset in cat.assets:  # the cars are the pack's enemies; the cone is a decoration
        if "/Cars/" in asset.path:
            asset.detected["role"] = "ENEMY"
    ref = config.PackRef(state.opened_packs[0].pack_id, str(pack), "0" * 64, "folder")
    state.config = config.default_for("T", [ref], archetype="turn_based")
    page = MappingPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    page.assign("ENEMY", bug)
    row = page.rows["ENEMY"]
    assert "4 colours" in row.asset_combo.currentText()
    assert [a.id for a in page.colour_choices("ENEMY")] == catalog.colour_groups(cat)[bug]
    page.fill_candidates("ENEMY")
    offered = [i for i in page.candidate_ids("ENEMY") if i not in (NONE_DATA, MORE_DATA)]
    assert offered[:4] == [bug, *catalog.colour_groups(cat)[bug]], "the other colours first"
    assert len(offered) == len(set(offered)), "nothing twice"
    combo = row.asset_combo
    at = combo.findData(red)
    assert "(colour: red)" in combo.itemText(at)
    combo.setCurrentIndex(at)
    page.on_combo("ENEMY")
    assert page.selection_for("ENEMY") == red
    assert [a.id for a in page.colour_choices("ENEMY")][0] == bug, "back to the plain one too"
    assert page.undo() and page.selection_for("ENEMY") == bug
    # the gallery shows every colour as a card (no folding), marked as a variant
    dialog = AssetPickerDialog(state.catalog, "ENEMY", make_resolver(state), page)
    qtbot.addWidget(dialog)
    shown = set(dialog.grid.visible_ids())
    assert {bug, *catalog.colour_groups(cat)[bug]} <= shown
    index = dialog.grid.proxy.mapFromSource(
        dialog.grid.model.index(dialog.grid.model.row_of(red), 0)
    )
    assert dialog.grid.view.card_delegate.variant_badge(index) == ag.VARIANT_GLYPH
