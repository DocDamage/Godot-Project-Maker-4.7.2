"""T12.57: the Audit page exports a contact sheet of the assets it shows."""

from __future__ import annotations

from pathlib import Path

from rpggen.gui.dialogs.contact_sheet_dialog import ContactSheetDialog, SheetOptions
from tests.gui.test_bulk import _page


def test_the_audit_page_exports_the_filtered_assets(qtbot, tmp_path: Path) -> None:
    page, state = _page(qtbot)
    shown = page.grid.visible_ids()
    asked: list[tuple[int, int]] = []

    def options(n_shown: int, total: int) -> SheetOptions:
        asked.append((n_shown, total))
        return SheetOptions("pdf", "A4", filtered=True, grid_overlay=True)

    page.ask_sheet_options = options  # type: ignore[method-assign]
    page.ask_sheet_path = lambda fmt: tmp_path / "sheet.pdf"  # type: ignore[method-assign]
    said: list[list[Path]] = []
    page.say_sheet_written = said.append  # type: ignore[method-assign]
    files = page.export_contact_sheet()
    assert files == [tmp_path / "sheet.pdf"] and said == [files]
    assert asked == [(len(shown), len(state.catalog.assets))]
    assert (tmp_path / "sheet.pdf").read_bytes().startswith(b"%PDF-")
    page.ask_sheet_options = lambda n, t: None  # type: ignore[method-assign]
    assert page.export_contact_sheet() == []  # cancelled in the dialog


def test_the_dialog_starts_on_the_filtered_set_only_when_it_is_smaller(qtbot) -> None:
    narrowed = ContactSheetDialog(5, 40)
    qtbot.addWidget(narrowed)
    assert narrowed.options() == SheetOptions("pdf", "A4", filtered=True, grid_overlay=False)
    everything = ContactSheetDialog(40, 40)
    qtbot.addWidget(everything)
    assert everything.options().filtered is False
