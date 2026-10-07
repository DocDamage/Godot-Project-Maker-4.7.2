from __future__ import annotations

from pathlib import Path

from PIL import Image

from rpggen.core import catalog
from rpggen.core.orchestrator import Callbacks
from rpggen.core.terrain import blob
from rpggen.core.terrain import rpgmaker_a2 as a2
from rpggen.gui import workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState

Q = 8
TILE = 2 * Q


def _blob_pack(tmp_path: Path) -> Path:
    block = Image.new("RGBA", (4 * Q, 6 * Q))
    for table in a2.QUARTER_TABLE.values():
        for j, (qx, qy) in enumerate(table.values()):
            color = (40 + 40 * j, 200 - 30 * j, 60 + 20 * j, 255)
            block.paste(color, (qx * Q, qy * Q, (qx + 1) * Q, (qy + 1) * Q))
    tiles = a2.compose_block(block, 0, 0, TILE)
    sheet = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 12) * TILE, (i // 12) * TILE))
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "LICENSE.txt").write_text("CC0\n")
    sheet.save(pack / "blob_terrain.png")
    return pack


def _page(qtbot, tmp_path: Path):
    state = WizardState(pack_sources=[_blob_pack(tmp_path)])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.show()
    page.enter(state)
    return page, state


def test_terrain_tab_lists_proposals_and_accepts_one(qtbot, tmp_path) -> None:
    page, _state = _page(qtbot, tmp_path)
    tab = page.terrain_tab
    assert tab is not None and page.tabs.tabText(page.tabs.indexOf(tab)) == "Terrain"
    assert tab.list.count() == 1 and tab.accept_button.isEnabled()
    asset_id = tab.current_id()
    assert tab.view.image_size == (12 * TILE, 4 * TILE)
    assert len(tab.view.grid_items) > 47  # bitmask squares over the sheet

    assert tab.accept_current()
    assert tab.list.count() == 0 and not tab.accept_button.isEnabled()
    asset = page.session.catalog.asset(asset_id)
    assert len(catalog.effective(asset)["tile_overrides"]) == 47
    assert any(t.terrain_sets for t in page.session.catalog.tilesets)

    page.session.undo_stack.undo()  # accepting is one undo step
    assert tab.list.count() == 1 and blob.has_proposal(page.session.catalog.asset(asset_id))


def test_terrain_tab_reject_hides_the_proposal(qtbot, tmp_path) -> None:
    page, _state = _page(qtbot, tmp_path)
    tab = page.terrain_tab
    asset_id = tab.current_id()
    assert tab.reject_current()
    asset = page.session.catalog.asset(asset_id)
    assert tab.list.count() == 0 and "tile_overrides" not in catalog.effective(asset)
