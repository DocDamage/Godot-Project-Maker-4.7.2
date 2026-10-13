"""T17.16: what earlier cards of M17 left to the wizard. A tile turned four ways is *Turns
(4)* in the audit and the sheets of the four seasons are *Seasons (4)* (colours stay *Variants*),
the Mapping page calls neither of them colours, and a pack card says *Looks like a farming
pack* and *Isometric tiles, 60 x 34*."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from rpggen.core import catalog, config, labels
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.models.project_model import ProjectModel
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.pages.mapping_page import MORE_DATA, NONE_DATA, MappingPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import asset_grid as ag

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _state(pack: str, archetype: str = "turn_based", projection: str = "top_down") -> WizardState:
    state = WizardState(pack_sources=[SYNTH / pack], archetype=archetype)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef(state.opened_packs[0].pack_id, str(SYNTH / pack), "0" * 64, "folder")
    state.config = config.default_for("T", [ref], archetype=archetype)
    state.config.projection = projection
    return state


def _audit(qtbot, state: WizardState) -> AuditPage:
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    page.enter(state)
    page.grid.chips["chipAll"].click()
    return page


def _group(cat: catalog.Catalog, first: str) -> list[catalog.Asset]:
    return [a for a in catalog.colour_group(cat, first) if a is not None]


# ------------------------------------------------------------------------ core


def test_a_group_is_of_colours_of_turns_or_of_seasons() -> None:
    ranch = _state("ranch").catalog
    grass = next(a.id for a in ranch.assets if a.path.endswith("spring/grass_16x16.png"))
    hen = next(
        a.id for a in ranch.assets if a.path.endswith("hen_01_black_move_down_16x16_4frames.png")
    )
    assert catalog.group_kind(_group(ranch, grass)) == catalog.GROUP_SEASONS
    assert catalog.group_kind(_group(ranch, hen)) == catalog.GROUP_COLOURS
    names = [catalog.member_name(a, catalog.GROUP_SEASONS) for a in _group(ranch, grass)]
    assert sorted(names) == ["autumn", "spring", "summer", "winter"]
    tiles = _state("iso_tiles").catalog
    first = "iso_tiles.png.isotile_001_0"
    turns = _group(tiles, first)
    assert catalog.group_kind(turns) == catalog.GROUP_TURNS
    assert [catalog.member_name(a, catalog.GROUP_TURNS) for a in turns] == [
        "turn 0",
        "turn 1",
        "turn 2",
        "turn 3",
    ]
    assert catalog.group_kind([]) == catalog.GROUP_COLOURS
    # every group of the three packs is one of the three, and none of the turns is a colour
    for cat in (ranch, tiles, _state("iso_miniature").catalog):
        for head in catalog.colour_groups(cat):
            kind = catalog.group_kind(_group(cat, head))
            assert kind in (catalog.GROUP_COLOURS, catalog.GROUP_TURNS, catalog.GROUP_SEASONS)
    kinds = {catalog.group_kind(_group(tiles, head)) for head in catalog.colour_groups(tiles)}
    assert kinds == {catalog.GROUP_TURNS}


# ------------------------------------------------------------------------ the audit


def test_a_set_of_turns_is_turns_in_the_audit(qtbot) -> None:
    state = _state("iso_tiles")
    page = _audit(qtbot, state)
    grid, detail = page.grid, page.detail
    first, third = "iso_tiles.png.isotile_001_0", "iso_tiles.png.isotile_001_2"
    grid.select_ids([first])
    assert detail.variants_box.isVisibleTo(detail)
    assert detail.variants_label.text() == "Turns (4)"
    assert detail.variants_names.text() == "turn 0, turn 1, turn 2, turn 3"
    assert "plain" not in detail.variants_names.text()
    assert "turn" in detail.variants_show_button.toolTip()
    assert "turn" in detail.variants_select_button.toolTip()
    assert detail.variants_kind == catalog.GROUP_TURNS
    index = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(first), 0))
    assert f"{ag.VARIANT_GLYPH} 4 turns" in index.data(Qt.ItemDataRole.ToolTipRole)
    assert index.data(Qt.ItemDataRole.AccessibleTextRole).endswith(", 4 turns")
    assert grid.view.card_delegate.variant_badge(index) == f"{ag.VARIANT_GLYPH} 4"
    detail.variants_show_button.click()  # a card a turn
    index = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(third), 0))
    assert "a turn of " + first in index.data(Qt.ItemDataRole.ToolTipRole)
    assert "colour" not in index.data(Qt.ItemDataRole.ToolTipRole)


def test_the_sheets_of_the_seasons_are_seasons_and_colours_stay_variants(qtbot) -> None:
    state = _state("ranch")
    page = _audit(qtbot, state)
    grid, detail = page.grid, page.detail
    cat = state.catalog
    grass = next(a.id for a in cat.assets if a.path.endswith("spring/grass_16x16.png"))
    grid.select_ids([grass])
    assert detail.variants_label.text() == "Seasons (4)"
    assert sorted(detail.variants_names.text().split(", ")) == [
        "autumn",
        "spring",
        "summer",
        "winter",
    ]
    assert "season" in detail.variants_show_button.toolTip()
    index = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(grass), 0))
    assert f"{ag.VARIANT_GLYPH} 4 seasons" in index.data(Qt.ItemDataRole.ToolTipRole)
    hen = next(
        a.id for a in cat.assets if a.path.endswith("hen_01_black_move_down_16x16_4frames.png")
    )
    grid.select_ids([hen])
    assert detail.variants_label.text() == "Variants (3)"
    assert detail.variants_names.text() == "black, brown, white"
    assert "colour" in detail.variants_show_button.toolTip()
    index = grid.proxy.mapFromSource(grid.model.index(grid.model.row_of(hen), 0))
    assert "3 colour variants" in index.data(Qt.ItemDataRole.ToolTipRole)


def test_the_roles_of_the_farm_have_their_labels_and_their_group() -> None:
    """T17.02 gave the audit CROP, ANIMAL and TOOL: each has a name a person reads, a sentence
    of help, and a place among the groups of the Mapping page."""
    from rpggen.gui.widgets import asset_detail

    grouped = {role for _group_name, roles in labels.MAPPING_GROUPS for role in roles}
    for role, name in (("CROP", "crop"), ("ANIMAL", "animal"), ("TOOL", "tool")):
        assert role in asset_detail.ROLES, f"{role} can be chosen in the audit"
        assert labels.role_label(role) != role and name in labels.role_label(role).lower()
        assert labels.role_help(role)
        assert role in grouped, f"{role} has a group on the Mapping page"


# ------------------------------------------------------------------------ the Mapping page


def _mapping(qtbot, state: WizardState) -> MappingPage:
    page = MappingPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page


def test_the_mapping_page_calls_turns_turns(qtbot) -> None:
    state = _state("iso_tiles", projection="isometric")
    page = _mapping(qtbot, state)
    row = page.rows["GROUND"]
    assert "4 turns" in row.asset_combo.currentText()
    assert "colour" not in row.asset_combo.currentText()
    page.fill_candidates("GROUND")
    combo = row.asset_combo
    texts = [combo.itemText(i) for i in range(combo.count())]
    assert any(text.endswith("(turn 2)") for text in texts), texts
    assert not any("colour" in text for text in texts)


def test_the_mapping_page_calls_seasons_seasons(qtbot) -> None:
    state = _state("ranch", archetype="farm")
    cat = state.catalog
    grass = next(a.id for a in cat.assets if a.path.endswith("spring/grass_16x16.png"))
    page = _mapping(qtbot, state)
    page.assign("GROUND", grass)
    row = page.rows["GROUND"]
    assert "4 seasons" in row.asset_combo.currentText()
    page.fill_candidates("GROUND")
    combo = row.asset_combo
    offered = [i for i in page.candidate_ids("GROUND") if i not in (NONE_DATA, MORE_DATA)]
    assert offered[0] == grass and len(offered) >= 4
    texts = [combo.itemText(i) for i in range(combo.count())]
    assert any("(season: winter)" in text for text in texts), texts
    assert not any("colour" in text for text in texts)


# ------------------------------------------------------------------------ the pack card


def test_the_pack_card_says_what_a_pack_looks_like() -> None:
    model = ProjectModel()
    assert model.mark_words((catalog.VIEW_FARM,)) == ["Looks like a farming pack"]
    assert model.mark_words(("isometric:180x104:measured", catalog.VIEW_ISOMETRIC)) == [
        "Isometric tiles, 180 x 104"
    ]
    assert model.mark_words(("isometric:what", "view:side")) == []
    for pack, words in (
        ("ranch", "Looks like a farming pack"),
        ("iso_tiles", "Isometric tiles, 60 x 34"),
    ):
        marks = tuple(_state(pack).catalog.packs[0].warnings)
        assert words in model.mark_words(marks), pack
    # the older words are what they were
    assert model.mark_words((catalog.VIEW_RACING, catalog.VIEW_SHMUP)) == [
        "Looks like a racing pack",
        "Looks like a shooter pack",
    ]
