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


# ------------------------------------------------------------------------ the side-view pack (T14.09)

SIDE = ROOT / "sample_pack_side"
SIDE_PROFILE = SIDE / "sample_side.rpgprofile.json"


def _assemble_side():
    opened = archive.open_pack(SIDE, set(), pack_id="sample_pack_side")
    inv = inventory.build_inventory(opened)
    cat, issues, _gen = catalog.assemble([(opened, inv)], None, [])
    return cat, issues


def test_the_side_pack_is_cc0_and_documented() -> None:
    assert paths.sample_pack_side_root() == SIDE and SIDE.is_dir()
    assert "CC0" in (SIDE / "LICENSE.txt").read_text(encoding="utf-8")
    source = (SIDE / "SOURCE.txt").read_text(encoding="utf-8")
    for png in SIDE.rglob("*.png"):
        rel = png.relative_to(SIDE).as_posix()
        stem = png.stem.split("_")[0]
        assert (
            rel in source
            or f"{png.parent.name}/*.png" in source
            or (f"{png.parent.name}/{stem}_*.png" in source)
        ), rel


def test_the_committed_side_pack_matches_the_generator(tmp_path: Path) -> None:
    tool = _build_tool()
    tool.build_side_pack(tmp_path / "fresh")
    tool.build_side_pack(tmp_path / "again")
    committed = sorted(p.relative_to(SIDE).as_posix() for p in SIDE.rglob("*.png"))
    assert committed == sorted(tool.SIDE_IMAGES)
    for rel in committed:
        a = Image.open(SIDE / rel).convert("RGBA")
        b = Image.open(tmp_path / "fresh" / rel).convert("RGBA")
        assert a.size == b.size and ImageChops.difference(a, b).getbbox() is None, rel
        assert (tmp_path / "fresh" / rel).read_bytes() == (tmp_path / "again" / rel).read_bytes()
    sounds = sorted(p.relative_to(SIDE).as_posix() for p in SIDE.rglob("*.wav"))
    assert len(sounds) == 14 and {"sfx/jump.wav", "sfx/land.wav", "sfx/dash.wav"} <= set(sounds)
    for rel in sounds:
        assert (SIDE / rel).read_bytes() == (tmp_path / "fresh" / rel).read_bytes(), rel


def test_the_side_pack_shares_the_sounds_of_the_first_and_is_about_its_size() -> None:
    for wav in SAMPLE.rglob("*.wav"):
        rel = wav.relative_to(SAMPLE)
        assert (SIDE / rel).read_bytes() == wav.read_bytes(), rel

    def size(root: Path) -> int:
        return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())

    assert abs(size(SIDE) - size(SAMPLE)) < 300_000


def test_the_side_pack_golden() -> None:
    cat, _issues = _assemble_side()
    golden = ROOT / "tests" / "golden" / "sample_pack_side.catalog.json"
    from rpggen import jsonio

    assert jsonio.dumps(cat.to_json()) == golden.read_text(encoding="utf-8")


def test_the_side_pack_is_detected_as_side_view_with_every_part() -> None:
    cat, _issues = _assemble_side()
    assert catalog.pack_view(cat.packs[0]) == "side"
    roles = {catalog.effective(a)["role"] for a in cat.assets}
    assert {
        "PLAYER",
        "GROUND",
        "ENEMY",
        "BOSS",
        "NPC",
        "ITEM",
        "BACKGROUND",
        "UI",
        "PORTRAIT",
    } <= roles
    hero = cat.asset("sample_pack_side.characters.hero_attack")
    assert hero is not None
    assert sorted(hero.detected["animations"]) == [
        "attack_down", "climb_down", "dash_down", "fall_down", "hurt_down", "idle_down",
        "jump_down", "walk_down",
    ]  # fmt: skip
    depths = sorted(
        t for a in cat.assets for t in a.detected.get("tags", []) if t.startswith("parallax:")
    )
    assert depths == ["parallax:1", "parallax:2", "parallax:3"]
    tagged = {a.id.rsplit(".", 1)[-1]: a.detected.get("tags") for a in cat.assets}
    assert tagged["save_bench"] == ["save_point"]
    assert tagged["orb_dash"] == ["ability"] and tagged["orb_double_jump"] == ["ability"]


