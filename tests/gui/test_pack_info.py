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
