from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from rpggen.core import anim_edit, catalog
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.anim_preview import AnimEditorDialog

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


# ------------------------------------------------------------------------ pure helpers


def test_standard_names_and_groups() -> None:
    have = {"walk_down": {}, "walk_up": {}, "idle_down": {}, "death": {}}
    missing = anim_edit.missing_standard_names(have)
    assert "walk_left" in missing and "walk_down" not in missing and "death" not in missing
    assert anim_edit.groups(list(have)) == [
        ("idle", ["idle_down"]),
        ("walk", ["walk_down", "walk_up"]),
        ("death", ["death"]),
    ]
    assert anim_edit.mirror_name("walk_left") == "walk_right"
    assert anim_edit.mirror_name("walk_up") is None and anim_edit.mirror_name("death") is None


def test_list_edits() -> None:
    a = {"frames": [[0, 0], [1, 0], [2, 0]], "fps": 8, "loop": True}
    assert anim_edit.reversed_frames(a)["frames"] == [[2, 0], [1, 0], [0, 0]]
    assert anim_edit.ping_pong(a)["frames"] == [[0, 0], [1, 0], [2, 0], [1, 0]]
    assert anim_edit.cleared(a)["frames"] == []
    t = anim_edit.toggle_cell(a, (5, 1))
    assert t["frames"][-1] == [5, 1]
    assert anim_edit.toggle_cell(t, (1, 0))["frames"] == [[0, 0], [2, 0], [5, 1]]
    assert anim_edit.mirrored(a)["flip_h"] is True
    assert anim_edit.mirrored(anim_edit.mirrored(a)).get("flip_h") is False
    rect = {"frames": [[0, 0]], "fps": 8, "loop": True, "rects": [[1, 2, 3, 4]]}
    assert "rects" not in anim_edit.toggle_cell(rect, (0, 1))


def test_cell_at_and_frame_rect() -> None:
    grid = {"cell": [16, 16], "margin": [1, 1], "separation": [2, 2]}
    assert anim_edit.cell_at(grid, 1, 1) == (0, 0)
    assert anim_edit.cell_at(grid, 17, 1) is None  # gutter
    assert anim_edit.cell_at(grid, 19, 20) == (1, 1)
    assert anim_edit.cell_at(grid, 0, 5) is None  # margin
    anim = {"frames": [[1, 1]], "fps": 8, "loop": True}
    assert anim_edit.frame_rect(anim, 0, (16, 16), grid) == (19, 19, 16, 16)
    assert anim_edit.frame_rect(anim, 0, (32, 48), None) == (32, 48, 32, 48)
    with_rects = {**anim, "rects": [[5, 6, 7, 8]]}
    assert anim_edit.frame_rect(with_rects, 0, (16, 16), grid) == (5, 6, 7, 8)


def test_durations_override_fps() -> None:
    anim = {"frames": [[0, 0], [1, 0]], "fps": 10, "loop": True, "durations": [0.5]}
    assert anim_edit.frame_duration_ms(anim, 0) == 500
    assert anim_edit.frame_duration_ms(anim, 1) == 100


def test_overrides_diff_removes_lost_keys() -> None:
    eff = {
        "walk_down": {"frames": [[0, 0]], "fps": 8, "loop": True, "rects": [[0, 0, 8, 8]]},
        "old": {"frames": [], "fps": 8, "loop": True},
    }
    edited = {
        "walk_down": {"frames": [[0, 0], [1, 0]], "fps": 8, "loop": True},
        "new": {"frames": [[0, 1]], "fps": 6, "loop": False},
    }
    diff = anim_edit.anim_overrides(eff, edited)
    assert diff["walk_down"]["rects"] is None and diff["walk_down"]["frames"] == [[0, 0], [1, 0]]
    assert diff["old"] is None and diff["new"]["fps"] == 6
    merged = catalog.merge({"animations": eff}, {"animations": diff})["animations"]
    assert merged == edited
    assert anim_edit.anim_overrides(eff, eff) == {}


# ------------------------------------------------------------------------ the dialog


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


def _hero(state):
    asset = state.catalog.asset("basic16.characters.hero")
    assert asset is not None and catalog.effective(asset).get("animations")
    return asset


