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
    page.sample_actions["top"].trigger()  # the button lists the samples (T16.17)
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


def _window_with(
    qtbot, tmp_path, monkeypatch, available: bool, arcade: bool = False, m17: bool = False
) -> MainWindow:
    """A window with the side-view sample on offer or not, the three arcade samples of M16
    (on since the gate of 1.4) only when ``arcade``, and the farm and the isometric view of
    M17 with their two samples only when ``m17``."""
    from rpggen import features

    monkeypatch.setattr(features, "METROIDVANIA_AVAILABLE", available)
    for flag in ("SHMUP_AVAILABLE", "RUN_AND_GUN_AVAILABLE", "RACING_AVAILABLE"):
        monkeypatch.setattr(features, flag, arcade)
    for flag in ("FARM_AVAILABLE", "ISOMETRIC_AVAILABLE"):
        monkeypatch.setattr(features, flag, m17)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    monkeypatch.setattr(ProjectPage, "documents_dir", lambda self: tmp_path / "Documents")
    (tmp_path / "Documents").mkdir(exist_ok=True)
    # the welcome card starts a generation (T15.22): these tests look at what it filled in
    from rpggen.gui.pages.generate_page import GeneratePage

    monkeypatch.setattr(GeneratePage, "start", lambda self: STARTED.append(self.state))
    STARTED.clear()
    win = MainWindow(state_mod.WizardState(), default_pages(), show_welcome=True)
    qtbot.addWidget(win)
    win.show()
    return win


STARTED: list = []  # the states the (replaced) Generate page was asked to start with
GENERATE_INDEX = OPTIONS_INDEX + 1


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
    assert card.toolTip() == "Fills in the bundled sample pack, generates it and shows the result"
    card.click()
    assert win.current_index == GENERATE_INDEX and [win.state] == STARTED
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
        assert win.current_index == GENERATE_INDEX
        found = _state_facts(win)
        for pack in found["config"]["packs"]:
            pack.pop("source", None)  # an absolute path of this checkout
        facts.append(found)
    assert facts[0] == facts[1] == facts[2]
    assert facts[0]["name"] == "Sample RPG" and facts[0]["archetype"] == "turn_based"
    assert facts[0]["packs"] == ["sample_pack"]


# ------------------------------------------------------------------------ two clicks (T15.22)


class _FakeWorkerSignals:
    def __init__(self) -> None:
        from PySide6.QtCore import QObject, Signal

        class Signals(QObject):
            finished = Signal(object)
            failed = Signal(object)

        self.q = Signals()


def test_the_welcome_sample_lands_on_generate_with_the_run_started(
    qtbot, tmp_path, monkeypatch
) -> None:
    """From the welcome view the sample is walked through every page (each writes its defaults)
    to the Generate page, where the run starts and a banner says what is used."""
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True)
    entered: list[str] = []
    for page in win.pages:
        original = page.enter
        page.enter = lambda state, o=original, p=page: (entered.append(p.title), o(state))[1]
    win.welcome.sample_card.click()
    assert win.current_index == GENERATE_INDEX and not win.welcome_visible
    assert entered[:6] == ["Project", "Archetype", "Audit", "Mapping", "Options", "Generate"]
    assert [win.state] == STARTED and win.state.sample_run
    assert win.state.config is not None and win.state.config.project_name == "Sample RPG"
    assert win.state.catalog is not None  # the Options page wrote its defaults on the way
    generate = win.current_page
    assert "default options" in generate.sample_banner.text()
    assert "nothing was written yet" in generate.sample_banner.text()


def test_back_is_open_during_a_sample_run_until_it_writes(qtbot, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    from rpggen.gui.pages.generate_page import PHASES, GeneratePage

    win = _window_with(qtbot, tmp_path, monkeypatch, available=True)
    win.welcome.sample_card.click()
    generate = win.current_page
    assert isinstance(generate, GeneratePage)
    cancelled: list[bool] = []

    class Worker:  # a run that is on, and stops when it is cancelled
        def cancel(self) -> None:
            cancelled.append(True)
            generate.running = False

        signals = _FakeWorkerSignals().q

    generate.worker = Worker()  # type: ignore[assignment]
    generate.running = True
    generate._on_progress("build", PHASES.index("build") + 1, len(PHASES))
    win.refresh()
    assert generate.back_allowed_while_running() and win.back_button.isEnabled()
    assert not generate.sample_banner.isHidden()
    # the Cancel of the page is in the window's bar, where Next was
    assert generate.cancel_button.isVisibleTo(win) and not win.next_button.isVisibleTo(win)
    assert generate.cancel_button.parentWidget() is win.next_button.parentWidget()
    assert generate.cancel_button.objectName() == "generateCancel"
    # ... but not once the run writes the project
    generate._on_progress("promote", PHASES.index("promote") + 1, len(PHASES))
    QApplication.processEvents()
    assert not generate.back_allowed_while_running() and not win.back_button.isEnabled()
    assert generate.stop_for_back() is False and cancelled == []
    generate._on_progress("smoke", PHASES.index("smoke") + 1, len(PHASES))
    win.refresh()
    win.back_button.click()  # stops the run and shows the options
    assert cancelled == [True] and win.current_index == OPTIONS_INDEX
    assert not win.state.sample_run  # the options are the user's choice from here on
    # a run the user started from the Options page has no banner and no open Back
    generate.running = True
    generate._on_progress("build", PHASES.index("build") + 1, len(PHASES))
    assert not generate.back_allowed_while_running()
    generate.running = False  # nothing runs when the window closes
    generate.worker = None


def test_the_project_pages_sample_button_still_stops_at_the_options(
    qtbot, tmp_path, monkeypatch
) -> None:
    """A user who is in the wizard is choosing a pack, not asking for a result."""
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True)
    win.welcome.own_card.click()
    win.pages[0].sample_actions["top"].trigger()  # the list of the button (T16.17)
    assert win.current_index == OPTIONS_INDEX and STARTED == []
    assert not win.state.sample_run
    assert win.next_button.text() == "Generate" and win.next_button.isEnabled()


