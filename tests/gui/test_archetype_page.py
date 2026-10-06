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


def test_arpg_is_disabled_until_m9(qtbot) -> None:
    assert features.ARPG_AVAILABLE is False
    page = _page(qtbot, WizardState())
    assert not page.arpg_card.isEnabled()
    assert page.arpg_card.toolTip() == "Coming in a later version"


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
