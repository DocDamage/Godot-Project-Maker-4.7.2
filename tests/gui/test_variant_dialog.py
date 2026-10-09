"""Audit → Make variant… (T13.18): the dialog, the grid's glyph and the undo."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyleOptionViewItem

from rpggen.core import archive, catalog, config, inventory, variants
from rpggen.gui.dialogs.variant_dialog import VariantDialog
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import asset_grid as ag

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _state() -> WizardState:
    opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
    inv = inventory.build_inventory(opened)
    cat = catalog.assemble([(opened, inv)], None, [])[0]
    state = WizardState()
    state.opened_packs = [opened]
    state.inventories = [inv]
    state.catalog = cat
    state.config = config.default_for("V", [config.pack_ref_from_source(SAMPLE, "sample_pack")])
    return state


def _page(qtbot) -> tuple[AuditPage, WizardState]:
    state = _state()
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.enter(state)
    page.show()
    return page, state


def _slime(cat: catalog.Catalog) -> catalog.Asset:
    return next(a for a in cat.assets if a.path.endswith("slime_idle.png"))


def _dialog(qtbot, asset_name: str = "slime_idle.png") -> VariantDialog:
    state = _state()
    asset = next(a for a in state.catalog.assets if a.path.endswith(asset_name))
    file = Path(state.opened_packs[0].root) / asset.path.split("/", 3)[3]
    dialog = VariantDialog(state.catalog, asset, file)
    qtbot.addWidget(dialog)
    return dialog


# ------------------------------------------------------------------------ the dialog


def test_the_dialog_shows_the_source_and_the_result_side_by_side(qtbot) -> None:
    dialog = _dialog(qtbot)
    assert dialog.source_view.pixmap() is not None and dialog.result_view.pixmap() is not None
    assert dialog.name_edit.text() == "Slime idle variant"
    assert dialog.op() == "hue"
    same = dialog.result_image.tobytes()
    assert same == dialog.image.tobytes(), "nothing turned yet: the result is the source"
    dialog.hue_dial.setValue(120)
    assert dialog.hue_label.text() == "120°"
    assert dialog.result_image.tobytes() != same, "the preview follows the wheel"
    dialog.saturation_slider.setValue(50)
    dialog.value_slider.setValue(150)
    assert dialog.params() == {"shift": 120, "saturation": 0.5, "value": 1.5}
    # an enemy gets the stats row, and the name is needed
    assert not dialog.stats_box.isHidden()
    dialog.stat_spins["hp"].setValue(2.0)
    dialog.stat_spins["gold"].setValue(3.5)
    dialog.name_edit.setText("  ")
    assert not dialog.ok_button.isEnabled()
    dialog.name_edit.setText("Fire slime")
    assert dialog.ok_button.isEnabled()
    assert dialog.definition() == {
        "id": "sample_pack.variants.fire_slime",
        "source": "sample_pack.enemies.slime_idle",
        "name": "Fire slime",
        "op": "hue",
        "params": {"shift": 120, "saturation": 0.5, "value": 1.5},
        "stats": {"hp": 2.0, "gold": 3.5},
    }


def test_the_palette_table_has_the_sources_colours_and_an_eyedropper(qtbot) -> None:
    dialog = _dialog(qtbot)
    assert dialog.table.rowCount() == len(dialog.colours) > 1
    assert dialog.table.item(0, 0).text() == "#{:02x}{:02x}{:02x}".format(*dialog.colours[0])
    # clicking a pixel of the source finds its colour's row and shows the table
    x, y = next(
        (x, y)
        for y in range(dialog.image.height)
        for x in range(dialog.image.width)
        if dialog.image.getpixel((x, y))[3] == 255
        and dialog.image.getpixel((x, y))[:3] == dialog.colours[1]
    )
    scale = dialog.source_view.scale
    left = (dialog.source_view.width() - round(dialog.image.width * scale)) // 2
    top = (dialog.source_view.height() - round(dialog.image.height * scale)) // 2
    at = QPoint(left + int(x * scale + scale / 2), top + int(y * scale + scale / 2))
    assert dialog.source_view.pixel_at(at) == (x, y)
    qtbot.mouseClick(dialog.source_view, Qt.MouseButton.LeftButton, pos=at)
    assert dialog.op() == "palette"
    assert dialog.table.currentRow() == 1
    assert dialog.source_view.pixel_at(QPoint(0, 0)) is None or left == 0
    # a row's colour becomes another one
    dialog.choose_colour = lambda start: (1, 2, 3)  # type: ignore[method-assign]
    dialog.pick_colour(1)
    assert dialog.table.item(1, 1).text() == "#010203"
    assert dialog.params() == {"map": [[list(dialog.colours[1]), [1, 2, 3]]]}
    result = dialog.result_image
    changed = [
        (x, y)
        for y in range(result.height)
        for x in range(result.width)
        if result.getpixel((x, y))[:3] == (1, 2, 3) and result.getpixel((x, y))[3] > 0
    ]
    assert changed, "the preview shows the new colour"
    dialog.choose_colour = lambda start: None  # type: ignore[method-assign]
    dialog.pick_colour(0)
    assert dialog.params() == {"map": [[list(dialog.colours[1]), [1, 2, 3]]]}, "cancelled"
    assert dialog.definition()["op"] == "palette"


def test_a_sprite_that_is_no_enemy_has_no_stats(qtbot) -> None:
    dialog = _dialog(qtbot, "hero.png")
    assert dialog.stats_box.isHidden()
    assert "stats" not in dialog.definition()


# ------------------------------------------------------------------------ the audit page


def _accept(dialog: VariantDialog) -> bool:
    dialog.hue_dial.setValue(120)
    dialog.name_edit.setText("Fire slime")
    dialog.stat_spins["hp"].setValue(2.0)
    return True


def test_make_variant_adds_the_asset_as_one_undo_step(qtbot) -> None:
    page, state = _page(qtbot)
    slime = _slime(page.session.catalog)
    count = len(page.session.catalog.assets)
    page.grid.chips["chipAll"].click()  # a variant is CONFIRMED: show those too
    page.grid.select_ids([slime.id])
    assert page.can_make_variant() and page.selected_variant() is None
    page.run_variant_dialog = _accept  # type: ignore[method-assign]
    before = page.session.undo_stack.count()
    variant_id = page.make_variant()
    assert variant_id == "sample_pack.variants.fire_slime"
    cat = page.session.catalog
    assert len(cat.assets) == count + 1 and [v["id"] for v in cat.variants] == [variant_id]
    assert page.session.undo_stack.count() == before + 1
    variant = cat.asset(variant_id)
    assert catalog.effective(variant)["derived_from"] == slime.id
    assert catalog.effective(variant)["role"] == "ENEMY"
    # it is in the grid, selected, with its name, its glyph and its own picture
    assert page.grid.selected_ids() == [variant_id]
    model = page.grid.model
    row = next(
        i for i in range(model.rowCount()) if model.index(i).data(ag.AssetIdRole) == variant_id
    )
    index = model.index(row)
    assert index.data(Qt.ItemDataRole.DisplayRole) == "Fire slime"
    assert index.data(ag.VariantRole) == slime.id
    assert ag.VARIANT_GLYPH in index.data(Qt.ItemDataRole.ToolTipRole)
    source_row = next(
        i for i in range(model.rowCount()) if model.index(i).data(ag.AssetIdRole) == slime.id
    )
    assert model.index(source_row).data(ag.VariantRole) is None
    file = model.resolver(variant)
    assert file is not None and Path(file) == variants.cached_file(variant.sha256)
    with Image.open(file) as rendered:
        assert rendered.size == tuple(catalog.effective(slime)["size"])
    # a variant of a variant is not offered; removing is
    assert not page.can_make_variant() and page.selected_variant() == variant_id
    # undo takes the asset and its definition away, redo brings both back
    page.session.undo_stack.undo()
    assert page.session.catalog.asset(variant_id) is None and page.session.catalog.variants == []
    page.session.undo_stack.redo()
    assert page.session.catalog.asset(variant_id) is not None
    # Remove variant is one step too
    page.grid.select_ids([variant_id])
    assert page.remove_variant()
    assert page.session.catalog.asset(variant_id) is None and page.session.catalog.variants == []
    page.session.undo_stack.undo()
    assert page.session.catalog.asset(variant_id) is not None
    # leaving the page hands the catalog with the variant to the next one
    page.leave(state)
    assert [v["name"] for v in state.catalog.variants] == ["Fire slime"]


def test_a_cancelled_dialog_and_other_selections_change_nothing(qtbot) -> None:
    page, _state_ = _page(qtbot)
    cat = page.session.catalog
    page.run_variant_dialog = lambda dialog: False  # type: ignore[method-assign]
    page.grid.select_ids([_slime(cat).id])
    assert page.make_variant() is None and page.session.catalog.variants == []
    sound = next(a for a in cat.assets if a.kind == "audio")
    page.grid.select_ids([sound.id])
    assert not page.can_make_variant() and page.make_variant() is None
    page.grid.select_ids([a.id for a in cat.assets if a.kind == "image"][:2])
    assert not page.can_make_variant(), "one asset at a time"
    assert not page.remove_variant()


def test_the_card_of_a_variant_has_the_glyph(qtbot) -> None:
    page, _state_ = _page(qtbot)
    page.grid.select_ids([_slime(page.session.catalog).id])
    page.run_variant_dialog = _accept  # type: ignore[method-assign]
    variant_id = page.make_variant()
    model = page.grid.model
    delegate = ag.AssetCardDelegate()
    cell = ag.grid_size_for(delegate.thumb)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, cell.width(), cell.height())

    def corner_of(asset_id: str) -> set[int]:
        row = next(
            i for i in range(model.rowCount()) if model.index(i).data(ag.AssetIdRole) == asset_id
        )
        image = QImage(cell, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        delegate.paint(painter, option, model.index(row, 0))
        painter.end()
        corner = QRect(2 + delegate.STRIP + 4, 2 + 4, 14, 14)
        return {
            image.pixelColor(x, y).rgb()
            for x in range(corner.left(), corner.right())
            for y in range(corner.top(), corner.bottom())
        }

    base = option.palette.base().color().rgb()
    ink = option.palette.text().color().rgb()

    def channels(rgb: int) -> tuple[int, int, int]:
        return (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255

    def distance(a: int, b: int) -> int:
        return sum(abs(x - y) for x, y in zip(channels(a), channels(b), strict=True))

    def inked(found: set[int]) -> bool:
        """A stroke of the glyph: a pixel in the text colour. A small glyph may have no pixel of
        the pure colour (the font and Qt version decide how much of it is anti-aliased, as on
        PySide6 6.7 with DejaVu), so a pixel nearer to the ink than to the patch counts."""
        return any(distance(p, ink) <= distance(p, base) for p in found)

    pixels = corner_of(variant_id)
    assert base in pixels and inked(pixels), "the glyph is drawn on its own patch"
    source = corner_of(_slime(page.session.catalog).id)
    assert not inked(source) or base not in source, "the source has no glyph"