# ------------------------------------------------------------------------ the arcade samples (T16.17)

# kind of the tool -> (folder, profile, the kind of game, the roles it must fill, sound slots)
ARCADE_SAMPLES = {
    "shmup": (
        "sample_pack_shmup",
        "sample_shmup.rpgprofile.json",
        "shmup",
        {"PLAYER", "ENEMY", "BOSS", "PROJECTILE", "EXPLOSION", "POWERUP", "HAZARD", "BACKGROUND"},
        {"music_stage", "music_boss", "music_title", "sfx_shoot", "sfx_explosion", "sfx_bomb"},
    ),
    "gun": (
        "sample_pack_gun",
        "sample_gun.rpgprofile.json",
        "run_and_gun",
        {"PLAYER", "GROUND", "ENEMY", "BOSS", "PROJECTILE", "EXPLOSION", "POWERUP", "HAZARD",
         "BACKGROUND", "DECORATION", "ITEM"},
        {"music_stage", "music_boss", "sfx_shoot", "sfx_explosion", "sfx_grenade", "sfx_grapple"},
    ),
    "race": (
        "sample_pack_race",
        "sample_race.rpgprofile.json",
        "racing",
        {"VEHICLE", "GROUND", "ENEMY", "HAZARD", "POWERUP", "DECORATION"},
        {"music_race", "music_results", "sfx_engine", "sfx_skid", "sfx_bump", "sfx_lap"},
    ),
}  # fmt: skip


def _assemble(folder: str):
    opened = archive.open_pack(ROOT / folder, set(), pack_id=folder)
    inv = inventory.build_inventory(opened)
    cat, issues, _gen = catalog.assemble([(opened, inv)], None, [])
    return cat, issues


@pytest.mark.parametrize("kind", sorted(ARCADE_SAMPLES))
def test_an_arcade_sample_is_cc0_documented_small_and_what_the_tool_makes(
    tmp_path: Path, kind: str
) -> None:
    folder, profile, _archetype, _roles, _slots = ARCADE_SAMPLES[kind]
    pack = ROOT / folder
    assert paths.sample_pack_dir(folder) == pack and pack.is_dir()
    assert "CC0" in (pack / "LICENSE.txt").read_text(encoding="utf-8")
    source = (pack / "SOURCE.txt").read_text(encoding="utf-8")
    for png in pack.rglob("*.png"):
        rel = png.relative_to(pack).as_posix()
        stem = png.stem.split("_")[0]
        assert (
            rel in source
            or f"{png.parent.name}/*.png" in source
            or f"{png.parent.name}/{stem}_*.png" in source
            or f"{png.parent.name}/{'_'.join(png.stem.split('_')[:2])}_*.png" in source
        ), rel
    size = sum(p.stat().st_size for p in pack.rglob("*") if p.is_file())
    assert size < 200_000, f"{folder} is {size} bytes"
    tool = _build_tool()
    tool.build_arcade_pack(kind, tmp_path / "fresh")
    tool.build_arcade_pack(kind, tmp_path / "again")
    name, _title, profile_name, _id, images, sounds, _source, _edit = tool.ARCADE_PACKS[kind]
    assert (name, profile_name) == (folder, profile)
    assert sorted(p.relative_to(pack).as_posix() for p in pack.rglob("*.png")) == sorted(images)
    assert sorted(p.relative_to(pack).as_posix() for p in pack.rglob("*.wav")) == sorted(sounds)
    for rel in images:
        a = Image.open(pack / rel).convert("RGBA")
        b = Image.open(tmp_path / "fresh" / rel).convert("RGBA")
        assert a.size == b.size and ImageChops.difference(a, b).getbbox() is None, rel
        assert (tmp_path / "fresh" / rel).read_bytes() == (tmp_path / "again" / rel).read_bytes()
    for rel in sounds:
        assert (pack / rel).read_bytes() == (tmp_path / "fresh" / rel).read_bytes(), rel
    for text in ("LICENSE.txt", "SOURCE.txt"):
        assert (pack / text).read_bytes() == (tmp_path / "fresh" / text).read_bytes(), text


