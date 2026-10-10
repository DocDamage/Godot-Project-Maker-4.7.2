from __future__ import annotations

import copy
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTransform

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
    # QImage.flipped is Qt 6.9+; a mirroring transform works on every version CI tests (6.7 up)
    assert flipped == normal.transformed(QTransform().scale(-1, 1))


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


# ------------------------------------------------------------------------ the shared player (T13.03)


def test_the_player_follows_fps_durations_speed_and_loop() -> None:
    from rpggen.gui.widgets.anim_preview import AnimPlayer

    anim = {"frames": [[0, 0], [1, 0], [2, 0]], "fps": 10, "loop": True}
    player = AnimPlayer(lambda: anim)
    seen: list[int] = []
    player.frameChanged.connect(seen.append)
    assert player.count() == 3 and player.interval_ms() == 100
    player.speed_percent = 200
    assert player.interval_ms() == 50
    for _ in range(4):  # the test is the clock
        player.tick()
    assert seen == [1, 2, 0, 1] and not player.timer.isActive(), "ticking alone starts no timer"
    anim["durations"] = [0.3, 0.1, 0.1]
    player.index = 0
    player.speed_percent = 100
    assert player.interval_ms() == anim_edit.frame_duration_ms(anim, 0)
    # a non-looping animation stops on its last frame and says so
    anim["loop"] = False
    ended: list[bool] = []
    player.finished.connect(lambda: ended.append(True))
    player.index = 1
    player.set_playing(True)
    assert player.timer.isActive()
    player.tick()
    assert player.index == 2 and player.playing
    player.tick()
    assert player.index == 2 and not player.playing and not player.timer.isActive()
    assert ended == [True]
    # nothing to play: no crash, no frame
    empty = AnimPlayer(lambda: None)
    empty.tick()
    empty.step()
    assert empty.count() == 0 and empty.index == 0


def test_the_detail_panel_has_a_transport_for_a_sprite_with_animations(qtbot, audit) -> None:
    page, state = audit
    hero = _hero(state)
    page.grid.select_ids([hero.id])
    detail = page.detail
    assert detail.anim_box.isVisibleTo(detail)
    names = [detail.anim_combo.itemData(i) for i in range(detail.anim_combo.count())]
    animations = catalog.effective(hero)["animations"]
    assert sorted(names) == sorted(animations)
    grouped = [n for _action, group in anim_edit.groups(list(animations)) for n in group]
    assert names == grouped, "grouped by action, directions in order, as in the dialog"
    walk = names.index("walk_down")
    detail.anim_combo.setCurrentIndex(walk)
    detail.anim_combo.activated.emit(walk)
    count = len(animations["walk_down"]["frames"])
    assert count > 1 and detail.anim_frame_label.text() == f"Frame 1 of {count}"
    # paused: the whole sheet with the frame marked on it
    sheet = detail.preview.image_size
    kinds = [m[0] for m in detail.preview.marks]
    assert kinds == ["current"] and detail.preview.grid_items
    # playing: the frame alone, advanced by the clock
    detail.anim_play_button.setChecked(True)
    assert detail.player.playing and detail.anim_play_button.text() == "Pause"
    frame = tuple(catalog.effective(hero)["frame"])
    assert detail.preview.image_size == frame and detail.preview.image_size != sheet
    detail.player.tick()
    assert detail.anim_frame_label.text() == f"Frame 2 of {count}"
    assert detail.preview.image_size == frame
    detail.anim_play_button.setChecked(False)
    assert not detail.player.timer.isActive() and detail.preview.image_size == sheet
    assert [m[0] for m in detail.preview.marks] == ["current"]
    # another animation starts at its first frame
    detail.player.step()
    assert detail.player.index == 2  # one tick above, one step here
    detail.anim_combo.setCurrentIndex(0)
    detail.anim_combo.activated.emit(0)
    assert detail.player.index == 0 and detail.animation_name() == names[0]