def test_the_side_profile_confirms_the_audit_and_names_the_special_tiles() -> None:
    profiles.install_profile(SIDE_PROFILE)
    cat, issues = _assemble_side()
    assert {a.status for a in cat.assets} == {"CONFIRMED"}
    assert cat.packs[0].profile_id == "rpggen_sample_pack_side"
    assert [i.code for i in issues if i.severity is not Severity.INFO] == []
    cave = cat.asset("sample_pack_side.tiles.cave")
    assert cave is not None
    tiles = catalog.effective(cave)["tile_overrides"]
    assert [k for k, v in tiles.items() if v.get("collision") == {"profile": "ONE_WAY"}] == [
        "4,0", "5,0", "6,0",
    ]  # fmt: skip
    assert [k for k, v in tiles.items() if v.get("collision") == {"profile": "LADDER"}] == [
        "7,0", "7,1",
    ]  # fmt: skip
    assert tiles["4,1"]["custom"] == {"hazard": True}
    assert tiles["5,1"]["custom"] == {"breakable": True}
    ref = config.PackRef("sample_pack_side", str(SIDE), "0" * 64, "folder")
    cfg = config.default_for("Sample Cave", [ref], archetype="metroidvania")
    assert requirements.check(cat, cfg) == []
    starter = mapping.default_starter(cat, "metroidvania")
    assert set(starter) == {"player", "ground", "enemy", "boss", "chest", "npc", "portrait"}
    assert mapping.missing_required(cat, "metroidvania", set()) == []


# ------------------------------------------------------------------------ the two entries


def _window_with(qtbot, tmp_path, monkeypatch, available: bool) -> MainWindow:
    from rpggen import features

    monkeypatch.setattr(features, "METROIDVANIA_AVAILABLE", available)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir(exist_ok=True)
    win = MainWindow(state_mod.WizardState(), default_pages(), show_welcome=True)
    qtbot.addWidget(win)
    win.show()
    return win


def _state_facts(win: MainWindow) -> dict:
    """What *Try the sample* filled in, without the folders of this test run."""
    state = win.state
    return {
        "name": state.project_name,
        "packs": [p.name for p in state.pack_sources],
        "target": state.target.name if state.target else None,
        "archetype": state.archetype,
        "config": state.config.to_json() if state.config else None,
        "statuses": sorted({a.status for a in state.catalog.assets}) if state.catalog else None,
    }


def test_the_welcome_card_is_the_plain_button_while_the_metroidvania_is_off(
    qtbot, tmp_path, monkeypatch
) -> None:
    win = _window_with(qtbot, tmp_path, monkeypatch, available=False)
    card = win.welcome.sample_card
    assert card.menu() is None and win.welcome.sample_side_action is None
    assert card.toolTip() == "Fills in the bundled sample pack and goes straight to the options"
    card.click()
    assert win.current_index == OPTIONS_INDEX
    assert win.state.pack_sources == [SAMPLE] and win.state.archetype == "turn_based"


def test_the_welcome_card_offers_both_samples_when_the_metroidvania_is_on(
    qtbot, tmp_path, monkeypatch
) -> None:
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True)
    welcome = win.welcome
    menu = welcome.sample_card.menu()
    assert menu is not None
    assert [a.text() for a in menu.actions()] == ["Top-down village", "Side-view cave"]
    welcome.sample_side_action.trigger()
    assert not win.welcome_visible
    state = win.state
    assert state.pack_sources == [SIDE]
    assert state.project_name == "Sample Cave"
    assert state.target == tmp_path / "Documents" / "rpggen-sample-1"
    assert state.catalog is not None
    assert {a.status for a in state.catalog.assets} == {"CONFIRMED"}


def test_the_first_entry_fills_the_same_state_with_the_flag_on_or_off(
    qtbot, tmp_path, monkeypatch
) -> None:
    """The top-down sample is today's path, whichever way it is reached."""
    facts = []
    for n, available in enumerate((False, True, True)):
        folder = tmp_path / f"run{n}"
        folder.mkdir()
        win = _window_with(qtbot, folder, monkeypatch, available=available)
        if n == 2:
            win.welcome.sample_top_action.trigger()  # from the menu
        else:
            win.welcome.sample_card.click()  # the card itself
        assert win.current_index == OPTIONS_INDEX
        found = _state_facts(win)
        for pack in found["config"]["packs"]:
            pack.pop("source", None)  # an absolute path of this checkout
        facts.append(found)
    assert facts[0] == facts[1] == facts[2]
    assert facts[0]["name"] == "Sample RPG" and facts[0]["archetype"] == "turn_based"
    assert facts[0]["packs"] == ["sample_pack"]
