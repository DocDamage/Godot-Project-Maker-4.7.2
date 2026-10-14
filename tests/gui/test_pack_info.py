"""The Audit page's Packs tab: licence, author and URL corrections (T12.51)."""

from __future__ import annotations

from rpggen.core import catalog as catalog_mod
from rpggen.core.licenses import PackLicense
from rpggen.gui import edits
from rpggen.gui.edits import EditSession
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.pack_info import PackInfoPanel


def _catalog() -> catalog_mod.Catalog:
    needs = catalog_mod.CatalogPack(
        "forest", "a", "assets/packs/forest", ["assets/packs/forest/LICENSE.txt"]
    )
    needs.license = PackLicense("CC-BY-4.0", "", "", True).to_json()
    free = catalog_mod.CatalogPack("sounds", "b", "assets/packs/sounds", [])
    free.license = PackLicense("CC0-1.0").to_json()
    return catalog_mod.Catalog(packs=[needs, free])


def test_set_pack_license_stores_only_real_corrections() -> None:
    cat = _catalog()
    new = edits.set_pack_license(cat, "forest", "author", "Jane")
    assert new is not cat and cat.packs[0].license_overrides == {}  # copy on write
    assert new.packs[0].license_overrides == {"author": "Jane"}
    assert edits.set_pack_license(new, "forest", "author", "Jane") is new  # nothing changes
    back = edits.set_pack_license(new, "forest", "author", "")
    assert back.packs[0].license_overrides == {}  # the detected value: no correction
    chosen = edits.set_pack_license(cat, "forest", "license_id", "CC0-1.0")
    assert not chosen.packs[0].effective_license().attribution_required
    assert edits.set_pack_license(cat, "nope", "author", "x") is cat
    assert edits.set_pack_license(cat, "forest", "colour", "x") is cat


def test_the_panel_edits_go_through_the_undo_stack(qtbot) -> None:
    session = EditSession(_catalog())
    panel = PackInfoPanel(session)
    qtbot.addWidget(panel)
    box = panel.boxes["forest"]
    assert list(panel.boxes) == ["forest", "sounds"]
    assert box.license_combo.currentData() == "CC-BY-4.0"
    assert box.credit_box.isChecked()
    assert not box.warning.isHidden()
    assert "LICENSE.txt" in box.files_label.text()
    assert panel.boxes["sounds"].warning.isHidden()
    assert panel.boxes["sounds"].files_label.text() == "No licence file found."
    box.author_edit.setText("Jane Doe")
    box.author_edit.editingFinished.emit()
    assert session.catalog.packs[0].effective_license().author == "Jane Doe"
    assert box.warning.isHidden()
    box.license_combo.setCurrentIndex(box.license_combo.findData("MIT"))
    box.license_combo.activated.emit(box.license_combo.currentIndex())
    assert session.catalog.packs[0].effective_license().license_id == "MIT"
    box.credit_box.setChecked(False)
    assert not session.catalog.packs[0].effective_license().attribution_required
    session.undo_stack.undo()
    session.undo_stack.undo()
    session.undo_stack.undo()
    assert session.catalog.packs[0].license_overrides == {}
    assert box.author_edit.text() == "" and not box.warning.isHidden()


def test_the_audit_page_has_a_packs_tab(qtbot) -> None:
    page = AuditPage()
    qtbot.addWidget(page)
    page.enter(WizardState(catalog=_catalog()))
    titles = [page.tabs.tabText(i) for i in range(page.tabs.count())]
    assert "Packs" in titles
    assert page.packs_panel is not None and set(page.packs_panel.boxes) == {"forest", "sounds"}


def test_a_pack_without_a_licence_file_takes_a_licence_and_a_credit_by_hand(qtbot) -> None:
    """T17.30: the card of a pack with no licence file has a credit line; what is stated there
    is a correction of the pack's licence, its user's own statement."""
    session = EditSession(_catalog())
    panel = PackInfoPanel(session)
    qtbot.addWidget(panel)
    with_file, without = panel.boxes["forest"], panel.boxes["sounds"]
    assert with_file.credit_edit.isHidden() and with_file.stated_note.isHidden()
    assert not without.credit_edit.isHidden() and not without.stated_note.isHidden()
    without.license_combo.setCurrentIndex(without.license_combo.findData("commercial"))
    without.license_combo.activated.emit(without.license_combo.currentIndex())
    without.credit_edit.setText("Sounds by Jane")
    without.credit_edit.editingFinished.emit()
    pack = session.catalog.packs[1]
    assert pack.license_overrides["credit"] == "Sounds by Jane"
    assert pack.licence_stated() and pack.effective_license().credit == "Sounds by Jane"
    session.undo_stack.undo()
    assert "credit" not in session.catalog.packs[1].license_overrides
    # the mark of AI-generated art, on any pack
    with_file.ai_box.setChecked(True)
    assert session.catalog.packs[0].effective_license().ai_generated
    with_file.ai_box.setChecked(False)
    assert "ai_generated" not in session.catalog.packs[0].license_overrides