def test_playback_stops_with_the_asset_the_page_and_review_mode(qtbot, audit) -> None:
    page, state = audit
    hero = _hero(state)
    other = next(a for a in state.catalog.assets if a.id != hero.id)
    detail = page.detail

    def play() -> None:
        page.grid.select_ids([hero.id])
        detail.anim_play_button.setChecked(True)
        assert detail.player.timer.isActive()

    play()
    page.grid.select_ids([other.id])  # another asset
    assert not detail.player.timer.isActive() and not detail.anim_play_button.isChecked()
    play()
    page.leave(state)  # the page is left
    assert not detail.player.timer.isActive() and not detail.anim_play_button.isChecked()
    play()
    page.set_review_mode(True)  # into review mode: one playback, in the large view
    assert not detail.player.timer.isActive()
    assert detail.extra_view is page.review.preview and detail.views() == [page.review.preview]
    page.grid.select_ids([hero.id])
    detail.anim_play_button.setChecked(True)
    frame = tuple(catalog.effective(hero)["frame"])
    assert page.review.preview.image_size == frame, "the large view plays the frame"
    page.set_review_mode(False)
    assert not detail.player.timer.isActive() and detail.views() == [detail.preview]
    assert detail.preview.image_size != frame, "back to the whole sheet in the panel"


def test_active_frames_are_tinted_and_follow_the_edit(qtbot, audit) -> None:
    page, state = audit
    hero = _hero(state)
    page.grid.select_ids([hero.id])
    detail = page.detail
    name = "walk_down"
    walk = detail.anim_combo.findData(name)
    detail.anim_combo.setCurrentIndex(walk)
    detail.anim_combo.activated.emit(walk)
    assert detail.animation_name() == name
    assert "active" not in [m[0] for m in detail.preview.marks]
    eff = catalog.effective(hero)
    anim = dict(eff["animations"][name])
    anim["active_frames"] = [1]
    assert page.session.set_override(hero.id, "animations", {name: anim})
    marks = detail.preview.marks
    assert [m[0] for m in marks] == ["active", "current"], "no reopening: the edit is drawn"
    rect = anim_edit.frame_rect(anim, 1, tuple(eff["frame"]), eff.get("grid"))
    assert tuple(marks[0][1:]) == tuple(rect)


# ----------------------------------------------------------------- naming an animation (T16.21)


def test_an_animation_is_renamed_in_its_place_and_the_override_follows(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    before = dialog.names()
    old = "walk_left"
    assert old in before and "dash_left" not in before
    spec = copy.deepcopy(dialog.animations[old])
    asked: list[str] = []
    dialog.ask_name = lambda current: asked.append(current) or "Dash Left"  # type: ignore[method-assign]
    dialog.select(old)
    dialog.rename_button.click()
    assert asked == [old]
    after = dialog.names()
    assert after == ["dash_left" if n == old else n for n in before], "in the place it had"
    assert dialog.animations["dash_left"] == spec
    assert dialog.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "dash_left"
    overrides = dialog.overrides()["animations"]
    assert overrides[old] is None and overrides["dash_left"] == spec


def test_a_name_that_is_taken_or_no_name_changes_nothing(qtbot, audit) -> None:
    dialog = _dialog(qtbot, audit)
    before = copy.deepcopy(dialog.animations)
    for typed in ("walk_right", "walk_left", "", "   ", "9 lives", "größe"):
        assert not dialog.rename_animation("walk_left", typed), typed
    assert not dialog.rename_animation("no_such_animation", "jump_down")
    assert dialog.animations == before and dialog.overrides() == {}
    dialog.ask_name = lambda current: None  # type: ignore[method-assign]  # cancelled
    dialog.select("walk_left")
    dialog.rename_button.click()
    assert dialog.animations == before


def test_the_names_the_game_plays_are_offered_and_a_lone_action_faces_down() -> None:
    offered = anim_edit.offered_names({"walk_down": {}, "idle_down": {}})
    assert offered[:3] == ["idle_left", "idle_right", "idle_up"]
    assert "walk_down" not in offered and "jump_down" in offered and "shoot_up" in offered
    assert anim_edit.clean_name(" Attack ") == "attack_down"
    assert anim_edit.clean_name("Run-Fast 2") == "run_fast_2"
    assert anim_edit.clean_name("anim_3") == "anim_3"
    unnamed = {"anim_1": {"frames": [[0, 0]]}, "anim_2": {"frames": [[1, 0]]}}
    named = anim_edit.renamed(unnamed, "anim_2", "walk_down")
    assert list(named) == ["anim_1", "walk_down"] and named["walk_down"] == unnamed["anim_2"]
    assert anim_edit.renamed(unnamed, "anim_2", "anim_1") is unnamed