@pytest.mark.parametrize("kind", sorted(ARCADE_SAMPLES))
def test_an_arcade_sample_is_catalogued_without_an_edit(kind: str) -> None:
    """The golden holds, and with the pack's own profile (what *Try the sample* installs) the
    audit is all confirmed and the kind has nothing to draw and nothing to ask for."""
    from rpggen import jsonio
    from rpggen.core import arcade_kit, sound_slots

    folder, profile, archetype, roles, slots = ARCADE_SAMPLES[kind]
    cat, _issues = _assemble(folder)
    golden = ROOT / "tests" / "golden" / f"{folder}.catalog.json"
    assert jsonio.dumps(cat.to_json()) == golden.read_text(encoding="utf-8")
    ref = config.PackRef(folder, str(ROOT / folder), "0" * 64, "folder")
    cfg = config.default_for("Sample", [ref], archetype=archetype)
    # without the profile nothing stops a run: at most a note
    plain = requirements.check(cat, cfg)
    assert [i.code for i in plain if i.severity is Severity.ERROR] == []

    profiles.install_profile(ROOT / folder / profile)
    cat, issues = _assemble(folder)
    assert {a.status for a in cat.assets} == {"CONFIRMED"}
    assert cat.packs[0].profile_id == f"rpggen_{folder}"
    assert [i.code for i in issues if i.severity is not Severity.INFO] == []
    assert roles <= {catalog.effective(a)["role"] for a in cat.assets}
    assert requirements.check(cat, cfg) == [], "no note at all: nothing is missing or drawn"
    assert arcade_kit.lacking(cat, archetype) == []
    assert mapping.missing_required(cat, archetype, set()) == []
    filled = sound_slots.default_sounds(cat, archetype)
    assert slots <= set(filled), sorted(slots - set(filled))


def test_what_each_arcade_sample_is_made_of() -> None:
    star, _i = _assemble("sample_pack_shmup")
    assert catalog.VIEW_SHMUP in star.packs[0].warnings
    ship = catalog.effective(star.asset("sample_pack_shmup.ships.player_ship"))
    assert ship["role"] == "PLAYER" and ship["frame"] == [24, 24]
    enemies = [a for a in star.assets if catalog.effective(a)["role"] == "ENEMY"]
    assert len(enemies) == 6
    layers = sorted(t for a in star.assets for t in a.detected.get("tags", []) if "parallax" in t)
    assert layers == ["parallax:1", "parallax:3"]

    profiles.install_profile(ROOT / "sample_pack_gun" / "sample_gun.rpgprofile.json")
    jungle, _i = _assemble("sample_pack_gun")
    assert catalog.pack_view(jungle.packs[0]) == "side"
    soldier = next(a for a in jungle.assets if catalog.effective(a)["role"] == "PLAYER")
    assert sorted(catalog.effective(soldier)["animations"]) == [
        "death_down", "fall_down", "hurt_down", "idle_down", "jump_down", "shoot_down",
        "walk_down",
    ]  # fmt: skip
    assert requirements.missing_air_animations(soldier) == []
    assert len([a for a in jungle.assets if catalog.effective(a)["role"] == "ENEMY"]) == 5
    boss = next(a for a in jungle.assets if catalog.effective(a)["role"] == "BOSS")
    assert catalog.effective(boss)["frame"] == [64, 64]
    assert sorted(catalog.effective(boss)["animations"]) == ["attack_down", "idle_down"]
    weapons = [a.id.rsplit("_", 1)[-1] for a in jungle.assets if ".pickups." in a.id]
    assert sorted(weapons) == ["flame", "laser", "machinegun", "spread"]
    hook = jungle.asset("sample_pack_gun.items.grapple_hook")
    assert catalog.effective(hook)["role"] == "ITEM" and "grapple" in hook.detected["tags"]
    tiles = catalog.effective(jungle.asset("sample_pack_gun.tiles.jungle"))["tile_overrides"]
    assert [k for k, v in tiles.items() if v.get("collision") == {"profile": "ONE_WAY"}] == [
        "4,0", "5,0", "6,0",
    ]  # fmt: skip
    assert tiles["4,1"]["custom"] == {"hazard": True}

    profiles.install_profile(ROOT / "sample_pack_race" / "sample_race.rpgprofile.json")
    dirt, _i = _assemble("sample_pack_race")
    assert catalog.VIEW_RACING in dirt.packs[0].warnings
    car = catalog.effective(dirt.asset("sample_pack_race.cars.player_car"))
    assert car["role"] == "VEHICLE" and car["headings"] == 16 and car["frame"] == [24, 24]
    rivals = [a for a in dirt.assets if catalog.effective(a)["role"] == "ENEMY"]
    assert len(rivals) == 3 and all(catalog.effective(a)["headings"] == 16 for a in rivals)
    road = dirt.asset("sample_pack_race.tiles.road")
    assert catalog.effective(road)["role"] == "GROUND" and "road" in road.detected["tags"]
    assert mapping.default_starter(dirt, "racing")["vehicle"] == "sample_pack_race.cars.player_car"


def _all_kinds(monkeypatch, on: bool) -> None:
    from rpggen import features

    for flag in ("SHMUP_AVAILABLE", "RUN_AND_GUN_AVAILABLE", "RACING_AVAILABLE"):
        monkeypatch.setattr(features, flag, on)


FIVE = ["Top-down village", "Side-view cave", "Star lane", "Jungle line", "Dirt cup"]


