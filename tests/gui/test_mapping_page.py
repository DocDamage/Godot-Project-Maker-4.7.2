from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, config, inventory, mapping
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages.mapping_page import AssetPickerDialog, MappingPage
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


def _page(qtbot, pack: str) -> tuple[MappingPage, WizardState]:
    state = WizardState(pack_sources=[SYNTH / pack], target=None)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef(
        state.opened_packs[0].pack_id,
        str(SYNTH / pack),
        "0" * 64,
        "folder",
    )
    state.config = config.default_for("T", [ref])
    page = MappingPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def test_checklist_shows_status_per_role(qtbot) -> None:
    page, state = _page(qtbot, "basic16")
    player = page.rows["PLAYER"]
    assert "assigned" in player.status_label.text()
    assert player.asset_label.text() == "basic16.characters.hero"
    assert not player.thumb_label.pixmap().isNull()
    npc = page.rows["NPC"]
    assert npc.status_label.text().startswith("⚠")
    assert "Continue without" in npc.fallback.currentText()
    assert page.validate(state) == []


def test_required_missing_blocks_next_until_placeholder_or_choice(qtbot) -> None:
    page, state = _page(qtbot, "mixed")
    player = page.rows["PLAYER"]
    assert player.status_label.text().startswith("✖")
    assert [i.severity.value for i in page.validate(state)] == ["error"]
    assert [player.fallback.itemData(i) for i in range(player.fallback.count())] == ["placeholder"]
    player.fallback.setCurrentIndex(0)
    player.fallback.activated.emit(0)
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
    shown = dialog.grid.model.rowCount()
    assert shown == len(mapping.candidates(state.catalog, "GROUND")) > 0
    first = dialog.grid.proxy.index(0, 0)
    dialog.grid.select_ids([first.data(0x0100 + 1)])
    assert dialog.picked and dialog.ok_button.isEnabled()


def page_resolver(state):
    from rpggen.gui.pages.audit_page import make_resolver

    return make_resolver(state)


@pytest.mark.parametrize("pack", ["basic16", "mixed", "strips"])
def test_starter_survives_a_config_round_trip(qtbot, pack) -> None:
    page, state = _page(qtbot, pack)
    page.leave(state)
    cfg = config.GeneratorConfig.from_json(state.config.to_json())
    assert cfg.starter == state.config.starter
