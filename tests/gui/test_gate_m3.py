"""Milestone gate M3: undo/redo for every edit type and drafts that resume after a restart."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, godot, inventory, objects
from rpggen.core.catalog import FolderRule
from rpggen.gui import edits
from rpggen.gui import state as state_mod
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

ROOT = Path(__file__).resolve().parents[2]
SYNTH = ROOT / "test_packs" / "synthetic"


def _build(pack: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


# ------------------------------------------------------------------------ undo / redo


def _new_object(sheet: str, taken: set[str]) -> catalog.SheetObject:
    return objects.make_object(sheet, "My object", (0, 0, 16, 16), taken)


def _first(cat, usage=None):
    return next(a for a in cat.assets if usage is None or catalog.effective(a)["usage"] == usage)


def _sheet(cat):
    return cat.objects[0].sheet


def _rule(glob: str, tag: str) -> FolderRule:
    return FolderRule("basic16", glob, {"tags": [tag]})


def _setup_override(s, c):
    s.set_override(_first(c).id, "role", "WALL")


def _setup_rules(s, c):
    s.add_rule(_rule("tiles/*", "a"))
    s.add_rule(_rule("characters/*", "b"))


# name -> (pack, setup (not counted), the edit under test)
CASES = {
    "set_override": ("basic16", None, lambda s, c: s.set_override(_first(c).id, "role", "WALL")),
    "clear_override": (
        "basic16",
        _setup_override,
        lambda s, c: s.clear_override(_first(c).id, "role"),
    ),
    "confirm": (
        "basic16",
        None,
        lambda s, c: s.confirm([a.id for a in c.assets if a.status != "CONFIRMED"]),
    ),
    "set_overrides": (
        "basic16",
        None,
        lambda s, c: s.set_overrides([_first(c).id], {"role": "NPC", "tags": ["x"]}),
    ),
    "bulk_edit": (
        "mixed",
        None,
        lambda s, c: s.bulk_edit([a.id for a in c.assets[:3]], {"role": "ITEM"}, ["bulk"], []),
    ),
    "add_rule": ("basic16", None, lambda s, c: s.add_rule(_rule("tiles/*", "t"))),
    "delete_rule": ("basic16", _setup_rules, lambda s, c: s.delete_rule(0)),
    "reorder_rules": ("basic16", _setup_rules, lambda s, c: s.reorder_rules([1, 0])),
    "add_object": (
        "objects_in_sheet",
        None,
        lambda s, c: s.add_object(_new_object(_sheet(c), {o.id for o in c.objects})),
    ),
    "update_object": (
        "objects_in_sheet",
        None,
        lambda s, c: s.update_object(c.objects[0].id, name="renamed", tags=["t"]),
    ),
    "remove_object": ("objects_in_sheet", None, lambda s, c: s.remove_object(c.objects[0].id)),
    "reject_object": ("objects_in_sheet", None, lambda s, c: s.reject_object(c.objects[0].id)),
    "accept_suggestions": (
        "objects_in_sheet",
        None,
        lambda s, c: s.accept_suggestions(_sheet(c)),
    ),
    "set_sheet_objects": (
        "objects_in_sheet",
        None,
        lambda s, c: s.set_sheet_objects(_sheet(c), [_new_object(_sheet(c), set())]),
    ),
}


@pytest.mark.parametrize("name", list(CASES))
def test_every_edit_type_undoes_and_redoes(qtbot, name: str) -> None:
    pack, setup, edit = CASES[name]
    session = edits.EditSession(_build(pack))
    if setup is not None:
        setup(session, session.catalog)
        session.undo_stack.clear()
    before = session.catalog.to_json()
    assert edit(session, session.catalog), name
    assert session.undo_stack.count() == 1, f"{name} must be exactly one undo step"
    after = session.catalog.to_json()
    assert after != before, name
    session.undo_stack.undo()
    assert session.catalog.to_json() == before, f"{name}: undo restores the catalog"
    session.undo_stack.redo()
    assert session.catalog.to_json() == after, f"{name}: redo reapplies the edit"


# ------------------------------------------------------------------------ drafts


@pytest.fixture
def make_window(qtbot, tmp_path, monkeypatch):
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    monkeypatch.setattr(ProjectPage, "ask_resume", lambda self: True)
    (tmp_path / "Documents").mkdir()

    def make() -> MainWindow:
        window = MainWindow(state_mod.WizardState(), default_pages())
        qtbot.addWidget(window)
        window.show()
        return window

    return make


def test_a_draft_resumes_after_closing_and_reopening(make_window) -> None:
    first = make_window()
    first.pages[0].sample_actions["top"].trigger()  # the list of the button (T16.17)
    assert first.current_index == OPTIONS_INDEX
    hero = next(a.id for a in first.state.catalog.assets if a.id.endswith("hero"))
    audit = first.pages[2]
    assert audit.session.set_override(hero, "tags", ["resumed"])
    first.state.catalog = audit.session.catalog
    options = first.pages[OPTIONS_INDEX]
    options.seed_box.setValue(4242)
    options.feature_boxes["combat"].setChecked(False)
    options.layer_name.setText("Fog")
    options.add_layer_button.click()
    first.go_back()  # leaving a page writes the draft
    target = first.state.target
    assert state_mod.load_draft(target) is not None
    first.close()

    second = make_window()  # a new session of the app: nothing in memory
    second.pages[0].sample_actions["top"].trigger()
    assert second.current_index == OPTIONS_INDEX
    assert second.state.target == target
    assert catalog.effective(second.state.catalog.asset(hero))["tags"] == ["resumed"]
    options = second.pages[OPTIONS_INDEX]
    assert options.seed_box.value() == 4242
    assert not options.feature_boxes["combat"].isChecked()
    assert not options.feature_boxes["demo"].isEnabled()
    assert "Fog" in options.layers()