def test_the_samples_that_are_offered_follow_the_kinds_that_can_be_chosen(monkeypatch) -> None:
    from rpggen import features
    from rpggen.gui.models import project_model

    monkeypatch.setattr(features, "METROIDVANIA_AVAILABLE", True)
    assert [s.label for s in project_model.offered_samples()] == FIVE, "all are on since 1.4"
    _all_kinds(monkeypatch, False)
    assert [s.label for s in project_model.offered_samples()] == FIVE[:2]
    monkeypatch.setattr(features, "RACING_AVAILABLE", True)
    assert [s.key for s in project_model.offered_samples()] == ["top", "side", "race"]
    _all_kinds(monkeypatch, True)
    assert [s.label for s in project_model.offered_samples()] == FIVE
    assert [s.archetype for s in project_model.SAMPLES] == [
        "turn_based", "metroidvania", "shmup", "run_and_gun", "racing", "farm", "turn_based",
    ]  # fmt: skip
    for sample in project_model.SAMPLES:
        pack = paths.sample_pack_dir(sample.folder)
        assert pack.is_dir() and (pack / sample.profile).is_file(), sample.key
    assert project_model.sample("nothing").key == "top"


@pytest.mark.parametrize(
    ("key", "folder", "name", "archetype"),
    [
        ("shmup", "sample_pack_shmup", "Star Lane", "shmup"),
        ("gun", "sample_pack_gun", "Jungle Line", "run_and_gun"),
        ("race", "sample_pack_race", "Dirt Cup", "racing"),
    ],
)
def test_the_welcome_menu_lists_five_and_each_lands_on_its_kind(
    qtbot, tmp_path, monkeypatch, key: str, folder: str, name: str, archetype: str
) -> None:
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True, arcade=True)
    welcome = win.welcome
    menu = welcome.sample_card.menu()
    assert menu is not None and [a.text() for a in menu.actions()] == FIVE
    assert welcome.sample_choose_button.toolTip() == "A sample pack for each kind of game"
    welcome.sample_actions[key].trigger()
    assert not win.welcome_visible and win.current_index == GENERATE_INDEX
    state = win.state
    assert [state] == STARTED and state.sample_run
    assert state.pack_sources == [ROOT / folder] and state.project_name == name
    assert state.archetype == archetype
    assert state.config is not None and state.config.archetype == archetype
    assert state.config.input == config.default_input(archetype)
    assert state.catalog is not None
    assert {a.status for a in state.catalog.assets} == {"CONFIRMED"}
    assert mapping.missing_required(state.catalog, archetype, set(state.placeholders)) == []


def test_the_project_pages_sample_button_offers_the_same_list(qtbot, tmp_path, monkeypatch) -> None:
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True, arcade=True)
    win.welcome.own_card.click()
    page = win.pages[0]
    assert page.sample_menu is not None
    assert [a.text() for a in page.sample_menu.actions()] == FIVE
    page.sample_button.click()  # opens the list: nothing is filled in yet
    assert page.sample_menu.isVisible() and win.current_index == 0 and win.state.catalog is None
    page.sample_menu.close()
    page.sample_actions["race"].trigger()
    assert win.current_index == OPTIONS_INDEX and STARTED == []
    assert not win.state.sample_run
    assert win.state.archetype == "racing" and win.state.config.archetype == "racing"
    assert win.state.pack_sources == [ROOT / "sample_pack_race"]
    assert win.current_page.arcade_box is not None
    assert win.current_page.arcade_box.objectName() == "racingBox"


# ------------------------------------------------------------------------ the samples of M17 (T17.17)

ISOMETRIC = config.PROJECTION_ISOMETRIC
# kind of the tool -> (folder, profile, the kind of game, its view, the roles it must fill, the
# sound slots it must fill)
M17_SAMPLES = {
    "farm": (
        "sample_pack_farm",
        "sample_farm.rpgprofile.json",
        "farm",
        config.PROJECTION_TOP_DOWN,
        {"PLAYER", "GROUND", "ROAD", "WATER", "WALL", "NPC", "CROP", "ANIMAL", "TOOL", "ITEM",
         "DECORATION", "EFFECT", "UI", "PORTRAIT"},
        {"music_spring", "music_summer", "music_autumn", "music_winter", "music_map", "sfx_hoe",
         "sfx_water", "sfx_plant", "sfx_harvest", "sfx_sell", "sfx_animal", "sfx_rooster",
         "sfx_ui_confirm"},
    ),
    "iso": (
        "sample_pack_iso",
        "sample_iso.rpgprofile.json",
        "turn_based",
        ISOMETRIC,
        {"PLAYER", "GROUND", "ROAD", "WATER", "WALL", "BUILDING", "DECORATION", "NPC", "ENEMY",
         "ITEM", "UI", "PORTRAIT"},
        {"music_map", "music_battle", "sfx_ui_move", "sfx_ui_confirm", "sfx_ui_cancel", "sfx_hit",
         "sfx_attack", "sfx_pickup", "sfx_chest", "sfx_step"},
    ),
}  # fmt: skip


def _documented(rel: str, source: str) -> bool:
    """True when ``SOURCE.txt`` lists the file: by its path, or by a line whose first word is a
    pattern for it (``PNG/path*.png``, ``sfx/*.wav``)."""
    import fnmatch

    firsts = [line.split()[0] for line in source.splitlines() if line[:1].strip()]
    return any(fnmatch.fnmatchcase(rel, first) for first in firsts)