def _dialog(qtbot, audit, **kwargs) -> AnimEditorDialog:
    page, state = audit
    asset = _hero(state)
    eff = catalog.effective(asset)
    grid = eff.get("grid")
    dialog = AnimEditorDialog(
        page.resolver(asset),
        eff["animations"],
        tuple(eff.get("frame") or grid["cell"]),
        tuple(eff["origin"]) if eff.get("origin") else None,
        grid,
        **kwargs,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_tree_groups_directions_together(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    tree = dialog.tree
    tops = {
        tree.topLevelItem(i).text(0): tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
    }
    assert "walk" in tops
    walk = tops["walk"]
    children = [walk.child(i).text(0) for i in range(walk.childCount())]
    assert children and all(c.startswith("walk_") for c in children)


def test_playback_uses_fps_and_stops_a_non_looping_animation(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    dialog.select("walk_down")
    count = len(dialog.anim()["frames"])
    assert count > 1
    dialog.fps_spin.setValue(10)
    assert dialog.interval_ms() == 100
    dialog.speed.setValue(200)
    assert dialog.interval_ms() == 50
    dialog.step()
    assert dialog.index == 1 and dialog.frame_label.text() == f"Frame 2 of {count}"
    dialog.loop_check.setChecked(False)
    dialog.index = 0
    dialog.play_button.setChecked(True)
    qtbot.waitUntil(lambda: not dialog.play_button.isChecked(), timeout=5000)
    assert dialog.index == count - 1


def test_flip_mirrors_the_pixmap(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    dialog.select("walk_down")
    normal = dialog.preview.pixmap.toImage()
    dialog.flip_check.setChecked(True)
    flipped = dialog.preview.pixmap.toImage()
    assert flipped == normal.flipped(Qt.Orientation.Horizontal)


def test_clicking_cells_edits_the_frame_list_in_click_order(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    dialog.add_animation("attack_down")
    dialog.select("attack_down")
    cw, ch = dialog.grid["cell"]
    dialog._on_sheet_click(cw * 2 + 1, 1)
    dialog._on_sheet_click(1, 1)
    assert dialog.anim()["frames"] == [[2, 0], [0, 0]]
    dialog._on_sheet_click(cw * 2 + 1, 1)  # again: removed
    assert dialog.anim()["frames"] == [[0, 0]]
    dialog._on_sheet_click(1, ch + 1)
    dialog.reverse_button.click()
    assert dialog.anim()["frames"] == [[0, 1], [0, 0]]
    dialog.pingpong_button.click()
    dialog.clear_button.click()
    assert dialog.anim()["frames"] == []


def test_add_and_mirror(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    labels = [a.text().split(" ")[0] for a in dialog.add_button.menu().actions()]
    assert "attack_down" in labels and "walk_down" not in labels
    dialog.add_animation("attack_right")
    assert dialog.anim()["frames"] == []
    dialog.select("walk_right")
    dialog.mirror_from("walk_right", "walk_left")
    left = dialog.animations["walk_left"]
    assert left["flip_h"] is True and left["frames"] == dialog.animations["walk_right"]["frames"]


def test_origin_picker_and_active_frames_field(qtbot, audit) -> None:
    arpg = _dialog(qtbot, audit, arpg=True)
    turn = _dialog(qtbot, audit, arpg=False)
    assert not arpg.active_edit.isHidden() and turn.active_edit.isHidden()
    arpg.select("walk_down")
    arpg.active_edit.setText("1, 2")
    arpg.active_edit.editingFinished.emit()
    assert arpg.anim()["active_frames"] == [1, 2]
    arpg._on_origin(8, 20)
    assert arpg.overrides()["origin"] == [8, 20]


def test_apply_writes_overrides_in_one_undo_step(qtbot, audit) -> None:
    page, state = audit
    asset = _hero(state)
    before = catalog.effective(asset)["animations"]

    def run(dialog) -> bool:
        dialog.select("walk_down")
        dialog.fps_spin.setValue(3)
        dialog.add_animation("death")
        dialog.select("death")
        dialog._on_sheet_click(1, 1)
        dialog._on_origin(7, 23)
        return True

    page.run_dialog = run  # type: ignore[method-assign]
    assert page.edit_animations(asset.id)
    edited = catalog.effective(page.session.catalog.asset(asset.id))
    assert edited["animations"]["walk_down"]["fps"] == 3
    assert edited["animations"]["death"]["frames"] == [[0, 0]]
    assert edited["animations"]["walk_down"]["frames"] == before["walk_down"]["frames"]
    assert edited["origin"] == [7, 23]
    assert page.session.undo_stack.count() == 1
    page.session.undo_stack.undo()
    assert catalog.effective(page.session.catalog.asset(asset.id))["animations"] == before


def test_unchanged_dialog_changes_nothing(qtbot, audit) -> None:
    page, state = audit
    page.run_dialog = lambda dialog: True  # type: ignore[method-assign]
    assert not page.edit_animations(_hero(state).id)
    assert page.session.undo_stack.count() == 0


def test_cancel_stops_the_timer(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    dialog.select("walk_down")
    dialog.play_button.setChecked(True)
    dialog.reject()
    assert not dialog.timer.isActive()
