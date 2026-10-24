"""T17.33: the wizard makes a project of assets only: its card, the Mapping page that asks for
nothing, the Options page without a game's sections and with the view of the packs, the
Generate page whose skipped play and export read as no failure, and Results without Play.
Offscreen and without Godot: the run is a stand-in that reports what the orchestrator does."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import dev
from rpggen.core import config, orchestrator
from rpggen.errors import CODES, Issue
from rpggen.gui import workers
from rpggen.gui.pages.archetype_page import ArchetypePage
from rpggen.gui.pages.generate_page import PHASES, GeneratePage
from rpggen.gui.pages.mapping_page import MappingPage
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import stepper
from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

SKIPPED = ("smoke", "export")


def _fake_run(seen: list[config.GeneratorConfig]):  # noqa: ANN202
    """A stand-in for ``workers.generate``: every phase, and the play and the export skipped
    with VAL-032, as the orchestrator does for a project of assets only."""

    def fake(cfg, cat, target, godot, placeholders, git_message=None, force=False,  # noqa: ANN001, ANN202
             accept=False, *, callbacks):  # fmt: skip
        seen.append(cfg)
        info = CODES["VAL-032"]
        for i, name in enumerate(PHASES, start=1):
            callbacks.on_phase(name, i, len(PHASES))
            if name in SKIPPED:
                callbacks.on_skip(name, "VAL-032")
        (target / "generated").mkdir(parents=True, exist_ok=True)
        issue = Issue("VAL-032", info.severity, info.message, info.fix)
        result = orchestrator.RunResult(True, target, [issue], None, None, catalog=cat, cfg=cfg)
        result.skipped = dict.fromkeys(SKIPPED, "VAL-032")
        result.timings = dict.fromkeys(PHASES, 1.0)
        return result

    return fake


def _window(qtbot, tmp_path: Path) -> MainWindow:  # noqa: ANN001
    state = dev.layout_state("turn_based", tmp_path)
    state.run_result = None  # not generated yet
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    return window


def test_the_assets_card_leads_to_generation_without_a_player(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[config.GeneratorConfig] = []
    monkeypatch.setattr(workers, "generate", _fake_run(seen))
    window = _window(qtbot, tmp_path)
    state = window.state
    archetype_index = next(i for i, p in enumerate(window.pages) if isinstance(p, ArchetypePage))
    window.show_page(archetype_index)
    page = window.current_page
    assert isinstance(page, ArchetypePage)
    page.assets_card.click()
    assert page.selected() == "assets"

    # the Mapping page asks for no role: nothing stops the way to the options
    window.go_next()
    while not isinstance(window.current_page, MappingPage):
        window.go_next()
    mapping_page = window.current_page
    assert state.config is not None and state.config.archetype == "assets"
    assert mapping_page.rows == {} and mapping_page.validate(state) == []
    assert mapping_page.status(state) == ("ok", 0)
    assert not mapping_page.assets_note.isHidden() and mapping_page.sound_section.isHidden()
    assert "Nothing to assign" in mapping_page.summary_label.text()
    window.continue_to(OPTIONS_INDEX)
    assert window.current_index == OPTIONS_INDEX
    options_page = window.current_page
    assert isinstance(options_page, OptionsPage)
    assert not options_page.assets_box.isHidden()
    for hidden in (
        options_page.starter_box,
        options_page.imported_box,
        options_page.layers_box,
        options_page.export_targets,
        options_page.presets,
        options_page.repair_box,
    ):
        assert hidden.isHidden(), hidden.objectName()
    for key in ("demo", "save", "dialogue", "combat", "navigation", "debug_tools"):
        assert options_page.feature_boxes[key].isHidden(), key
    for key in ("tilesets", "collision", "terrain", "animations", "editor_tools"):
        assert not options_page.feature_boxes[key].isHidden(), key
    assert options_page.summary.archetype_label.text() == "<b>Assets only</b>"
    assert "No maps" in options_page.summary.maps_label.text()
    assert options_page.validate(state) == []
    assert window.next_button.text() == "Generate"

    window.next_button.click()  # Generate
    generate = window.current_page
    assert isinstance(generate, GeneratePage)
    qtbot.waitUntil(lambda: not generate.running, timeout=20_000)
    cfg = seen[0]
    assert cfg.archetype == "assets" and cfg.starter_map == {} and cfg.sounds == {}
    assert cfg.features == config.default_features("assets")
    assert cfg.view == "", "nobody chose: the packs decide the view in the run"
    assert generate.status_label.text() == "Generation finished."
    assert generate.status_label.property("state") == "ok"
    for name in SKIPPED:
        item = generate.phase_list.item(PHASES.index(name))
        assert item.data(stepper.StateRole) == stepper.SKIPPED, name
        assert "skipped: a project of assets only has no game" in item.text()
        assert "✖" not in item.text()
    build = generate.phase_list.item(PHASES.index("build"))
    assert "Building the tile sets and scenes" in build.text()

    window.next_button.click()  # Show results
    results = window.current_page
    assert isinstance(results, ResultsPage)
    assert "generated" in results.header.text()
    assert results.play_button.isHidden() and results.starter_button.isHidden()
    assert not results.godot_button.isHidden()
    assert "generated/tilesets" in results.what_next_label.text()
    assert "F5" not in results.what_next_label.text()


def test_the_view_of_a_project_of_assets_only_is_chosen_on_the_options_page(
    qtbot, tmp_path: Path
) -> None:
    """The packs choose the view until somebody does; from the side the untouched bindings
    are the side's (it jumps), and back from above they are the top's again."""
    window = _window(qtbot, tmp_path)
    state = window.state
    assert state.config is not None
    state.archetype = state.config.archetype = "assets"
    state.config.features = config.default_features("assets")
    state.config.input = config.default_input("assets")
    state.config.starter_map = {}
    window.show_page(OPTIONS_INDEX)
    page = window.current_page
    assert isinstance(page, OptionsPage)
    box = page.assets_box
    combo = box.view_combo
    assert [combo.itemData(i) for i in range(combo.count())] == ["top", "side"]
    assert box.view() == "top", "the sample village is drawn from above"
    assert combo.isEnabled() and not box.note.isHidden()
    combo.setCurrentIndex(combo.findData("side"))
    assert page.draft is not None and page.draft.view == "side"
    assert page.draft.input == config.default_input("assets", "side")
    assert "jump" in page.model.input_map and box.note.isHidden()
    assert state.view_chosen
    page.leave(state)
    assert state.config.view == "side" and "jump" in state.config.input
    window.show_page(OPTIONS_INDEX)
    page.assets_box.view_combo.setCurrentIndex(page.assets_box.view_combo.findData("top"))
    page.leave(state)
    assert state.config.view == "top" and "jump" not in state.config.input
    assert state.config.projection == "top_down"


def test_an_isometric_pack_offers_the_isometric_view(qtbot, monkeypatch) -> None:  # noqa: ANN001
    from rpggen import features
    from rpggen.core import archive, catalog, inventory
    from rpggen.gui.models.options_model import OptionsModel

    monkeypatch.setattr(features, "ISOMETRIC_AVAILABLE", True)
    synth = dev.REPO_ROOT / "test_packs" / "synthetic" / "iso_tiles"
    opened = archive.open_pack(synth, set())
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    ref = config.PackRef("iso_tiles", str(synth), "0" * 64, "folder")
    state = WizardState(catalog=cat, config=config.default_for("T", [ref], archetype="assets"))
    model = OptionsModel()
    model.enter(state)
    view = model.assets_view_state()
    assert view.choices == ("top", "side", "isometric")
    assert view.view == "isometric", "the packs are isometric"
    assert model.set_assets_view("top")
    assert model.draft is not None and model.draft.projection == "top_down"
    assert model.set_assets_view("isometric")
    assert model.draft.projection == "isometric" and model.draft.view == "top"
    assert not model.set_assets_view("isometric"), "nothing changed"
    # packs of squares have nothing to choose isometric for
    plain = OptionsModel()
    plain.enter(WizardState(config=config.default_for("T", [ref], archetype="assets")))
    assert plain.assets_view_state().choices == ("top", "side")
