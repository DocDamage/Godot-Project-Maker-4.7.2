"""T14.10: the wizard for the third archetype: the Metroidvania card and its hints, the roles of
the Mapping page, the *Starter world* options with their bound and preview, the bindings rows and
the summary. The session runs with the feature flag on (the gate of 1.2 flips the default)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import features
from rpggen.core import archive, catalog, config, inventory, options, room_plan
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages import archetype_page
from rpggen.gui.pages.archetype_page import ArchetypePage
from rpggen.gui.pages.mapping_page import MappingPage
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.state import WizardState

REPO = Path(__file__).resolve().parents[2]
SIDE = REPO / "sample_pack_side"
SYNTH = REPO / "test_packs" / "synthetic"
REF = config.PackRef("x", "C:/x", "0" * 64, "folder")


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch) -> None:
    monkeypatch.setattr(features, "METROIDVANIA_AVAILABLE", True)


def _catalog(pack: Path) -> catalog.Catalog:
    opened = archive.open_pack(pack, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    return cat


def _side_state() -> WizardState:
    from rpggen.core import profiles

    profiles.install_profile(SIDE / "sample_side.rpgprofile.json")
    state = WizardState(pack_sources=[SIDE], archetype="metroidvania")
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef("sample_pack_side", str(SIDE), "0" * 64, "folder")
    state.config = config.default_for("Cave", [ref], archetype="metroidvania")
    return state


def _archetype_page(qtbot, state: WizardState) -> ArchetypePage:
    page = ArchetypePage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page


# ---------------------------------------------------------------- the card


def test_the_card_is_disabled_with_a_tooltip_while_the_flag_is_off(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(features, "METROIDVANIA_AVAILABLE", False)
    state = WizardState(archetype="metroidvania")
    page = _archetype_page(qtbot, state)
    card = page.metroidvania_card
    assert not card.isEnabled()
    assert card.toolTip() == "Coming in a later version"
    assert page.selected() == "turn_based", "a state that asks for it falls back"
    assert page.view_hint.isHidden()


def test_the_card_can_be_chosen_with_the_flag_on(qtbot) -> None:
    state = WizardState(config=config.default_for("T", [REF]))
    page = _archetype_page(qtbot, state)
    card = page.metroidvania_card
    assert card.isEnabled() and card.toolTip() == ""
    assert list(page.cards)[:3] == ["turn_based", "arpg", "metroidvania"]  # six since T16.16
    card.click()
    assert page.selected() == "metroidvania"
    assert not card.check_label.isHidden()
    page.leave(state)
    assert state.archetype == "metroidvania"
    assert state.config.archetype == "metroidvania"
    assert state.config.input == config.default_input("metroidvania"), "untouched bindings follow"
    assert {"jump", "dash", "attack", "down"} <= set(state.config.input)
    # coming back, the card is still the chosen one
    page.enter(state)
    assert page.selected() == "metroidvania"


def test_a_side_view_pack_suggests_the_card(qtbot) -> None:
    state = _side_state()
    assert archetype_page.pack_view_of(state.catalog) == "side"
    state.archetype = "turn_based"
    page = _archetype_page(qtbot, state)
    assert not page.view_hint.isHidden(), "shown whatever card is chosen"
    assert page.view_hint.text() == archetype_page.SIDE_BOTH_HINT, "the run and gun fits too"
    assert page.metroidvania_card.isEnabled()
    page.metroidvania_card.click()
    assert page.air_warning.isHidden(), "the sample hero has jump and fall animations"
    assert page.warning_label.isHidden(), "the swing warning is the action RPG's"


def test_a_top_down_pack_gets_the_hint_and_the_air_warning_without_being_locked(qtbot) -> None:
    state = WizardState(catalog=_catalog(SYNTH / "basic16"))
    assert archetype_page.pack_view_of(state.catalog) == "top"
    assert archetype_page.missing_air(state.catalog) == ["jump", "fall"]
    page = _archetype_page(qtbot, state)
    assert page.view_hint.isHidden() and page.air_warning.isHidden(), (
        "nothing while another is chosen"
    )
    card = page.metroidvania_card
    assert card.isEnabled(), "a top-down pack does not disable the card"
    card.click()
    assert not page.view_hint.isHidden()
    assert "walk-down animations" in page.view_hint.text()
    assert not page.air_warning.isHidden()
    assert "idle frame" in page.air_warning.text()
    page.turn_card.click()
    assert page.view_hint.isHidden() and page.air_warning.isHidden()
    assert archetype_page.pack_view_of(None) == "" and archetype_page.missing_air(None) == []


def test_the_card_is_drawn_with_the_players_jump_frame(qtbot) -> None:
    from PIL import Image

    state = _side_state()
    page = _archetype_page(qtbot, state)
    art = page.metroidvania_card.mock.art
    assert art is not None and art.side_player is not None
    with Image.open(SIDE / "characters" / "hero_jump.png") as strip:
        frame = strip.convert("RGBA").crop((0, 0, 24, 24))
    colors = {
        frame.getpixel((x, y))[:3]
        for x in range(frame.width)
        for y in range(frame.height)
        if frame.getpixel((x, y))[3] == 255
    }
    mock = page.metroidvania_card.mock
    mock.resize(300, 180)
    image = mock.grab().toImage()
    seen = {
        image.pixelColor(x, y).getRgb()[:3]
        for x in range(image.width())
        for y in range(image.height())
    }
    assert colors & seen, "no pixel of the hero's jump frame on the card"
    # a top-down hero has no jump or run animation: the card shows its first frame
    top = WizardState(catalog=_catalog(SYNTH / "basic16"))
    plain = _archetype_page(qtbot, top)
    art = plain.metroidvania_card.mock.art
    assert art is None or art.side_player is None
    plain.metroidvania_card.mock.grab()  # and the plain drawing paints without raising
    empty = _archetype_page(qtbot, WizardState())
    empty.metroidvania_card.mock.grab()


def test_a_long_flow_wraps_instead_of_squeezing_its_steps(qtbot) -> None:
    diagram = archetype_page.FlowDiagram(
        ["Run", "Jump", "Find an ability", "Open the way", "Explore"]
    )
    qtbot.addWidget(diagram)
    assert len(diagram.rows_for(2000)) == 1
    narrow = diagram.rows_for(240)
    assert len(narrow) >= 2 and [s for row in narrow for s in row] == diagram.steps
    assert diagram.height_for(240) > diagram.height_for(2000)
    diagram.resize(240, 44)
    diagram.show()
    assert diagram.minimumHeight() >= diagram.height_for(240)
    diagram.grab()


# ---------------------------------------------------------------- mapping and sounds


def test_the_mapping_page_lists_the_roles_of_the_archetype(qtbot) -> None:
    state = _side_state()
    page = MappingPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    assert set(page.rows) == {
        "PLAYER", "GROUND", "BACKGROUND", "DECORATION", "ENEMY", "BOSS", "ITEM", "NPC", "UI",
        "PORTRAIT",
    }  # fmt: skip
    assert "BUILDING" not in page.rows and "WALL" not in page.rows
    assert page.rows["BOSS"].used_label.text() == "Used for the guardian"
    assert page.rows["GROUND"].used_label.text() == "Used for the floors and walls of every room"
    assert page.rows["BACKGROUND"].used_label.text().endswith("parallax layers behind a room")
    assert page.validate(state) == []
    # the four sounds of the archetype are fixed slots, filled by name
    section = page.sound_section
    keys = section.slot_keys()
    assert keys[-4:] == ["sfx_jump", "sfx_land", "sfx_dash", "sfx_ability"]
    assert section.sounds["sfx_jump"].endswith("jump")
    assert section.sounds["sfx_land"].endswith("land")
    assert section.sounds["sfx_dash"].endswith("dash")
    assert section.sounds["sfx_ability"].endswith("powerup")
    assert "sfx_jump" not in section.remove_buttons, "a fixed slot cannot be removed"
    page.leave(state)
    assert state.config.sounds["sfx_ability"].endswith("powerup")
    assert ".boss.guardian" in state.config.starter["boss"]


# ---------------------------------------------------------------- options


def _options_page(qtbot, state: WizardState | None = None) -> tuple[OptionsPage, WizardState]:
    state = state or WizardState(
        config=config.default_for("T", [REF], archetype="metroidvania"), archetype="metroidvania"
    )
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def test_the_starter_world_replaces_the_starter_map(qtbot) -> None:
    page, state = _options_page(qtbot)
    before = state.config.to_json()
    assert page.model.is_side
    assert page.starter_box.isHidden() and page.imported_box.isHidden()
    box = page.world_box
    assert not box.isHidden() and box.title() == "Starter world"
    assert box.rooms.value() == 6
    assert (box.room_width.value(), box.room_height.value()) == (40, 23)
    assert box.chosen_abilities() == ["double_jump", "dash"]
    assert list(box.abilities) == list(room_plan.ABILITIES), "the plan's order"
    assert (box.enemies.value(), box.pickups.value()) == (2, 4)
    assert page.feature_boxes["navigation"].isHidden(), "rooms have no pathfinding"
    assert not page.feature_boxes["dialogue"].isHidden()
    # the layer list is the layers of a room, and fixed
    assert page.layers() == [
        "Background",
        "Ground",
        "Platforms",
        "Hazards",
        "Decoration",
        "Foreground",
    ]
    assert not page.add_layer_button.isEnabled() and not page.remove_layer_button.isEnabled()
    # the preview is the side-view one: a picture, and the plan in words
    assert box.plan is not None and len(box.plan["list"]) == 6
    assert not box.preview.pixmap().isNull()
    assert box.summary.text() == "6 rooms, 2 abilities, a guardian"
    assert page.summary.archetype_label.text() == "<b>Metroidvania</b>"
    assert page.summary.maps_label.text() == "World: 6 rooms, 2 abilities, a guardian"
    assert "Navigation" not in [chip.text() for chip in page.summary.chips]
    assert page.validate(state) == []
    page.leave(state)
    assert state.config.to_json() == before, "the defaults are not written out"
    assert state.config.map_layers == config.default_for("T", [REF]).map_layers


def test_the_rooms_can_never_be_fewer_than_the_abilities_need(qtbot) -> None:
    page, state = _options_page(qtbot)
    box = page.world_box
    assert box.rooms.minimum() == 5 and "2 abilities need at least 5 rooms" in box.bound.text()
    box.rooms.setValue(5)
    box.abilities["wall_jump"].setChecked(True)
    assert box.rooms.minimum() == 6 and box.rooms.value() == 6, "raised with the bound, live"
    box.abilities["high_jump"].setChecked(True)
    box.abilities["break_blocks"].setChecked(True)
    assert box.rooms.minimum() == 8 and box.rooms.value() == 8
    assert "5 abilities need at least 8 rooms" in box.bound.text()
    assert page.validate(state) == []
    assert box.plan is not None and len(box.plan["list"]) == 8
    assert page.summary.maps_label.text() == "World: 8 rooms, 5 abilities, a guardian"
    for check in box.abilities.values():
        check.setChecked(False)
    assert box.rooms.minimum() == 5 and box.rooms.value() == 8, "lowering the bound keeps the value"
    assert "0 abilities need at least 5 rooms" in box.bound.text()
    assert page.summary.maps_label.text() == "World: 8 rooms, 0 abilities"
    box.abilities["dash"].setChecked(True)
    assert "1 ability needs at least 5 rooms" in box.bound.text()
    page.leave(state)
    assert state.config.starter_map == {"rooms": 8, "abilities": ["dash"]}
    # the config with the new keys survives a round trip, and the schema holds the bound too
    again = config.GeneratorConfig.from_json(state.config.to_json())
    assert again.to_json() == state.config.to_json()
    assert again.starter_map_options() == {
        **room_plan.defaults(),
        "rooms": 8,
        "abilities": ["dash"],
    }
    assert options.config_errors(again) == []
    again.starter_map = {"rooms": 5, "abilities": list(room_plan.ABILITIES)}
    with pytest.raises(room_plan.RoomPlanError):
        room_plan.normalized(again.starter_map_options())


def test_the_other_world_options_and_reset(qtbot) -> None:
    page, state = _options_page(qtbot)
    box = page.world_box
    box.room_width.setValue(48)
    box.room_height.setValue(30)
    box.enemies.setValue(0)
    box.pickups.setValue(9)
    assert box.plan is not None and box.plan["room_size"] == [48, 30]
    first = box.plan
    page.seed_box.setValue(777)
    assert box.plan is not first and box.plan != first, "another seed, another world"
    page.leave(state)
    assert state.config.starter_map == {"room_size": [48, 30], "enemies": 0, "pickups": 9}
    assert state.config.seed == 777
    page.world_box.reset.click()
    assert box.room_width.value() == 40 and box.pickups.value() == 4
    page.leave(state)
    assert state.config.starter_map == {}


def test_added_rooms_are_rows_of_the_options(qtbot) -> None:
    page, state = _options_page(qtbot)
    box = page.world_box
    assert box.added.rowCount() == 0 and not box.remove_room.isEnabled()
    assert box.add_row()
    assert box.added_rows() == [{"name": "Room 7", "join": "Room 6"}]
    assert box.plan is not None and [r["name"] for r in box.plan["list"]][-1] == "Room 7"
    assert box.summary.text().startswith("7 rooms")
    assert page.summary.maps_label.text() == "World: 7 rooms, 2 abilities, a guardian"
    assert box.add_row("Annex", "Room 1")
    page.leave(state)
    assert state.config.starter_map == {
        "added_rooms": [{"name": "Room 7", "join": "Room 6"}, {"name": "Annex", "join": "Room 1"}]
    }
    assert box.remove_row() and box.added.rowCount() == 1
    page.leave(state)
    assert state.config.starter_map == {"added_rooms": [{"name": "Room 7", "join": "Room 6"}]}


def test_a_world_that_exists_keeps_its_options_but_takes_a_new_room(qtbot, tmp_path: Path) -> None:
    from rpggen.core import world_plan

    target = tmp_path / "game"
    plan = room_plan.world(room_plan.plan(room_plan.defaults(), 12345), 12345)
    (target / "rpggen").mkdir(parents=True)
    world_plan.save(target, plan)
    first = target / plan["rooms"]["list"][0]["map"]
    first.parent.mkdir(parents=True)
    first.write_text("[gd_scene format=3]\n", encoding="utf-8")
    assert room_plan.exists(target)
    cfg = config.default_for("T", [REF], archetype="metroidvania")
    cfg.starter_map = {"rooms": 7}
    state = WizardState(config=cfg, archetype="metroidvania", target=target, regenerating=True)
    page, _state = _options_page(qtbot, state)
    box = page.world_box
    assert page.model.starter_locked
    assert not box.note.isHidden() and "rooms that exist are kept" in box.note.text()
    assert not box.rooms.isEnabled() and not box.abilities["dash"].isEnabled()
    assert not box.reset.isEnabled()
    assert box.add_room.isEnabled(), "a room can still be added"
    assert box.plan is not None and len(box.plan["list"]) == 6, "the stored plan, not the options'"
    box.rooms.setValue(9)  # even if a widget changed, the options of the world stay
    assert box.add_row("Annex", "Room 6")
    assert [r["id"] for r in box.plan["list"]][-1] == "room_annex"
    page.leave(state)
    assert state.config.starter_map == {
        "rooms": 7,
        "added_rooms": [{"name": "Annex", "join": "Room 6"}],
    }


def test_the_bindings_table_has_the_actions_of_the_archetype(qtbot) -> None:
    page, state = _options_page(qtbot)
    table = page.input_table
    actions = [table.item(row, 0).text() for row in range(table.rowCount())]
    assert actions == list(config.default_input("metroidvania"))
    for action in ("jump", "dash", "attack", "down"):
        assert action in actions
    assert "dodge" not in actions and "secondary_attack" not in actions
    row = actions.index("jump")
    assert table.item(row, 1).text() == "Space, Z"
    table.item(row, 1).setText("Space, W")
    page.leave(state)
    assert state.config.input["jump"]["keys"] == ["Space", "W"]
    assert state.config.input["interact"]["keys"] == ["E", "Up"], "Space jumps here"


def test_a_factory_preset_applies_without_navigation(qtbot) -> None:
    page, state = _options_page(qtbot)
    preset = options.default_preset("metroidvania")
    preset["features"] = {**preset["features"], "navigation": True}
    preset["map_layers"] = ["Ground", "Fog"]
    cfg = options.apply_preset(state.config, preset)
    assert cfg.features["navigation"] is False
    assert cfg.map_layers == state.config.map_layers, "the layers of a room are fixed"
    # the top-down archetypes take both, as before
    plain = options.apply_preset(config.default_for("T", [REF]), preset | {"input": {}})
    assert plain.features["navigation"] is True and plain.map_layers == ["Ground", "Fog"]
    for key in ("minimal", "everything"):
        built_in = options.builtin_preset(key, "metroidvania")
        assert built_in is not None
        assert options.apply_preset(state.config, built_in).features["navigation"] is False


def test_the_summary_of_the_options_in_words() -> None:
    feats = config.default_features() | {"navigation": True}
    summary = options.summarize("metroidvania", feats, room_plan.defaults(), 16, (640, 360))
    assert summary.world == "6 rooms, 2 abilities, a guardian"
    assert summary.maps == []
    assert "Navigation" not in " ".join(summary.systems)
    broken = options.summarize(
        "metroidvania", feats, {"rooms": 5, "abilities": list(room_plan.ABILITIES)}, 16, (640, 360)
    )
    assert broken.world == ""
    top = options.summarize("turn_based", feats, config.starter_map_defaults(), 16, (640, 360))
    assert top.world == "" and top.maps[0] == "Starter map"


def test_another_archetype_still_gets_the_starter_map(qtbot) -> None:
    state = WizardState(config=config.default_for("T", [REF], archetype="arpg"), archetype="arpg")
    page, _state = _options_page(qtbot, state)
    assert not page.model.is_side
    assert not page.starter_box.isHidden() and page.world_box.isHidden()
    assert not page.feature_boxes["navigation"].isHidden()
    assert page.add_layer_button.isEnabled()
    # and the same page shows the world when the state turns into a metroidvania
    side = WizardState(
        config=config.default_for("T", [REF], archetype="metroidvania"), archetype="metroidvania"
    )
    page.enter(side)
    assert page.starter_box.isHidden() and not page.world_box.isHidden()
    page.enter(state)
    assert not page.starter_box.isHidden() and page.world_box.isHidden()
    assert page.layers() == config.default_for("T", [REF]).map_layers