@pytest.mark.parametrize("kind", sorted(M17_SAMPLES))
def test_a_sample_of_m17_is_cc0_documented_small_and_what_the_tool_makes(
    tmp_path: Path, kind: str
) -> None:
    from rpggen import jsonio

    folder, profile, _archetype, _view, _roles, _slots = M17_SAMPLES[kind]
    pack = ROOT / folder
    assert paths.sample_pack_dir(folder) == pack and pack.is_dir()
    assert "CC0" in (pack / "LICENSE.txt").read_text(encoding="utf-8")
    source = (pack / "SOURCE.txt").read_text(encoding="utf-8")
    files = sorted(p.relative_to(pack).as_posix() for p in pack.rglob("*") if p.is_file())
    for rel in files:
        if rel.endswith((".png", ".wav")):
            assert _documented(rel, source), rel
    size = sum((pack / rel).stat().st_size for rel in files)
    assert size < 200_000, f"{folder} is {size} bytes"
    tool = _build_tool()
    name, _title, profile_name, _id, images, sounds, _source, _edit = tool.ARCADE_PACKS[kind]
    texts = ["LICENSE.txt", "SOURCE.txt", *tool.PACK_TEXTS.get(kind, {})]
    assert (name, profile_name) == (folder, profile)
    # nothing is in the folder that the tool does not write
    assert files == sorted([*images, *sounds, *texts, profile])
    tool.build_arcade_pack(kind, tmp_path / "fresh")
    tool.build_arcade_pack(kind, tmp_path / "again")
    for rel in images:
        a = Image.open(pack / rel).convert("RGBA")
        b = Image.open(tmp_path / "fresh" / rel).convert("RGBA")
        assert a.size == b.size and ImageChops.difference(a, b).getbbox() is None, rel
        assert (tmp_path / "fresh" / rel).read_bytes() == (tmp_path / "again" / rel).read_bytes()
    for rel in [*sounds, *texts]:
        assert (pack / rel).read_bytes() == (tmp_path / "fresh" / rel).read_bytes(), rel
        assert (pack / rel).read_bytes() == (tmp_path / "again" / rel).read_bytes(), rel
    # the profile is the audit of the pack, made by the tool: twice the same, and what is kept
    # (compared without the hashes of the pictures, which are those of the PNG files)
    made = [
        tool.build_arcade_profile(kind, tmp_path / again, tmp_path / again / profile)
        for again in ("fresh", "again")
    ]
    kept = jsonio.read(pack / profile)
    assert made[0] == made[1]
    for data in (made[0], kept):
        data["fingerprint"] = sorted(data["fingerprint"]["required_files"])
    assert made[0] == kept


@pytest.mark.parametrize("kind", sorted(M17_SAMPLES))
def test_a_sample_of_m17_is_catalogued_without_an_edit(kind: str) -> None:
    """The golden holds; without the profile nothing stops a run; and with the pack's own
    profile (what *Try the sample* installs) the audit is confirmed and the kind, in the view of
    the sample, has nothing to draw and nothing to ask for."""
    from rpggen import jsonio
    from rpggen.core import farm_kit, iso_kit, sound_slots

    folder, profile, archetype, view, roles, slots = M17_SAMPLES[kind]
    cat, _issues = _assemble(folder)
    golden = ROOT / "tests" / "golden" / f"{folder}.catalog.json"
    assert jsonio.dumps(cat.to_json()) == golden.read_text(encoding="utf-8")
    ref = config.PackRef(folder, str(ROOT / folder), "0" * 64, "folder")
    cfg = config.default_for("Sample", [ref], archetype=archetype)
    cfg.projection = view
    plain = requirements.check(cat, cfg)
    assert [i.code for i in plain if i.severity is not Severity.INFO] == []
    # what the names alone do not say is drawn, and said: the two soil tiles of the farm are
    # one tile each (no grid to measure, so they are read as pictures), and the slime of the
    # isle is a sheet in a folder of characters (read as a villager)
    assert (
        sorted(i.detail["thing"] for i in plain)
        == {
            "farm": ["tilled soil", "watered soil"],
            "iso": ["enemy"],
        }[kind]
    )
    assert {i.code for i in plain} == {"ASSET-031"}

    profiles.install_profile(ROOT / folder / profile)
    cat, issues = _assemble(folder)
    # the farmer's four strips with a tool are read as the farmer's and left unused (T17.10)
    unused = {"farm": {"UNUSED"}, "iso": set()}[kind]
    assert {a.status for a in cat.assets} == {"CONFIRMED"} | unused
    assert cat.packs[0].profile_id == f"rpggen_{folder}"
    assert [i.code for i in issues if i.severity is not Severity.INFO] == []
    assert roles <= {catalog.effective(a)["role"] for a in cat.assets}
    assert requirements.check(cat, cfg) == [], "no note at all: nothing is missing or drawn"
    drawn = farm_kit.lacking(cat, view) if kind == "farm" else iso_kit.lacking(cat, view)
    assert drawn == []
    assert mapping.missing_required(cat, archetype, set(), view) == []
    filled = sound_slots.default_sounds(cat, archetype)
    assert slots <= set(filled), sorted(slots - set(filled))


