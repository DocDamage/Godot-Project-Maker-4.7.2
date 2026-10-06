from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from rpggen import paths
from rpggen.core import archive, catalog, config, godot, inventory, mapping, profiles, requirements
from rpggen.errors import Severity
from rpggen.gui import state as state_mod
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.wizard import OPTIONS_INDEX, MainWindow, default_pages

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample_pack"


def _build_tool():
    spec = importlib.util.spec_from_file_location(
        "build_sample_pack", ROOT / "tools" / "build_sample_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble_sample():
    opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
    inv = inventory.build_inventory(opened)
    cat, issues, _gen = catalog.assemble([(opened, inv)], None, [])
    return cat, issues


# ------------------------------------------------------------------------ the pack


def test_the_pack_is_cc0_and_documented() -> None:
    assert paths.sample_pack_root() == SAMPLE and SAMPLE.is_dir()
    assert "CC0" in (SAMPLE / "LICENSE.txt").read_text(encoding="utf-8")
    sources = (SAMPLE / "SOURCES.md").read_text(encoding="utf-8")
    for png in SAMPLE.rglob("*.png"):
        # every folder of the pack is described (files are listed by name or by wildcard)
        rel = png.relative_to(SAMPLE).as_posix()
        assert rel in sources or f"{png.parent.name}/*.png" in sources, rel


def test_the_committed_images_match_the_generator(tmp_path: Path) -> None:
    tool = _build_tool()
    tool.build_pack(tmp_path / "fresh")
    committed = sorted(p.relative_to(SAMPLE).as_posix() for p in SAMPLE.rglob("*.png"))
    assert committed == sorted(tool.FILES)
    for rel in committed:
        a = Image.open(SAMPLE / rel).convert("RGBA")
        b = Image.open(tmp_path / "fresh" / rel).convert("RGBA")
        assert a.size == b.size and ImageChops.difference(a, b).getbbox() is None, rel


def test_the_pack_covers_every_demo_role() -> None:
    cat, _issues = _assemble_sample()
    roles = {catalog.effective(a)["role"] for a in cat.assets}
    assert {"PLAYER", "NPC", "ENEMY", "GROUND", "WALL", "WATER", "ITEM", "UI", "PORTRAIT"} <= roles
    names = {o.name for o in cat.objects}
    assert any(o.role == "BUILDING" for o in cat.objects)
    assert len([o for o in cat.objects if o.role == "DECORATION"]) == 2
    assert names  # a house and two trees were found among the loose tiles


def test_the_profile_makes_the_audit_all_confirmed(tmp_path: Path) -> None:
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    cat, issues = _assemble_sample()
    assert {a.status for a in cat.assets} == {"CONFIRMED"}
    assert cat.packs[0].profile_id == "rpggen_sample_pack"
    assert [i.code for i in issues if i.severity is not Severity.INFO] == []
    house = next(o for o in cat.objects if o.role == "BUILDING")
    assert house.name == "house" and house.door == [40, 63] and house.status == "CONFIRMED"
    assert sorted(o.name for o in cat.objects if o.role == "DECORATION") == ["tree_1", "tree_2"]
    assert all(o.status == "CONFIRMED" for o in cat.objects)


def test_requirements_and_mapping_are_complete(tmp_path: Path) -> None:
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    cat, _issues = _assemble_sample()
    ref = config.PackRef("sample_pack", str(SAMPLE), "0" * 64, "folder")
    cfg = config.default_for("Sample RPG", [ref])
    assert requirements.check(cat, cfg) == []
    starter = mapping.default_starter(cat, "turn_based")
    assert set(starter) == {"player", "npc", "enemy", "ground", "building", "chest", "portrait"}
    assert starter["building"].endswith("#house")
    assert mapping.missing_required(cat, "turn_based", set()) == []


# ------------------------------------------------------------------------ the button


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch) -> MainWindow:
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir()
    win = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(win)
    win.show()
    return win


def test_try_fills_the_page_and_jumps_to_options(qtbot, window, tmp_path) -> None:
    page = window.pages[0]
    assert page.sample_button.text() == "Try with sample pack"
    page.sample_button.click()
    assert window.current_index == OPTIONS_INDEX
    state = window.state
    assert state.project_name == "Sample RPG"
    assert state.pack_sources == [SAMPLE]
    assert state.target == tmp_path / "Documents" / "rpggen-sample-1"
    assert state.config is not None and state.config.project_name == "Sample RPG"
    assert state.catalog is not None
    assert {a.status for a in state.catalog.assets} == {"CONFIRMED"}
    assert state.config.starter["building"].endswith("#house")
    assert window.next_button.text() == "Generate" and window.next_button.isEnabled()


def test_try_picks_a_new_output_folder_each_time(qtbot, window, tmp_path) -> None:
    (tmp_path / "Documents" / "rpggen-sample-1").mkdir()
    (tmp_path / "Documents" / "rpggen-sample-2").mkdir()
    assert window.pages[0].sample_target() == tmp_path / "Documents" / "rpggen-sample-3"


def test_try_stays_on_the_page_when_godot_is_missing(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path)
    win = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(win)
    win.show()
    assert win.pages[0].try_sample() is False
    assert win.current_index == 0
    assert any("Godot" in i.message for i in win.issues)
    assert win.pages[0].pack_list.count() == 1  # the sample is filled in anyway
