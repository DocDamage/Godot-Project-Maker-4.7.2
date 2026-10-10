"""The whole wizard on the sample pack: open -> Try -> Generate -> Results (needs Godot)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import godot
from rpggen.gui import state as state_mod
from rpggen.gui.pages.generate_page import GeneratePage
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

pytestmark = pytest.mark.slow


def test_try_generate_and_results_on_the_sample_pack(
    qtbot, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [godot_exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir()
    window = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(window)
    window.show()

    window.pages[0].sample_button.click()  # Try with sample pack
    assert window.current_index == OPTIONS_INDEX
    assert window.next_button.text() == "Generate"

    window.next_button.click()  # Generate
    generate = window.current_page
    assert isinstance(generate, GeneratePage) and generate.running
    qtbot.waitUntil(lambda: not generate.running, timeout=240_000)
    result = window.state.run_result
    assert result is not None
    assert result.ok, [(i.code, i.message) for i in result.issues]
    assert window.next_button.isEnabled()

    window.next_button.click()  # Show results
    results = window.current_page
    assert isinstance(results, ResultsPage)
    assert "generated" in results.header.text()
    assert results.count_labels["errors"].text() == "0"
    assert int(results.count_labels["assets"].text()) >= 14
    assert int(results.count_labels["scenes"].text()) >= 1

    target = window.state.target
    assert (target / "GENERATION_REPORT.md").is_file()
    assert (target / "project.godot").is_file()
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "Result: SUCCESS" in report and "sample_pack" in report


def test_the_arpg_path_generates_a_project_that_passes_its_smoke_test(
    qtbot, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ARPG card is enabled; picking it on the archetype page carries through to a project
    with the action-RPG runtime, whose smoke test (the arpg steps) passed."""
    from rpggen import features, jsonio
    from rpggen.gui.pages.archetype_page import ArchetypePage

    assert features.ARPG_AVAILABLE is True
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [godot_exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir()
    window = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(window)
    window.show()

    window.pages[0].sample_button.click()  # Try with sample pack: ends on the options page
    assert window.current_index == OPTIONS_INDEX
    assert window.state.archetype == "turn_based"
    archetype_index = next(i for i, p in enumerate(window.pages) if isinstance(p, ArchetypePage))
    while window.current_index > archetype_index:
        window.back_button.click()
    page = window.current_page
    assert isinstance(page, ArchetypePage) and page.arpg_card.isEnabled()
    page.arpg_card.click()
    window.continue_to(OPTIONS_INDEX)
    assert window.current_index == OPTIONS_INDEX
    assert window.state.archetype == "arpg"
    assert window.state.config is not None and window.state.config.archetype == "arpg"
    assert "attack" in window.state.config.input and "dodge" in window.state.config.input

    window.next_button.click()  # Generate
    generate = window.current_page
    assert isinstance(generate, GeneratePage) and generate.running
    qtbot.waitUntil(lambda: not generate.running, timeout=300_000)
    result = window.state.run_result
    assert result is not None
    assert result.ok, [(i.code, i.message) for i in result.issues]

    target = window.state.target
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    names = [item["name"] for item in smoke["items"]]
    assert smoke["ok"] is True and "death_policy" in names and "encounter_start" not in names
    assert (target / "addons/rpg_runtime/archetypes/arpg").is_dir()
    assert not (target / "addons/rpg_runtime/archetypes/turn_based").exists()
    assert "Combat and enemies (action RPG)" in (target / "README.md").read_text(encoding="utf-8")


def test_the_metroidvania_path_generates_a_project_that_passes_its_smoke_test(
    qtbot, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate of 1.2 (T14.13): the welcome view's side-view sample leads to the Options page
    with the Metroidvania card chosen, the card can be left and chosen again, and the project
    that is generated has the metroidvania's runtime, rooms and README and passed its own smoke
    sequence."""
    from rpggen import features, jsonio
    from rpggen.gui.pages.archetype_page import ArchetypePage
    from rpggen.gui.pages.options_page import OptionsPage

    assert features.METROIDVANIA_AVAILABLE is True
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [godot_exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir()
    window = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(window)
    window.show()

    # the welcome view's second sample
    window.show_welcome_view()
    side = window.welcome.sample_side_action
    assert side is not None and side.text() == "Side-view cave"
    side.trigger()
    # T15.22: the sample walks on to the Generate page and starts with the default options;
    # Back is open until the run writes the project, stops the run and shows the options
    qtbot.waitUntil(lambda: window.current_index == OPTIONS_INDEX + 1, timeout=120_000)
    started = window.current_page
    qtbot.waitUntil(lambda: started.running, timeout=30_000)
    assert not started.sample_banner.isHidden() and window.back_button.isEnabled()
    window.back_button.click()
    assert not started.running and window.current_index == OPTIONS_INDEX
    assert not window.state.sample_run
    assert not (tmp_path / "Documents" / "rpggen-sample-1" / "project.godot").exists()
    assert window.state.archetype == "metroidvania"
    cfg = window.state.config
    assert cfg is not None and cfg.archetype == "metroidvania"
    assert {"jump", "dash", "attack", "down"} <= set(cfg.input)
    options = window.current_page
    assert isinstance(options, OptionsPage)
    assert not options.world_box.isHidden() and options.starter_box.isHidden()
    assert options.world_box.summary.text() == "6 rooms, 2 abilities, a guardian"

    # back to the Archetype page: the third card is the chosen one, and stays the choice
    archetype_index = next(i for i, p in enumerate(window.pages) if isinstance(p, ArchetypePage))
    while window.current_index > archetype_index:
        window.back_button.click()
    page = window.current_page
    assert isinstance(page, ArchetypePage)
    assert page.metroidvania_card.isEnabled() and page.selected() == "metroidvania"
    assert not page.view_hint.isHidden() and "side-view" in page.view_hint.text()
    assert page.air_warning.isHidden(), "the sample hero has jump and fall animations"
    page.turn_card.click()
    page.metroidvania_card.click()
    window.continue_to(OPTIONS_INDEX)
    assert window.current_index == OPTIONS_INDEX
    assert window.state.config is not None and window.state.config.archetype == "metroidvania"
    assert window.state.config.starter.get("boss"), "the guardian's sprite is mapped"
    assert window.state.config.sounds.get("sfx_jump"), "and the jump sound"

    window.next_button.click()  # Generate
    generate = window.current_page
    assert isinstance(generate, GeneratePage) and generate.running
    qtbot.waitUntil(lambda: not generate.running, timeout=300_000)
    result = window.state.run_result
    assert result is not None
    assert result.ok, [(i.code, i.message) for i in result.issues]

    target = window.state.target
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    names = [item["name"] for item in smoke["items"]]
    assert smoke["ok"] is True
    assert names[0] == "title_new_game" and names[-1] == "end_room"
    assert "guardian_dies" in names and "encounter_start" not in names
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["metroidvania"]
    assert (target / "game/maps/rooms/room_01.tscn").is_file()
    assert not (target / "game/maps/starter_map.tscn").exists()
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "Rooms, abilities and enemies (metroidvania)" in readme

    window.next_button.click()  # Show results
    results = window.current_page
    assert isinstance(results, ResultsPage)
    assert "generated" in results.header.text()
    assert results.count_labels["errors"].text() == "0"
    assert results.starter_button.text() == "Open first room"
    assert results.first_map() == "res://game/maps/rooms/room_01.tscn"
    assert results.picture_path() is not None, "the world, seen from the side"