def test_what_green_acre_is_made_of() -> None:
    from rpggen.core import animal_plan, crop_plan, farm_kit, forage_plan, orchestrator

    name = "sample_pack_farm"
    plain, _i = _assemble(name)
    assert catalog.VIEW_FARM in plain.packs[0].warnings, "the names say it is a farming pack"
    farmer = plain.asset(f"{name}.characters.farmer.farmer_walk_down_16x24_4frames")
    assert catalog.effective(farmer)["role"] == "PLAYER", "read without the profile"
    profiles.install_profile(ROOT / name / "sample_farm.rpgprofile.json")
    cat, _i = _assemble(name)
    farmer = catalog.effective(cat.asset(farmer.id))
    assert farmer["role"] == "PLAYER" and farmer["frame"] == [16, 24]
    assert sorted(farmer["animations"]) == ["walk_down", "walk_left", "walk_right", "walk_up"]
    # the four strips of the farmer with a tool: the farmer's, unused (nothing plays them yet)
    strips = {
        tag.split(":", 1)[1]: a
        for a in cat.assets
        for tag in catalog.effective(a).get("tags", [])
        if tag.startswith("use_anim:")
    }
    assert sorted(strips) == ["axe", "hoe", "sickle", "water"]
    for strip in strips.values():
        assert strip.status == "UNUSED" and catalog.effective(strip)["role"] == "NONE"
        assert (
            f"of:{name}.characters.farmer.farmer_walk_down_16x24_4frames" in strip.detected["tags"]
        )
    # four crops that grow, by their names, two in every season
    crops = {
        a.id.rsplit(".", 1)[-1].split("_")[0]: catalog.effective(a)
        for a in cat.assets
        if catalog.effective(a).get("role") == "CROP"
    }
    assert {k: v["stages"] for k, v in crops.items()} == {
        "corn": 6, "wheat": 5, "tomato": 7, "turnip": 4,
    }  # fmt: skip
    assert {v["usage"] for v in crops.values()} == {"growth_strip"}
    section = crop_plan.plan({}, 12345, crop_plan.facts_of(cat))
    assert crop_plan.per_season(section) == {"spring": 2, "summer": 2, "autumn": 2, "winter": 2}
    # soil and watered soil of its own, one tile each; the grass once a season
    for stand_in in (farm_kit.SOIL, farm_kit.WATERED):
        own = farm_kit.own_asset(cat, stand_in)
        assert own is not None and catalog.effective(own)["size"] == [16, 16]
    assert catalog.season_groups(cat) == {
        f"{name}.tilesets.spring.grass": {
            season: f"{name}.tilesets.{season}.grass"
            for season in ("spring", "summer", "autumn", "winter")
        }
    }
    # a hen and a cow that walk and sleep; five tools; a fish and two things to find
    animals = animal_plan.facts_of(cat, ("coop", "barn"))["animals"]
    assert [(a["kind"], a["walk"], a["sleep"]) for a in animals] == [
        ("cow", True, True), ("hen", True, True),
    ]  # fmt: skip
    tools = [a.id.rsplit(".", 1)[-1] for a in cat.assets if catalog.effective(a)["role"] == "TOOL"]
    assert sorted(tools) == ["axe", "fishing_rod", "hoe", "sickle", "watering_can"]
    found = forage_plan.facts_of(cat)
    assert [f["name"] for f in found["fish"]] == ["perch"]
    assert [f["name"] for f in found["forage"]] == ["mushroom", "wild_berries"]
    assert len([a for a in cat.assets if catalog.effective(a)["role"] == "NPC"]) == 3
    rain = catalog.effective(cat.asset(f"{name}.weather.rain_64x64_3frames"))
    assert rain["role"] == "EFFECT" and "weather" in rain["tags"] and rain["frame"] == [64, 64]
    # the three buildings are objects of a sheet, which is what the planner sees: the house is
    # the one a map takes, and it is as large as the plan takes a farmhouse to be
    buildings = {o.name: o for o in cat.objects if o.role == "BUILDING"}
    assert sorted(buildings) == ["house", "yard_barn", "yard_coop"]
    assert "barn" in buildings["yard_barn"].tags and "coop" in buildings["yard_coop"].tags
    starter = mapping.default_starter(cat, "farm")
    assert starter["building"] == f"{name}.objects.farmyard#house"
    assert starter["ground"] == f"{name}.tilesets.spring.grass", "the first season of the four"
    assert starter["chest"] == f"{name}.items.chest"
    assert starter["player"] == f"{name}.characters.farmer.farmer_walk_down_16x24_4frames"
    ref = config.PackRef(name, str(ROOT / name), "0" * 64, "folder")
    cfg = config.default_for("Sample", [ref], archetype="farm")
    cfg.starter = starter
    facts = orchestrator.farm_facts(cfg, cat)
    assert facts["house"] == {"size": [6, 4], "door": [2, 4]} and facts["water"] is True


