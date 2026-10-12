from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QSpinBox

from rpggen.core import catalog
from rpggen.core.analyzer import frames as frames_mod
from rpggen.core.analyzer import grid as grid_mod
from rpggen.core.analyzer import image_facts
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.grid_editor import GridEditorDialog, HeadingRing

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _sheet() -> Path:
    return SYNTH / "basic16" / "tiles" / "terrain.png"


def test_readout_counts_cells_and_remainder() -> None:
    mask = np.zeros((40, 50), dtype=bool)
    mask[0:16, 0:16] = True
    info = grid_mod.grid_readout(mask, (16, 16), (0, 0), (0, 0))
    assert (info.cols, info.rows, info.nonempty) == (3, 2, 1)
    assert info.remainder == (2, 8)
    clean = grid_mod.grid_readout(np.ones((32, 32), dtype=bool), (16, 16), (0, 0), (0, 0))
    assert clean.remainder == (0, 0) and clean.nonempty == 4
    gutter = grid_mod.grid_readout(np.ones((34, 34), dtype=bool), (16, 16), (0, 0), (2, 2))
    assert (gutter.cols, gutter.rows, gutter.remainder) == (2, 2, (0, 0))
    assert grid_mod.grid_readout(mask, (0, 0), (0, 0), (0, 0)).cols == 0


def test_dialog_readout_and_warning(qtbot) -> None:
    dialog = GridEditorDialog(_sheet(), {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]})
    qtbot.addWidget(dialog)
    dialog.show()
    a = image_facts.load_rgba(_sheet())
    h, w = a.shape[:2]
    assert dialog.readout.text().startswith(f"{w // 16} × {h // 16},")
    assert dialog.warning.isHidden() == (w % 16 == 0 and h % 16 == 0)
    dialog.cell_w.setValue(15)  # square lock keeps h in step
    assert dialog.cell_h.value() == 15
    assert not dialog.warning.isHidden() and "ASSET-003" in dialog.warning.text()
    dialog.square.setChecked(False)
    dialog.cell_h.setValue(10)
    assert dialog.grid()["cell"] == [15, 10]


def test_overlay_draws_margin_gutters_and_lines(qtbot) -> None:
    dialog = GridEditorDialog(_sheet(), {"cell": [16, 16], "margin": [1, 1], "separation": [2, 2]})
    qtbot.addWidget(dialog)
    plain = GridEditorDialog(_sheet(), {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]})
    qtbot.addWidget(plain)
    assert len(dialog.view.grid_items) > len(plain.view.grid_items) > 0


def test_candidates_are_listed_and_clicking_applies_one(qtbot) -> None:
    dialog = GridEditorDialog(_sheet(), {"cell": [8, 8], "margin": [0, 0], "separation": [0, 0]})
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.candidate_list.count() > 0, timeout=10000)
    assert 1 <= dialog.candidate_list.count() <= 5
    first = dialog._candidates[0]
    assert f"{first.cell[0]}×{first.cell[1]}" in dialog.candidate_list.item(0).text()
    dialog._on_candidate(dialog.candidate_list.item(0))
    assert dialog.grid()["cell"] == list(first.cell)
    assert dialog.grid()["margin"] == list(first.margin)


@pytest.fixture
def audit(qtbot):
    state = WizardState(pack_sources=[SYNTH / "basic16"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    page.grid.chips["chipAll"].click()
    return page, state


def test_apply_writes_a_grid_override_keeping_source_ids(audit) -> None:
    page, state = audit
    asset = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "tiles")
    ids_before = {s["asset"]: s["source_id"] for t in state.catalog.tilesets for s in t.sources}
    original = catalog.effective(asset)["grid"]

    def run(dialog) -> bool:
        dialog.margin_x.setValue(0)
        dialog.set_grid({**original, "margin": list(original["margin"])})
        dialog.sep_x.setValue(original["separation"][0])
        return True

    page.run_dialog = run  # type: ignore[method-assign]
    assert page.edit_grid(asset.id)
    new = page.session.catalog.asset(asset.id)
    assert new.overrides["grid"] == {
        "cell": original["cell"],
        "margin": original["margin"],
        "separation": original["separation"],
    }
    assert new.status == "CONFIRMED"
    ids_after = {
        s["asset"]: s["source_id"] for t in page.session.catalog.tilesets for s in t.sources
    }
    assert ids_after == ids_before
    page.session.undo_stack.undo()
    assert page.session.catalog.asset(asset.id).overrides == {}


def test_cancel_changes_nothing(audit) -> None:
    page, state = audit
    asset = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "tiles")
    page.run_dialog = lambda dialog: False  # type: ignore[method-assign]
    assert not page.edit_grid(asset.id)
    assert page.session.undo_stack.count() == 0


