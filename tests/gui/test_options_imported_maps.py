"""T12.49: the Options page lists the maps imported from Tiled and LDtk files."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from rpggen.core import archive, catalog, config, inventory, options
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.state import WizardState

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
TOWN = "tiled_map.maps.town"
CAVE = "tiled_map.maps.cave"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(name: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / name, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    return cat


def _page(qtbot, name: str = "tiled_map", **imported) -> tuple[OptionsPage, WizardState]:
    ref = config.PackRef(name, "C:/x", "0" * 64, "folder")
    cfg = config.default_for("T", [ref])
    cfg.imported_maps = dict(imported)
    state = WizardState(config=cfg, catalog=_catalog(name))
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def _item(page: OptionsPage, map_id: str):
    for row in range(page.imported_list.count()):
        item = page.imported_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == map_id:
            return item
    raise AssertionError(map_id)


def test_the_box_is_hidden_for_packs_without_maps(qtbot) -> None:
    ref = config.PackRef("basic16", "C:/x", "0" * 64, "folder")
    state = WizardState(config=config.default_for("T", [ref]), catalog=_catalog("basic16"))
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    assert not page.imported_box.isVisible()
    page.leave(state)
    assert "imported_maps" not in state.config.to_json()


def test_every_map_is_listed_with_a_checkbox_and_nothing_is_chosen_at_first(qtbot) -> None:
    page, state = _page(qtbot)
    assert page.imported_box.isVisible()
    assert page.imported_list.count() == 4
    assert page.imported_values() == {}
    assert "maps/town · tiled_map · 6 × 4 tiles" in [
        page.imported_list.item(r).text() for r in range(page.imported_list.count())
    ]
    page.leave(state)
    assert "imported_maps" not in state.config.to_json()


def test_checked_maps_are_stored_in_the_config(qtbot) -> None:
    page, state = _page(qtbot)
    _item(page, CAVE).setCheckState(Qt.CheckState.Checked)
    page.leave(state)
    assert state.config.to_json()["imported_maps"] == {"include": [CAVE]}
    again = OptionsPage()
    qtbot.addWidget(again)
    again.enter(state)
    assert _item(again, CAVE).checkState() == Qt.CheckState.Checked
    assert _item(again, TOWN).checkState() == Qt.CheckState.Unchecked


def test_choosing_a_starter_checks_it_and_skips_the_layout_options(qtbot) -> None:
    page, state = _page(qtbot)
    assert page.starter_counts["npcs"].isEnabled() and not page.starter_note.isVisible()
    page.imported_starter.setCurrentIndex(page.imported_starter.findData(TOWN))
    town = _item(page, TOWN)
    assert town.checkState() == Qt.CheckState.Checked
    assert not town.flags() & Qt.ItemFlag.ItemIsUserCheckable  # it is always built
    assert not page.starter_counts["npcs"].isEnabled()
    assert not page.starter_size.isEnabled() and page.starter_note.isVisible()
    assert page.draft.imported_maps == {"include": [TOWN], "starter": TOWN}
    page.leave(state)
    assert state.config.to_json()["imported_maps"] == {"include": [TOWN], "starter": TOWN}
    # back to the planner
    page.imported_starter.setCurrentIndex(0)
    assert page.starter_counts["npcs"].isEnabled() and not page.starter_note.isVisible()
    assert _item(page, TOWN).flags() & Qt.ItemFlag.ItemIsUserCheckable


def test_the_summary_follows_the_choice(qtbot) -> None:
    page, _state = _page(qtbot)
    page.imported_starter.setCurrentIndex(page.imported_starter.findData(TOWN))
    _item(page, CAVE).setCheckState(Qt.CheckState.Checked)
    assert page.draft.imported_maps == {"include": [CAVE, TOWN], "starter": TOWN}
    assert page.summary.maps_label.text() == "Maps: Starter map (imported), 1 imported map"


def test_a_selection_of_a_map_the_catalog_lost_is_dropped(qtbot) -> None:
    page, state = _page(qtbot, include=["gone.map", CAVE], starter="gone.map")
    assert page.imported_values() == {"include": [CAVE]}
    page.leave(state)
    assert state.config.to_json()["imported_maps"] == {"include": [CAVE]}


def test_without_a_catalog_the_selection_of_the_config_is_kept(qtbot) -> None:
    ref = config.PackRef("tiled_map", "C:/x", "0" * 64, "folder")
    cfg = config.default_for("T", [ref])
    cfg.imported_maps = {"include": [CAVE], "starter": CAVE}
    state = WizardState(config=cfg)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    page.leave(state)
    assert state.config.to_json()["imported_maps"] == {"include": [CAVE], "starter": CAVE}


def test_the_solid_values_dialog_changes_the_catalog(qtbot) -> None:
    page, state = _page(qtbot, "ldtk_level")
    assert page.solid_button.isVisibleTo(page)
    seen = []
    page.run_dialog = lambda dialog: (seen.append(dialog), _tick_water(dialog), True)[2]
    changed = []
    page.changed.connect(lambda: changed.append(True))
    assert page.edit_solid_values() is True
    rows = {(r["value"]): r["solid"] for r in options.intgrid_rows(state.catalog.maps)}
    assert rows == {1: True, 2: True}
    assert seen[0].list.count() == 2 and changed
    # cancelling changes nothing
    page.run_dialog = lambda dialog: False
    assert page.edit_solid_values() is False


def _tick_water(dialog) -> None:
    dialog.list.item(1).setCheckState(Qt.CheckState.Checked)


def test_a_pack_without_intgrid_layers_has_no_solid_button(qtbot) -> None:
    page, _state = _page(qtbot, "tiled_map")
    assert not page.solid_button.isVisibleTo(page)


def test_an_existing_starter_map_cannot_be_replaced_by_an_imported_one(
    qtbot, tmp_path: Path
) -> None:
    project = tmp_path / "game"
    (project / "game" / "maps").mkdir(parents=True)
    (project / "game" / "maps" / "starter_map.tscn").write_text("[gd_scene]\n", encoding="utf-8")
    ref = config.PackRef("tiled_map", "C:/x", "0" * 64, "folder")
    state = WizardState(
        config=config.default_for("T", [ref]),
        catalog=_catalog("tiled_map"),
        target=project,
        regenerating=True,
    )
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    assert not page.imported_starter.isEnabled()
    assert page.imported_list.isEnabled()  # a map that is not there yet can still be added