def test_what_stone_isle_is_made_of() -> None:
    from rpggen.core import map_preview

    name = "sample_pack_iso"
    said = (ROOT / name / "Tile information.txt").read_text(encoding="utf-8")
    assert "Image size : 80 x 96 px" in said and "Tile size  : 40 x 28 px" in said
    plain, _i = _assemble(name)
    # the diamond is measured, and it is not twice as wide as high: 28 is the diamond with the
    # 6 px of earth under it, as the text files of such packs say it
    assert catalog.isometric_footprint(plain.packs[0]) == (40, 22, "tile_information")
    assert catalog.pack_view(plain.packs[0]) == "isometric"
    assert catalog.VIEW_RACING not in plain.packs[0].warnings
    profiles.install_profile(ROOT / name / "sample_iso.rpgprofile.json")
    cat, _i = _assemble(name)
    facets = {a.id.split(".", 1)[1]: catalog.effective(a) for a in cat.assets}
    tiles = {k: v for k, v in facets.items() if v.get("usage") == "iso_tile"}
    assert len(tiles) == 42
    for key, tile in tiles.items():
        assert tile["footprint"] == [40, 22] and tile["canvas"] == [80, 96], key
        assert tile["origin"] == [40, 79] and tile["projection"] == ISOMETRIC, key
    flat = sorted(k for k, v in tiles.items() if v["role"] == "GROUND")
    assert flat == ["png.grass", "png.grassflowers", "png.groundstone"]
    assert all(tiles[k]["rise"] == 0 and "joins" not in tiles[k] for k in flat)

    def joins(prefix: str, role: str) -> list[str]:
        found = {k: v for k, v in tiles.items() if k.startswith(prefix) and "joins" in v}
        assert {v["role"] for v in found.values()} == {role}, prefix
        return sorted("".join(v["joins"]) for v in found.values())

    # a path that can be laid any way: its ends, straights, corners, forks and its crossing
    assert joins("png.path", "ROAD") == sorted(
        ["n", "e", "s", "w", "ns", "ew", "ne", "es", "sw", "nw", "nes", "esw", "nsw", "new",
         "nesw"]
    )  # fmt: skip
    assert joins("png.water", "WATER") == sorted(
        ["ne", "es", "sw", "nw", "nes", "esw", "nsw", "new", "nesw"]
    )
    assert tiles["png.water"]["role"] == "WATER" and "joins" not in tiles["png.water"]
    assert joins("png.wall", "WALL") == sorted(
        ["n", "e", "s", "w", "ns", "ew", "ne", "es", "sw", "nw"]
    )
    assert all(v["rise"] > 0 for k, v in tiles.items() if k.startswith("png.wall"))
    # a block that rises, turned four ways: four pictures of one tile
    blocks = [tiles[f"png.stoneblock_{turn}"] for turn in range(4)]
    assert [b["turn"] for b in blocks] == [0, 1, 2, 3] and {b["rise"] for b in blocks} == {14}
    assert all(f"variant_of:{name}.png.stoneblock_0" in b["tags"] for b in blocks[1:])
    # the house stands on four diamonds, and the planner sees it; trees and a rock on one
    houses = [facets[f"png.house_{turn}"] for turn in range(4)]
    assert all(h["role"] == "BUILDING" and h["stands_on"] == [2, 2] for h in houses)
    assert [h["turn"] for h in houses] == [0, 1, 2, 3]
    assert map_preview.building_info_for(cat, "", ISOMETRIC) == {"size": [2, 2], "door": [0, 2]}
    for key in ("png.treeoak", "png.treepine", "png.rock"):
        assert facets[key]["role"] == "DECORATION" and facets[key]["stands_on"] == [1, 1], key
    chest = facets["items.chest"]
    assert chest["role"] == "ITEM" and "chest" in chest["tags"] and chest["stands_on"] == [1, 1]
    # the people are seen from the front and walk the four ways of the screen, which is what
    # an isometric game shows of them (its facing is one of four, by the screen)
    roles = {"hero": "PLAYER", "villager_fisher": "NPC", "villager_mason": "NPC", "slime": "ENEMY"}
    for who, role in roles.items():
        sheet = facets[f"characters.{who}"]
        assert sheet["role"] == role and sheet["directions"] == 4, who
        assert "projection" not in sheet, "a sheet of a character is no isometric picture"
        for way in ("down", "left", "right", "up"):
            assert f"walk_{way}" in sheet["animations"], (who, way)
    starter = mapping.default_starter(cat, "turn_based", ISOMETRIC)
    assert starter["ground"] == f"{name}.png.grass"
    assert starter["building"] == f"{name}.png.house_0", "the turn with its door to the south"
    assert starter["enemy"] == f"{name}.characters.slime"


SEVEN = [*FIVE, "Green acre", "Stone isle"]


