from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from rpggen.core import archive, catalog, config, inventory, mapping
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.dialogs.asset_picker import AssetPickerDialog
from rpggen.gui.pages.mapping_page import MORE_DATA, NONE_DATA, MappingPage
from rpggen.gui.state import WizardState

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _assemble(pack: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


# ------------------------------------------------------------------------ core


def test_rows_follow_requirements() -> None:
    rows = mapping.rows("turn_based")
    assert [r.role for r in rows][:2] == ["PLAYER", "GROUND"]
    assert {r.role for r in rows} == {
        "PLAYER",
        "GROUND",
        *["NPC", "ENEMY", "BUILDING", "WALL", "ITEM", "UI", "PORTRAIT"],
    }
    assert [r.required for r in rows][:3] == [True, True, False]
    assert {r.role: r.key for r in rows}["ITEM"] == "chest"
    assert {r.role: r.key for r in rows}["WALL"] is None


def test_default_and_resolved_starter() -> None:
    cat = _assemble("basic16")
    starter = mapping.default_starter(cat, "turn_based")
    assert starter["player"] == "basic16.characters.hero"
    assert starter["ground"] == "basic16.tiles.terrain"
    kept = mapping.resolve_starter(cat, "turn_based", {"player": "basic16.characters.hero"})
    assert kept["player"] == "basic16.characters.hero"
    stale = mapping.resolve_starter(cat, "turn_based", {"player": "gone", "enemy": "gone"})
    assert stale["player"] == "basic16.characters.hero" and "enemy" not in stale


def test_candidates_are_restricted_by_usage_and_ranked() -> None:
    cat = _assemble("mixed")
    tiles = mapping.candidates(cat, "GROUND")
    assert tiles and all(catalog.effective(a)["usage"] == "tiles" for a in tiles)
    assert catalog.effective(tiles[0]).get("role") == "GROUND"
    assert all(catalog.effective(a)["usage"] == "sprite" for a in mapping.candidates(cat, "PLAYER"))


def test_missing_required_counts_placeholders() -> None:
    cat = _assemble("mixed")  # ground and items but no player
    assert mapping.missing_required(cat, "turn_based", set()) == ["PLAYER"]
    assert mapping.missing_required(cat, "turn_based", {"PLAYER"}) == []


def test_buildings_may_be_objects() -> None:
    cat = _assemble("objects_in_sheet")
    assert cat.objects
    best = mapping.best_for(cat, "BUILDING")
    assert best is not None and (best in {o.id for o in cat.objects} or cat.asset(best))


# ------------------------------------------------------------------------ the page


def _page(qtbot, pack: str, archetype: str = "turn_based") -> tuple[MappingPage, WizardState]:
    state = WizardState(pack_sources=[SYNTH / pack], target=None, archetype=archetype)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef(
        state.opened_packs[0].pack_id,
        str(SYNTH / pack),
        "0" * 64,
        "folder",
    )
    state.config = config.default_for("T", [ref], archetype=archetype)
    page = MappingPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def test_checklist_shows_status_per_role(qtbot) -> None:
    page, state = _page(qtbot, "basic16")
    player = page.rows["PLAYER"]
    assert "assigned" in player.status_label.text()
    assert player.asset_combo.currentText() == "hero.png · basic16"
    assert player.asset_combo.toolTip() == "basic16.characters.hero"
    assert player.used_label.text() == "Used for the player actor"
    assert player.role_label.text().startswith("Player *")
    assert not player.thumb_label.pixmap().isNull()
    npc = page.rows["NPC"]
    assert npc.status_label.text().startswith("⚠")
    assert npc.without_radio.isChecked() and not npc.placeholder_radio.isChecked()
    assert not npc.fallback_box.isHidden() and player.fallback_box.isHidden()
    assert page.validate(state) == []


def test_required_missing_blocks_next_until_placeholder_or_choice(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    player = page.rows["PLAYER"]
    assert player.status_label.text().startswith("✖")
    assert [i.severity.value for i in page.validate(state)] == ["error"]
    assert player.without_radio.parent() is player.fallback_box and player.without_radio.isHidden()
    assert not player.placeholder_radio.isChecked() and not player.without_radio.isChecked()
    player.placeholder_radio.click()
    assert "PLAYER" in page.placeholders and page.validate(state) == []
    assert "placeholder" in player.status_label.text()
    page.leave(state)
    assert state.placeholders == {"PLAYER"}


def test_choose_assigns_the_role_and_stores_the_starter(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    sprite = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "sprite")
    assert catalog.effective(sprite).get("role") != "PLAYER"
    page.run_picker = lambda dialog: setattr(dialog, "picked", sprite.id) or True  # type: ignore[method-assign]
    assert page.choose("PLAYER")
    assert catalog.effective(state.catalog.asset(sprite.id))["role"] == "PLAYER"
    assert page.starter["player"] == sprite.id
    assert page.validate(state) == []
    page.leave(state)
    assert state.config.starter["player"] == sprite.id
    assert state.config.to_json()["starter"]["player"] == sprite.id


def test_cancelled_picker_changes_nothing(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    page.run_picker = lambda dialog: False  # type: ignore[method-assign]
    assert not page.choose("PLAYER")
    assert "player" not in page.starter


def test_picker_lists_plausible_assets_only(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    dialog = AssetPickerDialog(state.catalog, "GROUND", page_resolver(state))
    qtbot.addWidget(dialog)
    shown = dialog.grid.visible_ids()
    assert len(shown) == len(mapping.candidates(state.catalog, "GROUND")) > 0
    dialog.grid.select_ids([shown[0]])
    assert dialog.picked == shown[0] and dialog.ok_button.isEnabled()


def page_resolver(state):
    from rpggen.gui.pages.audit_page import make_resolver

    return make_resolver(state)


@pytest.mark.parametrize("pack", ["basic16", "mixed", "strips"])
def test_starter_survives_a_config_round_trip(qtbot, pack) -> None:
    page, state = _page(qtbot, pack)
    page.leave(state)
    cfg = config.GeneratorConfig.from_json(state.config.to_json())
    assert cfg.starter == state.config.starter


# ------------------------------------------------------------------------ sound


def test_sound_group_is_collapsed_with_a_summary_and_stores_the_choices(qtbot) -> None:
    from rpggen.core import sound_slots

    page, state = _page(qtbot, "audio_basic")
    section = page.sound_section
    assert not section.isHidden()
    assert section.body.isHidden()
    assert section.summary_label.text() == "3 music tracks, 4 sound effects assigned"
    section.edit_button.setChecked(True)
    assert not section.body.isHidden()
    battle = "audio_basic.music.battle_bgm"
    section.run_picker = lambda dialog: setattr(dialog, "picked", battle) or True  # type: ignore[method-assign]
    assert section.choose("music_map")
    assert section.sounds["music_map"] == battle
    section.clear("sfx_hit")
    assert section.sounds["sfx_hit"] == sound_slots.CLEARED
    assert section.summary_label.text() == "3 music tracks, 3 sound effects assigned"
    page.leave(state)
    assert state.config.sounds["music_map"] == battle
    assert state.config.to_json()["sounds"]["sfx_hit"] == ""
    # coming back keeps the cleared slot silent instead of refilling the default
    page.enter(state)
    assert page.sound_section.sounds["sfx_hit"] == ""


def test_the_sound_group_hides_when_the_packs_have_no_audio(qtbot) -> None:
    page, _state = _page(qtbot, "basic16")
    assert page.sound_section.isHidden()


def test_sound_picker_lists_only_the_right_kind_with_lengths(qtbot) -> None:
    from rpggen.core import sound_slots
    from rpggen.gui.widgets.sound_section import SoundPickerDialog

    page, state = _page(qtbot, "audio_basic")
    dialog = SoundPickerDialog(state.catalog, sound_slots.slot("music_map"), None)
    qtbot.addWidget(dialog)
    assert dialog.list.count() == 2
    assert "30.0 s" in dialog.list.item(1).text()
    sfx = SoundPickerDialog(state.catalog, sound_slots.slot("sfx_hit"), None)
    qtbot.addWidget(sfx)
    assert sfx.list.count() == 4


def test_rows_are_grouped_and_summarised(qtbot) -> None:
    page, _state = _page(qtbot, "basic16")
    headers = [
        page.findChild(type(page.summary_label), f"group_{g}")
        for g in ("World", "Characters", "Things", "Interface")
    ]
    assert all(h is not None for h in headers)
    assert (
        page.summary_label.text()
        == "2 of 2 required roles assigned, 0 of 7 optional roles assigned"
    )
    assert page.rows["GROUND"].role_label.text().startswith("Ground tiles *")


def test_clear_returns_a_chosen_role_to_the_automatic_choice(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    sprite = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "sprite")
    page.run_picker = lambda dialog: setattr(dialog, "picked", sprite.id) or True  # type: ignore[method-assign]
    page.choose("NPC")
    row = page.rows["NPC"]
    automatic = mapping.best_for(state.catalog, "NPC")
    assert row.clear_button.isEnabled() == (automatic != sprite.id)
    page.clear("NPC")
    assert page.starter.get("npc") == automatic or (automatic is None and "npc" not in page.starter)


def test_a_placeholder_choice_is_remembered_by_the_radio_buttons(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    player = page.rows["PLAYER"]
    player.placeholder_radio.click()
    assert "PLAYER" in page.placeholders and player.placeholder_radio.isChecked()
    assert page.validate(state) == []


def test_transparent_thumbnails_sit_on_a_checkerboard(qtbot) -> None:
    from rpggen.gui.pages.mapping_page import THUMB, checkerboard

    board = checkerboard(THUMB)
    image = board.toImage()
    assert image.pixelColor(0, 0) != image.pixelColor(8, 0)  # two shades
    page, _state = _page(qtbot, "basic16")
    pixmap = page.rows["GROUND"].thumb_label.pixmap()
    assert not pixmap.isNull() and pixmap.width() == THUMB


def test_a_tile_sheet_thumbnail_starts_at_the_first_filled_cell(tmp_path) -> None:
    from PIL import Image

    from rpggen.gui import thumbnails

    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    for x in range(32, 48):
        for y in range(0, 16):
            img.putpixel((x, y), (255, 0, 0, 255))  # the first filled cell is column 2, row 0
    path = tmp_path / "sheet.png"
    img.save(path)
    grid = {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}
    assert thumbnails.first_filled_cell(img, grid) == (2, 0)
    req = thumbnails.request_for(
        "x", path, {"usage": "tiles", "grid": grid}, size=48, cells=3, skip_empty=True
    )
    out = Image.open(__import__("io").BytesIO(thumbnails.render_thumbnail(req, 48)))
    assert out.getpixel((1, 1))[3] == 255  # starts on the red cell, not on emptiness


# ------------------------------------------------------------------------ scrolling (T12.01)


def _settle() -> None:
    """A scroll area needs a few turns of the event loop to lay its content out."""
    from PySide6.QtWidgets import QApplication

    for _ in range(3):
        QApplication.processEvents()


@pytest.mark.parametrize("archetype", ["turn_based", "arpg"])
def test_rows_keep_their_size_at_the_window_minimum(qtbot, archetype: str) -> None:
    from rpggen.gui.wizard import MIN_WINDOW

    page, _state = _page(qtbot, "basic16", archetype)
    # the page inside the window: minus the sidebar, the button bar and the margins
    page.resize(MIN_WINDOW[0] - 200, MIN_WINDOW[1] - 120)
    _settle()
    assert page.rows
    for widget in page.rows.values():
        assert widget.height() >= widget.minimumSizeHint().height(), widget.objectName()
        assert widget.choose_button.height() >= widget.choose_button.sizeHint().height()
    assert page.scroll_area.verticalScrollBar().maximum() > 0  # more rows than the window shows


def test_reveal_missing_scrolls_to_the_first_required_row_without_an_asset(qtbot) -> None:
    from PySide6.QtCore import QPoint

    page, state = _page(qtbot, "mixed")  # ground and items but no player
    page.resize(700, 320)
    _settle()
    row = page.rows["PLAYER"]
    viewport = page.scroll_area.viewport()

    def top() -> int:
        return row.mapTo(viewport, QPoint(0, 0)).y()

    assert top() + row.height() > viewport.height()  # below the fold
    page.reveal_missing(state)
    _settle()
    assert top() >= 0 and top() + row.height() <= viewport.height()
    assert row.choose_button.hasFocus()


# ------------------------------------------------------------------------ T12.36: the combo


def test_the_combo_offers_the_top_candidates_in_rank_order(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    row = page.rows["ITEM"]
    page.fill_candidates("ITEM")
    ids = page.candidate_ids("ITEM")
    ranked = [a.id for a in mapping.candidates(state.catalog, "ITEM")]
    current = page.selection_for("ITEM")
    offered = [i for i in ids if i not in (NONE_DATA, MORE_DATA)]
    expected = ([current] if current else []) + [i for i in ranked[:5] if i != current]
    assert offered == expected[: len(offered)] and len(offered) <= 6
    assert ids[-1] == MORE_DATA
    combo = row.asset_combo
    first_candidate = next(i for i in range(combo.count()) if combo.itemData(i) in ranked)
    assert "%" in combo.itemText(first_candidate)  # the confidence
    assert not combo.itemIcon(first_candidate).isNull()


def test_choosing_in_the_combo_assigns_and_can_be_undone(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    sprite = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "sprite")
    original_catalog = state.catalog
    page.fill_candidates("PLAYER")
    combo = page.rows["PLAYER"].asset_combo
    assert sprite.id in page.candidate_ids("PLAYER")
    combo.setCurrentIndex(combo.findData(sprite.id))
    page.on_combo("PLAYER")
    assert page.starter["player"] == sprite.id
    assert catalog.effective(state.catalog.asset(sprite.id))["role"] == "PLAYER"
    assert page.undo_button.isEnabled()
    assert page.undo()
    assert "player" not in page.starter and state.catalog is original_catalog
    assert not page.undo_button.isEnabled() and not page.undo()


def test_none_and_more_in_the_combo(qtbot) -> None:
    page, state = _page(qtbot, "basic16")
    assert page.starter["player"]
    page.fill_candidates("PLAYER")
    combo = page.rows["PLAYER"].asset_combo
    combo.setCurrentIndex(combo.findData(NONE_DATA))
    page.on_combo("PLAYER")
    assert "player" not in page.starter and page.rows["PLAYER"].status_label.text().startswith("✖")
    page.undo()
    assert page.starter["player"]
    asked: list[str] = []
    page.choose = lambda role: asked.append(role) or False  # type: ignore[method-assign]
    page.fill_candidates("PLAYER")
    combo.setCurrentIndex(combo.findData(MORE_DATA))
    page.on_combo("PLAYER")
    assert asked == ["PLAYER"]


def test_the_combo_is_reachable_by_keyboard(qtbot) -> None:
    page, _state = _page(qtbot, "basic16")
    combo = page.rows["PLAYER"].asset_combo
    assert combo.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert page.rows["PLAYER"].choose_button.isEnabled()  # More… and Choose… both open the picker


# ------------------------------------------------------------------------ the gallery and the audit (T13.05)


def _two_packs_state() -> WizardState:
    state = WizardState(
        pack_sources=[SYNTH / "mixed", SYNTH / "basic16"], target=None, archetype="turn_based"
    )
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return state


def test_the_gallery_groups_by_pack_and_keeps_the_rank_order(qtbot) -> None:
    state = _two_packs_state()
    dialog = AssetPickerDialog(state.catalog, "GROUND", page_resolver(state))
    qtbot.addWidget(dialog)
    dialog.resize(760, 520)
    dialog.show()
    ranked = [a.id for a in mapping.candidates(state.catalog, "GROUND")]
    groups = dialog.groups()
    assert [pack for pack, _ids in groups] == sorted({i.split(".")[0] for i in ranked})
    assert len(groups) == 2, "one header per pack"
    for pack, ids in groups:
        assert ids == [i for i in ranked if i.split(".")[0] == pack], "rank order inside a pack"
    assert sorted(i for _p, ids in groups for i in ids) == sorted(ranked), "only the candidates"
    # headers without buttons, thumbnails at the grid's size, the confidence in the tooltip
    assert dialog.grid.view.card_delegate.header_actions == ()
    assert dialog.grid.model.thumb_size == dialog.grid.view.card_delegate.thumb
    auto = next(a for a in mapping.candidates(state.catalog, "GROUND") if a.status != "CONFIRMED")
    row = dialog.grid.model.row_of(auto.id)
    tip = dialog.grid.model.index(row, 0).data(Qt.ItemDataRole.ToolTipRole)
    assert f"{round(auto.confidence * 100)}%" in tip
    # the search of the filter bar narrows it; a pack without a match loses its header
    dialog.grid.search.setText("ground32")
    assert [pack for pack, _ids in dialog.groups()] == ["mixed"]
    assert dialog.grid.visible_ids() == ["mixed.tiles.ground32"]
    # a double-click chooses
    index = dialog.grid.proxy.index(1, 0)  # row 0 is the header
    dialog.grid.select_ids(["mixed.tiles.ground32"])
    dialog.grid.view.doubleClicked.emit(index)
    assert dialog.picked == "mixed.tiles.ground32" and dialog.result() == 1


def test_choosing_in_the_gallery_is_the_same_undoable_edit_as_the_combo(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    sprite = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "sprite")
    original = state.catalog
    seen = []

    def pick(dialog) -> bool:
        seen.append(dialog)
        dialog.grid.select_ids([sprite.id])
        return dialog.picked == sprite.id

    page.run_picker = pick  # type: ignore[method-assign]
    page.fill_candidates("PLAYER")
    combo = page.rows["PLAYER"].asset_combo
    combo.setCurrentIndex(combo.findData(MORE_DATA))
    page.on_combo("PLAYER")  # More…
    assert len(seen) == 1 and isinstance(seen[0], AssetPickerDialog)
    assert page.starter["player"] == sprite.id
    assert catalog.effective(state.catalog.asset(sprite.id))["role"] == "PLAYER"
    assert page.undo() and "player" not in page.starter and state.catalog is original


def test_show_in_audit_selects_the_asset_and_back_returns_to_the_row(qtbot, tmp_path) -> None:
    from rpggen import dev
    from rpggen.gui.pages.audit_page import AuditPage
    from rpggen.gui.wizard import MainWindow, default_pages

    window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(1100, 720)
    window.show()
    mapping_page = next(p for p in window.pages if isinstance(p, MappingPage))
    audit = next(p for p in window.pages if isinstance(p, AuditPage))
    mapping_index = window.pages.index(mapping_page)
    window.show_page(window.pages.index(audit))  # visited, as in a real walk
    window.show_page(mapping_index)
    QApplication.processEvents()  # the rows made on entry are shown by the event loop
    role = next(r for r in mapping_page.rows if mapping_page.selection_for(r) is not None)
    asset_id = mapping_page.audit_asset(role)
    assert asset_id is not None
    row = mapping_page.rows[role]
    assert row.audit_button.isVisibleTo(mapping_page) and row.audit_button.toolTip()
    row.audit_button.click()
    assert window.current_page is audit
    assert audit.grid.selected_ids() == [asset_id]
    assert audit.detail is not None and audit.detail.asset_id == asset_id
    window.back_button.click()
    assert window.current_page is mapping_page, "not the page before the audit"
    again = mapping_page.rows[role].asset_combo  # the rows are made anew on entry
    assert window.focusWidget() is again
    # an ordinary Back from the audit still goes one page back
    window.show_page(window.pages.index(audit))
    window.back_button.click()
    assert window.current_index == window.pages.index(audit) - 1


def test_a_row_without_an_asset_has_no_audit_button(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    empty = next(r for r in page.rows if page.selection_for(r) is None)
    assert not page.rows[empty].audit_button.isVisibleTo(page)
    assert page.audit_asset(empty) is None and not page.show_in_audit(empty)


def test_a_custom_slot_is_added_and_removed_as_one_undo_step_each(qtbot) -> None:
    """T13.16: Add slot… and the row's remove button, both taken back by the page's Undo."""
    page, state = _page(qtbot, "audio_basic")
    section = page.sound_section
    section.edit_button.setChecked(True)
    assert not section.add_button.isHidden()
    fixed = len(section.rows)
    assert not section.remove_buttons, "the fixed slots cannot be removed"
    # a bad name and a duplicate are refused, with the reason under the rows
    assert not section.add_slot("Magic Sound")
    assert not section.add_error.isHidden() and "sfx_<name>" in section.add_error.text()
    assert not section.add_slot("sfx_hit")
    assert "already" in section.add_error.text()
    assert len(section.rows) == fixed and not page.undo_button.isEnabled()
    # the dialog's answer goes through the same check
    section.ask_name = lambda: "sfx_magic"  # type: ignore[method-assign]
    assert section.ask_new_slot()
    assert section.add_error.isHidden()
    assert list(section.rows)[-1] == "sfx_magic" and "sfx_magic" in section.remove_buttons
    assert section.findChild(type(section.add_button), "soundRemove_sfx_magic") is not None
    assert section.sounds["sfx_magic"] == ""
    assert not section.add_slot("sfx_magic"), "a duplicate"
    section.ask_name = lambda: None  # type: ignore[method-assign]
    assert not section.ask_new_slot(), "cancelled"
    # a sound for it
    hit = "audio_basic.sfx.hit"
    section.run_picker = lambda dialog: setattr(dialog, "picked", hit) or True  # type: ignore[method-assign]
    assert section.choose("sfx_magic")
    assert section.summary_label.text() == "3 music tracks, 5 sound effects assigned"
    page.leave(state)
    assert state.config.sounds["sfx_magic"] == hit
    assert state.config.to_json()["sounds"]["sfx_magic"] == hit
    # one Undo takes back the sound, the next one the slot
    assert page.undo()
    assert section.sounds["sfx_magic"] == ""
    assert page.undo()
    assert "sfx_magic" not in section.sounds and len(section.rows) == fixed
    assert not page.undo_button.isEnabled()
    # removing is one step too
    assert section.add_slot("music_cave")
    section.remove_buttons["music_cave"].click()
    assert "music_cave" not in section.sounds and "music_cave" not in section.rows
    assert not section.remove_slot("sfx_hit"), "a fixed slot stays"
    assert page.undo()
    assert "music_cave" in section.rows and section.sounds["music_cave"] == ""
    # the slot survives leaving and coming back
    page.leave(state)
    page.enter(state)
    assert "music_cave" in page.sound_section.rows


# ------------------------------------------------------------------ T17.16: the isometric view


def _two_packs(qtbot, packs: tuple[str, ...], archetype: str, projection: str):  # noqa: ANN001, ANN202
    sources = [SYNTH / pack for pack in packs]
    state = WizardState(pack_sources=sources, target=None, archetype=archetype)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    refs = [
        config.PackRef(opened.pack_id, str(source), "0" * 64, "folder")
        for opened, source in zip(state.opened_packs, sources, strict=True)
    ]
    state.config = config.default_for("T", refs, archetype=archetype)
    state.config.projection = projection
    page = MappingPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def _offered(page: MappingPage, role: str) -> list[str]:
    page.fill_candidates(role)
    return [i for i in page.candidate_ids(role) if i not in (NONE_DATA, MORE_DATA)]


def test_an_isometric_project_is_offered_only_what_fits_its_view(qtbot) -> None:
    packs = ("basic16", "iso_tiles")
    flat, state = _two_packs(qtbot, packs, "turn_based", "top_down")
    cat = state.catalog

    def isometric(ident: str) -> bool:
        asset = cat.asset(ident)
        return asset is not None and catalog.effective(asset).get("projection") == "isometric"

    assert flat.projection == "top_down"
    ground = _offered(flat, "GROUND")
    assert ground and not any(isometric(i) for i in ground), "squares for a map seen from above"
    assert flat.selection_for("GROUND").startswith("basic16.")
    iso, state = _two_packs(qtbot, packs, "turn_based", "isometric")
    assert iso.projection == "isometric"
    ground = _offered(iso, "GROUND")
    assert ground and all(isometric(i) for i in ground), "diamonds for an isometric one"
    assert iso.selection_for("GROUND").startswith("iso_tiles.")
    assert iso.selection_for("BUILDING").startswith("iso_tiles."), "the house drawn at the angle"
    # a hero drawn for a top-down game walks an isometric map: the packs of diamonds have none
    assert iso.selection_for("PLAYER") == flat.selection_for("PLAYER")
    assert iso.selection_for("PLAYER").startswith("basic16.")
    iso.leave(state)
    assert state.config.starter["ground"].startswith("iso_tiles.")
    assert iso.validate(state) == [] and iso.status(state) == ("ok", 0)
    # More...: the gallery of an isometric project has the same candidates
    dialog = AssetPickerDialog(
        state.catalog, "GROUND", lambda asset: None, iso, projection="isometric"
    )
    qtbot.addWidget(dialog)
    assert dialog.candidates and all(isometric(a.id) for a in dialog.candidates)
    seen: list[AssetPickerDialog] = []
    iso.run_picker = lambda dialog: bool(seen.append(dialog))  # type: ignore[method-assign]
    assert not iso.choose("GROUND")
    assert [a.id for a in seen[0].candidates] == [a.id for a in dialog.candidates]


def test_a_car_drawn_from_above_is_said_to_look_flat_on_an_isometric_track(qtbot) -> None:
    from rpggen.core import options

    page, state = _two_packs(qtbot, ("racer", "iso_tiles"), "racing", "isometric")
    row = page.rows["VEHICLE"]
    car = page.selection_for("VEHICLE")
    assert car is not None and car.startswith("racer."), "sixteen headings, drawn from above"
    assert not row.note_label.isHidden()
    assert row.note_label.text() == options.FLAT_VEHICLE_NOTE
    assert row.note_label.text() == "drawn from above: it will look flat on an isometric track"
    assert "16 headings" in row.asset_combo.currentText()
    for other in page.rows.values():
        assert other is row or other.note_label.isHidden()
    # the same car on a track seen from above is what it always was
    flat, _state = _two_packs(qtbot, ("racer", "iso_tiles"), "racing", "top_down")
    assert flat.rows["VEHICLE"].note_label.isHidden()
    # ... and a car drawn at the angle (eight turns of it) needs no note
    own, state = _two_packs(qtbot, ("iso_miniature",), "racing", "isometric")
    car = own.selection_for("VEHICLE")
    assert car is not None and catalog.effective(state.catalog.asset(car))["headings"] == 8
    assert own.rows["VEHICLE"].note_label.isHidden()
    assert not options.flat_vehicle(state.catalog, car, "racing", "isometric")
    assert not options.flat_vehicle(state.catalog, None, "racing", "isometric")
    assert not options.flat_vehicle(None, "x", "racing", "isometric")
