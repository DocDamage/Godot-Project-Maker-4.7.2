"""T17.29 in the wizard: a pack's layered character in the Compose dialog with its bodies and
parts as choices, and the Tile size of a pack drawn in several sizes on the Packs tab."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory, lpc_compose
from rpggen.gui.dialogs.character_dialog import CharacterDialog
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets.pack_info import PackInfoPanel

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _catalog(name: str) -> tuple[catalog.Catalog, dict[str, Path]]:
    opened = archive.open_pack(SYNTH / name, set(), pack_id=name)
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    return cat, {name: opened.root}


def test_the_layered_character_shows_its_bodies_and_parts(qtbot) -> None:  # noqa: ANN001
    cat, roots = _catalog("farm_layered")
    definition = cat.characters[0]
    body = cat.asset(definition["body"])
    assert body is not None
    dialog = CharacterDialog(cat, body, roots, definition)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Compose character"
    assert dialog.body_combo is not None and dialog.body_combo.count() == 2
    assert sorted(dialog.combos) == ["eyes", "hair", "hat", "torso"]
    assert dialog.combos["torso"].count() == 3  # (none) and two clothes
    assert dialog.preview.pixmap() is not None and not dialog.preview.pixmap().isNull()
    dialog.body_combo.setCurrentIndex(1)
    chosen = dialog.definition()
    assert chosen["body"] != definition["body"]
    assert chosen["id"] == definition["id"]
    assert lpc_compose.is_layered(cat.asset(chosen["body"]))


def test_the_packs_tab_offers_the_sizes_of_a_pack(qtbot) -> None:  # noqa: ANN001
    cat, _roots = _catalog("farm_sizes")
    session = EditSession(cat)
    panel = PackInfoPanel(session)
    qtbot.addWidget(panel)
    box = panel.boxes["farm_sizes"]
    assert [box.size_combo.itemText(i) for i in range(box.size_combo.count())] == [
        "16 px",
        "32 px",
    ]
    assert box.size_combo.currentIndex() == 0 and not box.size_combo.isHidden()
    box.size_combo.setCurrentIndex(1)
    box.size_combo.activated.emit(1)
    assert session.catalog.pack_sizes == {"farm_sizes": 32}
    assert box.size_combo.currentIndex() == 1
    session.undo_stack.undo()
    assert session.catalog.pack_sizes == {"farm_sizes": 16}


def test_a_pack_of_one_size_shows_no_size(qtbot) -> None:  # noqa: ANN001
    cat, _roots = _catalog("farm_crops")
    panel = PackInfoPanel(EditSession(cat))
    qtbot.addWidget(panel)
    assert panel.boxes["farm_crops"].size_combo.isHidden()