def test_the_two_samples_of_m17_are_offered_with_their_flags(monkeypatch) -> None:
    from rpggen import features
    from rpggen.gui.models import project_model

    monkeypatch.setattr(features, "METROIDVANIA_AVAILABLE", True)
    _all_kinds(monkeypatch, True)
    assert not features.FARM_AVAILABLE and not features.ISOMETRIC_AVAILABLE
    assert [s.label for s in project_model.offered_samples()] == FIVE, "five, as today"
    monkeypatch.setattr(features, "FARM_AVAILABLE", True)
    assert [s.label for s in project_model.offered_samples()] == [*FIVE, "Green acre"]
    monkeypatch.setattr(features, "FARM_AVAILABLE", False)
    monkeypatch.setattr(features, "ISOMETRIC_AVAILABLE", True)
    assert [s.label for s in project_model.offered_samples()] == [*FIVE, "Stone isle"]
    monkeypatch.setattr(features, "FARM_AVAILABLE", True)
    assert [s.label for s in project_model.offered_samples()] == SEVEN
    assert [s.label for s in project_model.SAMPLES] == SEVEN
    views = {s.key: s.projection for s in project_model.SAMPLES}
    assert views.pop("iso") == ISOMETRIC and set(views.values()) == {config.PROJECTION_TOP_DOWN}
    assert [s.key for s in project_model.SAMPLES if s.archetype == "farm"] == ["farm"]
    # a sample is known by its folder, and its view is for the kinds that have it
    isle = project_model.sample("iso")
    assert project_model.sample_of([paths.sample_pack_dir(isle.folder)]) is isle
    assert project_model.sample_of([ROOT / "test_packs"]) is None
    assert project_model.sample_of([ROOT / isle.folder, SAMPLE]) is None
    assert project_model.sample_view(isle, "turn_based") == ISOMETRIC
    assert project_model.sample_view(isle, "metroidvania") == config.PROJECTION_TOP_DOWN
    assert project_model.sample_view(None, "turn_based") == config.PROJECTION_TOP_DOWN
    # a config the state already has takes the view when it is one of the sample's pack; a
    # config of other packs is left as it is (the pages replace it when the pack has been read)
    state = state_mod.WizardState(archetype="arpg")
    mine = config.PackRef("isle", str(paths.sample_pack_dir(isle.folder)), "0" * 64, "folder")
    state.config = config.default_for("Mine", [mine])
    project_model.try_as(state, isle)
    assert state.archetype == "turn_based" and state.config.projection == ISOMETRIC
    other = config.default_for("Other", [config.PackRef("top", str(SAMPLE), "0" * 64, "folder")])
    state.config = other
    project_model.try_as(state, isle)
    assert other.projection == config.PROJECTION_TOP_DOWN


@pytest.mark.parametrize(
    ("key", "folder", "name", "archetype", "view"),
    [
        ("farm", "sample_pack_farm", "Green Acre", "farm", config.PROJECTION_TOP_DOWN),
        ("iso", "sample_pack_iso", "Stone Isle", "turn_based", ISOMETRIC),
    ],
)
def test_the_welcome_menu_lists_seven_and_each_lands_on_its_kind_and_its_view(
    qtbot, tmp_path, monkeypatch, key: str, folder: str, name: str, archetype: str, view: str
) -> None:
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True, arcade=True, m17=True)
    welcome = win.welcome
    menu = welcome.sample_card.menu()
    assert menu is not None and [a.text() for a in menu.actions()] == SEVEN
    welcome.sample_actions[key].trigger()
    assert not win.welcome_visible and win.current_index == GENERATE_INDEX
    state = win.state
    assert [state] == STARTED and state.sample_run
    assert state.pack_sources == [ROOT / folder] and state.project_name == name
    assert state.archetype == archetype
    assert state.config is not None and state.config.archetype == archetype
    assert state.config.projection == view
    assert state.config.to_json().get("projection", config.PROJECTION_TOP_DOWN) == view
    assert state.config.input == config.default_input(archetype)
    assert state.catalog is not None
    assert {a.status for a in state.catalog.assets} <= {"CONFIRMED", "UNUSED"}
    assert mapping.missing_required(state.catalog, archetype, set(state.placeholders), view) == []
    assert requirements.check(state.catalog, state.config) == []


def test_the_top_down_sample_after_the_isometric_one_is_seen_from_above(
    qtbot, tmp_path, monkeypatch
) -> None:
    """The view goes with the sample, not with the window: the village that is tried after the
    isle is the village it always was."""
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True, arcade=True, m17=True)
    # the samples share an output folder: the second one is asked whether the first is resumed
    monkeypatch.setattr(ProjectPage, "ask_resume", lambda self: False)
    win.welcome.sample_actions["iso"].trigger()
    assert win.state.config.projection == ISOMETRIC
    win.show_welcome_view()
    win.welcome.sample_actions["top"].trigger()
    assert win.current_index == GENERATE_INDEX
    assert win.state.pack_sources == [SAMPLE] and win.state.config.archetype == "turn_based"
    assert win.state.config.projection == config.PROJECTION_TOP_DOWN
    assert "projection" not in win.state.config.to_json()


def test_the_project_pages_list_offers_seven_and_the_isle_comes_with_its_view(
    qtbot, tmp_path, monkeypatch
) -> None:
    win = _window_with(qtbot, tmp_path, monkeypatch, available=True, arcade=True, m17=True)
    win.welcome.own_card.click()
    page = win.pages[0]
    assert page.sample_menu is not None
    assert [a.text() for a in page.sample_menu.actions()] == SEVEN
    page.sample_actions["iso"].trigger()
    assert win.current_index == OPTIONS_INDEX and STARTED == []
    assert not win.state.sample_run
    assert win.state.archetype == "turn_based" and win.state.config.archetype == "turn_based"
    assert win.state.config.projection == ISOMETRIC
    assert win.state.pack_sources == [ROOT / "sample_pack_iso"]
