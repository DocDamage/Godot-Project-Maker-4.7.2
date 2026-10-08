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
