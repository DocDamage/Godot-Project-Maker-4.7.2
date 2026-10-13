from __future__ import annotations

from pathlib import Path

from rpggen import features
from rpggen.core import archive, catalog, config, inventory
from rpggen.gui.pages.archetype_page import ArchetypePage, has_attack_animation
from rpggen.gui.state import WizardState

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _catalog(pack: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


def _page(qtbot, state):
    page = ArchetypePage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page


def test_turn_based_is_the_default(qtbot) -> None:
    state = WizardState()
    page = _page(qtbot, state)
    assert page.turn_card.isChecked() and not page.arpg_card.isChecked()
    assert page.validate(state) == []
    page.leave(state)
    assert state.archetype == "turn_based"


def test_arpg_is_available_since_m9(qtbot) -> None:
    assert features.ARPG_AVAILABLE is True
    page = _page(qtbot, WizardState())
    assert page.arpg_card.isEnabled()
    assert page.arpg_card.toolTip() == ""


def test_arpg_selection_and_warning(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(features, "ARPG_AVAILABLE", True)
    state = WizardState(catalog=_catalog("basic16"))
    page = _page(qtbot, state)
    assert page.arpg_card.isEnabled()
    page.arpg_card.click()
    assert page.selected() == "arpg"
    assert not page.warning_label.isHidden()
    assert "generic swing effect" in page.warning_label.text()
    page.turn_card.click()
    assert page.warning_label.isHidden()
    page.arpg_card.click()
    page.leave(state)
    assert state.archetype == "arpg"


def test_attack_animations_hide_the_warning(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(features, "ARPG_AVAILABLE", True)
    cat = _catalog("basic16")
    assert not has_attack_animation(cat)
    hero = cat.asset("basic16.characters.hero")
    hero.overrides = {"animations": {"attack_down": {"frames": [[0, 0]], "fps": 8, "loop": False}}}
    assert has_attack_animation(cat)
    state = WizardState(catalog=cat, archetype="arpg")
    page = _page(qtbot, state)
    assert page.arpg_card.isChecked() and page.warning_label.isHidden()


def test_changing_archetype_updates_untouched_input_map(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(features, "ARPG_AVAILABLE", True)
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    state = WizardState(config=config.default_for("T", [ref]))
    page = _page(qtbot, state)
    page.arpg_card.click()
    page.leave(state)
    assert state.config.archetype == "arpg"
    assert state.config.input == config.default_input("arpg")


def _sample_state() -> WizardState:
    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers

    sample = Path(__file__).resolve().parents[2] / "sample_pack"
    state = WizardState(pack_sources=[sample])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return state


def test_the_cards_are_drawn_with_the_packs_art(qtbot) -> None:
    from PySide6.QtGui import QImage

    from rpggen.core import mapping
    from rpggen.gui import thumbnails
    from rpggen.gui.pages.audit_page import make_resolver

    state = _sample_state()
    page = _page(qtbot, state)
    hero_id = mapping.best_for(state.catalog, "PLAYER")
    hero = state.catalog.asset(hero_id)
    frame = thumbnails.first_frame_image(
        make_resolver(state)(hero), catalog.effective(hero)
    ).convert("RGBA")
    colors = {
        frame.getpixel((x, y))[:3]
        for x in range(frame.width)
        for y in range(frame.height)
        if frame.getpixel((x, y))[3] == 255
    }
    for card in (page.turn_card, page.arpg_card):
        assert card.mock.art is not None and card.mock.art.enemy is not None
        card.mock.resize(360, 200)
        image: QImage = card.mock.grab().toImage()
        seen = {
            image.pixelColor(x, y).getRgb()[:3]
            for x in range(image.width())
            for y in range(image.height())
        }
        assert colors & seen, f"{card.key}: no pixel of the hero sprite on the card"
    again = page.turn_card.mock.art
    page.enter(state)  # the same catalog: nothing is built again
    assert page.turn_card.mock.art is again


def test_without_a_catalog_the_cards_keep_their_drawing(qtbot) -> None:
    page = _page(qtbot, WizardState())
    assert page.turn_card.mock.art is None and page.arpg_card.mock.art is None
    page.turn_card.mock.grab()  # paints today's drawing without raising
    no_player = WizardState(catalog=_catalog("basic16"))
    page.enter(no_player)
    assert page.turn_card.mock.art is None or page.turn_card.mock.art.player is not None


# ---------------------------------------------------------------- six cards (T16.16)

ARCADE = ("shmup", "run_and_gun", "racing")
FLOWS = {
    "shmup": ["Fly", "Shoot", "Power up", "Boss"],
    "run_and_gun": ["Run", "Aim", "Shoot", "Boss"],
    "racing": ["Drive", "Overtake", "Lap", "Podium"],
    "farm": ["Till", "Plant", "Water", "Harvest", "Sell"],
}


def _arcade_on(monkeypatch, on: bool = True) -> None:
    for flag in ("SHMUP_AVAILABLE", "RUN_AND_GUN_AVAILABLE", "RACING_AVAILABLE"):
        monkeypatch.setattr(features, flag, on)


def test_the_three_arcade_kinds_are_on_since_the_gate_of_1_4() -> None:
    assert features.SHMUP_AVAILABLE and features.RUN_AND_GUN_AVAILABLE
    assert features.RACING_AVAILABLE


def test_there_are_seven_cards_and_a_kind_behind_its_flag_cannot_be_chosen(
    qtbot, monkeypatch
) -> None:
    _arcade_on(monkeypatch, False)
    monkeypatch.setattr(features, "FARM_AVAILABLE", False)
    state = WizardState(archetype="racing")
    page = _page(qtbot, state)
    assert list(page.cards) == ["turn_based", "arpg", "metroidvania", *ARCADE, "farm"]
    for key in (*ARCADE, "farm"):
        card = page.cards[key]
        assert not card.isEnabled() and card.toolTip() == "Coming in a later version"
        assert card.flow.steps == FLOWS[key]
    assert page.selected() == "turn_based", "a state that asks for a kind that is off falls back"
    assert page.view_hint.isHidden()


def test_each_arcade_kind_can_be_chosen_with_its_flag_on(qtbot, monkeypatch) -> None:
    _arcade_on(monkeypatch)
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    for key in ARCADE:
        state = WizardState(config=config.default_for("T", [ref], archetype="metroidvania"))
        state.archetype = "metroidvania"
        state.config.starter_map = {"rooms": 8}  # an option of the kind that is left
        page = _page(qtbot, state)
        card = page.cards[key]
        assert card.isEnabled() and card.toolTip() == ""
        card.click()
        assert page.selected() == key and not card.check_label.isHidden()
        page.leave(state)
        assert state.archetype == key and state.config.archetype == key
        assert state.config.input == config.default_input(key), "untouched bindings follow"
        assert state.config.features == config.default_features(key), "and untouched features"
        assert state.config.starter_map == {}, "the rooms are no option of this kind"
        assert state.config.to_json()["archetype"] == key
        page.enter(state)
        assert page.selected() == key, "coming back, the card is still the chosen one"


def test_seven_cards_in_rows_of_four_or_three_and_a_narrow_window_has_a_column(
    qtbot, monkeypatch
) -> None:
    """T17.16: rows of four from 1280 px on (two rows), rows of three below that (two rows in
    view, the third scrolls), and the column of a narrow window."""
    from rpggen.gui.pages import archetype_page

    _arcade_on(monkeypatch)
    monkeypatch.setattr(features, "FARM_AVAILABLE", True)
    page = _page(qtbot, WizardState())
    cards = list(page.cards.values())
    assert len(cards) == 7
    grid = page.cards_grid
    for (width, height), columns in (((1100, 620), 3), ((1400, 1000), 4), ((1280, 720), 4)):
        page.resize(width, height)
        qtbot.wait(20)
        assert page.in_grid and page.columns == columns
        places = [grid.getItemPosition(grid.indexOf(card))[:2] for card in cards]
        assert places == [(index // columns, index % columns) for index in range(7)]
        for card in cards:
            assert card.shape == "grid"
            assert card.mock.height() <= archetype_page.MOCK_GRID_HEIGHT
            assert card.height() >= card.minimumSizeHint().height(), f"{card.key} is squeezed"
            assert card.width() >= card.minimumWidth(), f"{card.key} is too narrow"
            assert card.mock.y() > card.body_label.y(), "the drawing is under the text"
        room = page.cards_scroll.viewport().height()
        if columns == 4:  # two rows: everything is in view
            assert page.cards_box.height() <= room
        else:  # three rows: two fill the room where two fit, and the third scrolls
            gap = grid.verticalSpacing()
            assert page.cards_box.height() > room
            if page._fit(page._row_needs(3), room):
                assert cards[6].geometry().top() == room + gap, "two rows fill the room"
                assert cards[5].geometry().bottom() < room, "the second row is whole"
            assert cards[6].geometry().top() >= room, "the third row is below the fold"
        # (that two whole rows are in view at 720 px is the layout test's, with a real font)
    # whether two rows of whole cards fit is measured on the cards: a large window has room
    # for the lists, and one that is as wide but lower leaves them out again
    page.resize(2000, 1400)
    qtbot.wait(20)
    assert cards[0].bullet_label.isHidden() is False and page.columns == 4
    assert page.cards_box.height() <= page.cards_scroll.viewport().height()
    page.resize(2000, 700)
    qtbot.wait(20)
    assert cards[0].bullet_label.isHidden()
    page.resize(1100, 620)
    qtbot.wait(20)
    assert cards[0].bullet_label.isHidden() and cards[0].controls_label.isHidden()
    # the chosen card of the third row is brought into view, its row whole
    state = WizardState(archetype="farm")
    page.enter(state)
    qtbot.wait(20)
    bar = page.cards_scroll.verticalScrollBar()
    assert page.selected() == "farm" and bar.value() > 0
    farm = cards[6].geometry()
    assert farm.top() >= bar.value()
    assert farm.bottom() <= bar.value() + page.cards_scroll.viewport().height()
    page.enter(WizardState())

    page.resize(828, 420)  # the page of a window of the minimum size
    qtbot.wait(20)
    assert not page.in_grid and page.columns == 1
    places = [grid.getItemPosition(grid.indexOf(card))[:2] for card in cards]
    assert places == [(row, 0) for row in range(7)]
    for card in cards:
        assert card.shape == "row"
        assert card.mock.size().toTuple() == archetype_page.MOCK_ROW_SIZE
        assert card.mock.x() < card.body_label.x(), "the drawing is at the left"
        assert not card.bullet_label.isHidden() and not card.controls_label.isHidden()
        assert card.height() >= card.minimumSizeHint().height(), f"{card.key} is squeezed"
        assert card.width() <= page.cards_scroll.viewport().width()
    # the column scrolls: it is higher than the room it has, and the chosen card is brought in
    assert page.cards_box.height() > page.cards_scroll.viewport().height()
    state = WizardState(archetype="racing")
    page.enter(state)
    assert page.selected() == "racing"
    qtbot.wait(20)
    assert page.cards_scroll.verticalScrollBar().value() > 0


def test_the_new_cards_have_their_drawings(qtbot, monkeypatch) -> None:
    from PySide6.QtGui import QImage

    from rpggen.gui.pages.archetype_page import MockScreen

    _arcade_on(monkeypatch)
    page = _page(qtbot, WizardState())
    seen: dict[str, set] = {}
    for key in ARCADE:
        mock = page.cards[key].mock
        assert mock.art is None
        mock.setFixedSize(320, 160)
        image: QImage = mock.grab().toImage()
        seen[key] = {
            image.pixelColor(x, y).getRgb()[:3]
            for x in range(0, image.width(), 2)
            for y in range(0, image.height(), 2)
        }
        assert MockScreen.BACKGROUNDS[key].getRgb()[:3] in seen[key]
    assert (70, 70, 78) in seen["racing"], "the road"
    assert (220, 60, 60) in seen["racing"], "the car in the bend"
    assert (96, 160, 232) in seen["shmup"], "the ship"
    assert (250, 224, 96) in seen["shmup"] and (250, 224, 96) in seen["run_and_gun"], "the shots"
    # with the art of a pack the ship and the soldier are its player
    state = _sample_state()
    page.enter(state)
    for key in ("shmup", "run_and_gun"):
        mock = page.cards[key].mock
        assert mock.art is not None
        mock.grab()


def test_a_pack_made_for_a_kind_points_at_its_card(qtbot, monkeypatch) -> None:
    from rpggen.gui.pages import archetype_page

    racer, shooter, gunner = (_catalog(name) for name in ("racer", "shooter", "gunner"))
    assert archetype_page.pack_kind_of(racer) == "racing"
    assert archetype_page.pack_kind_of(shooter) == "shmup"
    assert archetype_page.pack_kind_of(gunner) == "" and archetype_page.pack_kind_of(None) == ""
    _arcade_on(monkeypatch, False)
    off = _page(qtbot, WizardState(catalog=racer))
    assert off.view_hint.isHidden(), "the card cannot be chosen: nothing points at it"
    _arcade_on(monkeypatch)
    for cat, text in ((racer, archetype_page.RACING_HINT), (shooter, archetype_page.SHMUP_HINT)):
        page = _page(qtbot, WizardState(catalog=cat))
        assert not page.view_hint.isHidden() and page.view_hint.text() == text
    side = _page(qtbot, WizardState(catalog=gunner))
    assert side.view_hint.text() == archetype_page.SIDE_BOTH_HINT
    side.run_and_gun_card.click()
    # ASSET-030 is the run and gun's too: the soldier of the pack jumps but has no fall
    assert side.air_warning.isHidden() == (not archetype_page.missing_air(gunner))
    top = _page(qtbot, WizardState(catalog=_catalog("basic16")))
    assert top.view_hint.isHidden()
    top.run_and_gun_card.click()
    assert top.view_hint.text() == archetype_page.TOP_DOWN_GUN_HINT
    assert not top.air_warning.isHidden()
    assert top.air_warning.text() == archetype_page.AIR_WARNING_GUN


# ---------------------------------------------------------------- the farm, the view (T17.16)


def _farm_on(monkeypatch, farm: bool = True, isometric: bool = True) -> None:
    monkeypatch.setattr(features, "FARM_AVAILABLE", farm)
    monkeypatch.setattr(features, "ISOMETRIC_AVAILABLE", isometric)


def test_the_farm_and_the_isometric_view_are_on_since_the_gate_of_1_5() -> None:
    assert features.FARM_AVAILABLE and features.ISOMETRIC_AVAILABLE


def test_the_farm_can_be_chosen_with_its_flag_on_and_what_follows_it(qtbot, monkeypatch) -> None:
    _farm_on(monkeypatch)
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    state = WizardState(config=config.default_for("T", [ref]))
    areas = [{"name": "Woods", "biome": "forest"}]
    state.config.starter_map = {"buildings": 2, "areas": areas}
    page = _page(qtbot, state)
    card = page.farm_card
    assert card.isEnabled() and card.toolTip() == "" and card.flow.steps == FLOWS["farm"]
    card.click()
    assert page.selected() == "farm" and not card.check_label.isHidden()
    page.leave(state)
    cfg = state.config
    assert state.archetype == "farm" and cfg.archetype == "farm"
    assert cfg.input == config.default_input("farm"), "untouched bindings follow"
    assert cfg.features == config.default_features("farm"), "and untouched features"
    assert cfg.features["combat"] is False and cfg.features["demo"] is True
    # the starter map is the farm's village: its options are the same options
    assert cfg.starter_map == {"buildings": 2, "areas": areas}
    assert cfg.to_json()["archetype"] == "farm"
    assert set(cfg.starter_map_options()) >= {"farm_size", "plot", "days_per_season"}
    page.enter(state)
    assert page.selected() == "farm", "coming back, the card is still the chosen one"
    # the farm's own options do not go along to another kind; the village's do
    cfg.starter_map = {**cfg.starter_map, "animals": "coop", "days_per_season": 7}
    page.arpg_card.click()
    page.leave(state)
    assert state.config.archetype == "arpg"
    assert state.config.starter_map == {"buildings": 2, "areas": areas}
    page.enter(state)
    page.metroidvania_card.click()
    page.leave(state)
    assert state.config.starter_map == {}, "and nothing of a map is an option of rooms"


def test_the_controls_line_of_the_farm_names_its_default_bindings(qtbot, monkeypatch) -> None:
    _farm_on(monkeypatch)
    page = _page(qtbot, WizardState())
    bindings = config.default_input("farm")
    text = page.farm_card.controls_label.text()
    assert text.startswith("Controls: WASD to walk, Space to use what you hold, E to talk")
    assert {"W", "A", "S", "D"} <= {
        bindings[f"move_{way}"]["keys"][0] for way in ("up", "left", "down", "right")
    }
    assert "Space" in bindings["use"]["keys"] and bindings["interact"]["keys"] == ["E"]
    assert bindings["hotbar_1"]["keys"] == ["1"] and bindings["hotbar_10"]["keys"] == ["0"]
    assert "1 to 0 to choose" in text


def test_the_farm_card_has_its_drawing(qtbot, monkeypatch) -> None:
    from PySide6.QtGui import QImage

    from rpggen.gui.pages.archetype_page import MockScreen

    _farm_on(monkeypatch)
    page = _page(qtbot, WizardState())
    mock = page.farm_card.mock
    assert mock.art is None
    mock.setFixedSize(320, 160)
    image: QImage = mock.grab().toImage()
    seen = {
        image.pixelColor(x, y).getRgb()[:3]
        for x in range(image.width())
        for y in range(image.height())
    }
    assert MockScreen.BACKGROUNDS["farm"].getRgb()[:3] in seen
    for colour, what in (
        ((142, 98, 62), "the tilled soil"),
        ((98, 66, 44), "the watered soil"),
        ((176, 70, 60), "the roof of the house"),
        ((96, 160, 232), "the farmer"),
        ((250, 214, 90), "the clock"),
    ):
        assert colour in seen, what
    # with the art of a pack the farmer is its player
    state = _sample_state()
    page.enter(state)
    assert mock.art is not None
    mock.grab()
    for size in ((200, 48), (200, 112), (440, 160)):  # the shapes a card gives its drawing
        mock.setFixedSize(*size)
        assert not mock.grab().isNull()


def test_a_farming_pack_points_at_the_farm_card(qtbot, monkeypatch) -> None:
    from rpggen.gui.pages import archetype_page

    ranch = _catalog("ranch")
    assert archetype_page.pack_kind_of(ranch) == "farm"
    assert archetype_page.pack_kind_of(_catalog("basic16")) == ""
    _farm_on(monkeypatch, farm=False)
    off = _page(qtbot, WizardState(catalog=ranch))
    assert off.view_hint.isHidden(), "the card cannot be chosen: nothing points at it"
    _farm_on(monkeypatch)
    page = _page(qtbot, WizardState(catalog=ranch))
    assert not page.view_hint.isHidden()
    assert page.view_hint.text() == archetype_page.FARM_HINT
    assert page.view_hint.text() == "This pack looks like a farming pack: a farm fits it."
    assert page.iso_hint.isHidden(), "the ranch is seen from above"


def test_an_isometric_pack_says_so_under_the_cards(qtbot, monkeypatch) -> None:
    tiles = _catalog("iso_tiles")
    _farm_on(monkeypatch, isometric=False)
    off = _page(qtbot, WizardState(catalog=tiles))
    assert off.iso_hint.isHidden(), "the view cannot be chosen: nothing is said of it"
    _farm_on(monkeypatch)
    page = _page(qtbot, WizardState(catalog=tiles))
    assert not page.iso_hint.isHidden()
    assert page.iso_hint.text().startswith("This pack is isometric (60 x 34 diamonds).")
    plain = _page(qtbot, WizardState(catalog=_catalog("basic16")))
    assert plain.iso_hint.isHidden()


def test_a_new_project_starts_in_the_view_of_its_packs(qtbot, monkeypatch) -> None:
    """The view is chosen for the packs when the page is left: isometric when their ground is
    isometric and none is seen from above, for the kinds that have the view."""
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    tiles = _catalog("iso_tiles")

    def left(catalog_, kind: str, **changes):  # noqa: ANN001, ANN202
        state = WizardState(config=config.default_for("T", [ref]), catalog=catalog_)
        for key, value in changes.items():
            setattr(state, key, value)
        page = _page(qtbot, state)
        page.cards[kind].click()
        page.leave(state)
        return state.config

    _arcade_on(monkeypatch)
    _farm_on(monkeypatch)
    for kind in ("turn_based", "arpg", "farm", "racing"):
        assert left(tiles, kind).projection == "isometric", kind
    for kind in ("metroidvania", "shmup", "run_and_gun"):
        assert left(tiles, kind).projection == "top_down", f"{kind} has no isometric view"
    assert left(_catalog("basic16"), "turn_based").projection == "top_down"
    assert left(None, "turn_based").projection == "top_down"
    assert left(tiles, "turn_based", view_chosen=True).projection == "top_down", "a choice stays"
    assert left(tiles, "turn_based", regenerating=True).projection == "top_down"
    _farm_on(monkeypatch, isometric=False)
    assert left(tiles, "turn_based").projection == "top_down", "the flag is off: as it was"