def test_spin_boxes_have_object_names(qtbot) -> None:
    dialog = GridEditorDialog(_sheet(), None)
    qtbot.addWidget(dialog)
    names = {s.objectName() for s in dialog.findChildren(QSpinBox)}
    assert {"cellW", "cellH", "marginX", "marginY", "sepX", "sepY"} <= names


# ------------------------------------------------------------------ T16.02: the heading ring


def _car() -> Path:
    return SYNTH / "racer" / "cars" / "player_car.png"  # 16 views of 24 x 24 in one row


def test_the_views_of_a_rotation_sheet_point_round_the_ring() -> None:
    up = frames_mod.heading_angles(4, "up_cw")
    assert [round(math.degrees(a)) for a in up] == [-90, 0, 90, 180]  # up, right, down, left
    other = frames_mod.heading_angles(4, "right_ccw")
    assert [round(math.degrees(a)) for a in other] == [0, -90, -180, -270]
    assert len(frames_mod.heading_angles(16, "up_ccw")) == 16
    assert frames_mod.heading_angles(0) == [] and frames_mod.heading_angles(8, "?")[0] < 0


def test_the_grid_editor_shows_the_headings_as_a_ring(qtbot) -> None:
    grid = {"cell": [24, 24], "margin": [0, 0], "separation": [0, 0]}
    dialog = GridEditorDialog(_car(), grid, headings=16, heading_order="up_cw")
    qtbot.addWidget(dialog)
    dialog.show()
    ring = dialog.ring
    assert ring is not None and ring.isVisibleTo(dialog)
    assert "16 headings" in dialog.ring_label.text()
    spots = ring.positions()
    assert len(spots) == 16
    assert len({(round(p.x()), round(p.y())) for p in spots}) == 16, "sixteen places"
    centre = (ring.width() / 2, ring.height() / 2)
    assert abs(spots[0].x() - centre[0]) < 1 and spots[0].y() < centre[1], "the first is up"
    assert spots[4].x() > centre[0] and abs(spots[4].y() - centre[1]) < 1, "a quarter on: right"
    assert spots[1].x() > spots[0].x(), "clockwise"
    reach = {round(math.hypot(p.x() - centre[0], p.y() - centre[1]), 3) for p in spots}
    assert len(reach) == 1, "all on one circle"
    assert [ring.frame_rect(i).x() for i in (0, 1, 15)] == [0, 24, 360]
    # it paints: the car's pixels are at the top of the ring and nothing is in its middle
    image = ring.grab().toImage()
    background = image.pixelColor(int(centre[0]), int(centre[1]))
    box = range(-6, 7)
    at_first = {
        image.pixelColor(int(spots[0].x()) + dx, int(spots[0].y()) + dy).rgba()
        for dx in box
        for dy in box
    }
    assert len(at_first - {background.rgba()}) >= 2
    # the other way round, and the ring follows the grid being edited
    ring.set_ring(16, "up_ccw", grid)
    assert ring.positions()[1].x() < ring.positions()[0].x()
    dialog.cell_w.setValue(48)
    assert ring.grid["cell"][0] == 48 and ring.frame_rect(1).x() == 48
    ring.grab()  # eight cells for sixteen headings: the missing views are left out, no error


def test_a_sheet_without_headings_has_no_ring(qtbot) -> None:
    dialog = GridEditorDialog(_sheet(), None)
    qtbot.addWidget(dialog)
    assert dialog.ring is None and dialog.findChild(HeadingRing) is None


def test_the_audit_opens_the_ring_for_a_rotation_sheet(qtbot) -> None:
    state = WizardState(pack_sources=[SYNTH / "racer"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    car = next(a for a in state.catalog.assets if a.path.endswith("player_car.png"))
    eff = catalog.effective(car)
    seen: list[GridEditorDialog] = []
    page.run_dialog = lambda dialog: bool(seen.append(dialog))  # type: ignore[method-assign]
    assert not page.edit_grid(car.id)
    (dialog,) = seen
    assert dialog.ring is not None and dialog.ring.headings == eff["headings"] == 16
    assert dialog.ring.order == eff["heading_order"] and len(dialog.ring.positions()) == 16
    tiles = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "tiles")
    assert not page.edit_grid(tiles.id) and seen[-1].ring is None
