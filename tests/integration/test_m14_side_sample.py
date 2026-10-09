"""Milestone M14: the metroidvania archetype on the side-view sample pack, on the synthetic
`platformer` pack, on a top-down pack without a jump animation, and the stored plan of rooms
through regenerations (T14.06)."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import (
    archive,
    catalog,
    config,
    godot,
    inventory,
    ledger,
    mapping,
    orchestrator,
    profiles,
    promote,
    requirements,
    world_plan,
    world_repair,
)

pytestmark = [pytest.mark.integration, pytest.mark.metroidvania]

REPO = Path(__file__).resolve().parents[2]
SIDE = REPO / "sample_pack_side"
SYNTH = REPO / "test_packs" / "synthetic"
# A metroidvania has no village to walk, so its sequence is its own from the title screen on
# (the other archetypes append theirs to the shared one).
M14_STEPS = [
    "title_new_game",
    "sign_dialogue",
    "inventory_item",
    "jump_clears_gap",
    "one_way_platform",
    "hazard_hurts_and_returns",
    "gate_blocks",
    "room_transition",
    "npc_talks",
    "guardian_dies",
    "double_jump_reaches_ledge",
    "pickup_dash",
    "dash_crosses_gap",
    "save_station_persist",
    "defeat_returns_to_station",
    "end_room",
]
ROOMS = [f"room_{n:02d}" for n in range(1, 7)]


def _side_config(smoke: bool = True) -> config.GeneratorConfig:
    profiles.install_profile(SIDE / "sample_side.rpgprofile.json")
    opened = archive.open_pack(SIDE, set(), pack_id="sample_pack_side")
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        "Sample Cave",
        [config.pack_ref_from_source(SIDE, "sample_pack_side")],
        archetype="metroidvania",
    )
    cfg.starter = mapping.default_starter(cat, "metroidvania")
    cfg.validation = {"smoke_test": smoke}
    return cfg


def _errors(result) -> list[str]:
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value != "info"]


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(folder)
    try:
        yield folder
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


@pytest.fixture(scope="module")
def sample(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("m14") / "out"
    result = orchestrator.run_in_memory(_side_config(), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _vacuous(target: Path) -> list[str]:
    """The steps that passed only because the world had nothing of theirs."""
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    return re.findall(r"INFO (\w+): .*step passes", log)


# ---------------------------------------------------------------- the side-view sample


def test_the_whole_sequence_passes_for_real_on_the_side_sample(sample: Path) -> None:
    assert _smoke(sample) == M14_STEPS
    assert _vacuous(sample) == []


def test_the_generated_project_has_only_the_metroidvania_archetype(sample: Path) -> None:
    archetypes = sample / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["metroidvania"]
    # the real-time set both action archetypes share is there, the builders of the others are not
    assert (sample / "addons/rpg_runtime/combat/realtime/hitbox.gd").is_file()
    recipes = sample / "generated/builder/recipes"
    assert (recipes / "metroidvania/rooms_recipe.gd").is_file()
    assert not (recipes / "arpg").exists()
    smoke = sample / "generated/builder/smoke"
    assert (smoke / "smoke_steps_metroidvania.gd").is_file()


def test_the_world_is_six_rooms_and_no_starter_map(sample: Path) -> None:
    rooms = sample / "game/maps/rooms"
    assert sorted(p.stem for p in rooms.glob("*.tscn")) == ROOMS
    assert not (sample / "game/maps/starter_map.tscn").exists()
    plan = world_plan.load(sample)
    assert plan is not None
    assert [r["id"] for r in plan["rooms"]["list"]] == ROOMS
    assert plan["rooms"]["abilities"] == ["double_jump", "dash"]
    assert sorted(plan["maps"]) == ROOMS, "every room's hash is recorded"
    assert world_repair.unedited_maps(sample) == [f"game/maps/rooms/{r}.tscn" for r in ROOMS]
    start = (rooms / "room_01.tscn").read_text(encoding="utf-8")
    for node in ('name="Player"', 'name="SaveStation"', 'name="Sign"', 'name="room_01_exit_e"'):
        assert node in start, node
    assert "uid://" not in (sample / "game/data/new_game.tres").read_text(encoding="utf-8")
    # the picture the Results page and the welcome view show: the world seen from the side
    from PIL import Image

    with Image.open(sample / "rpggen/results/starter_map.png") as picture:
        assert picture.width > picture.height > 40
    report = (sample / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "- 6 rooms, 2 abilities, a guardian" in report and "0 areas" not in report
    assert "Archetype metroidvania" in report
    assert "rooms/room_01.tscn" in (sample / "game/data/new_game.tres").read_text(encoding="utf-8")


def test_scenes_and_data_exist(sample: Path) -> None:
    for rel in (
        "generated/scenes/metroidvania/side_camera.tscn",
        "generated/scenes/metroidvania/save_station.tscn",
        "generated/scenes/metroidvania/ability_double_jump.tscn",
        "generated/scenes/metroidvania/ability_dash.tscn",
        "generated/scenes/enemies/guardian.tscn",
        "generated/scenes/ui/hud_metroidvania.tscn",
        "game/data/dialogue/room_sign.tres",
        "game/data/dialogue/end_npc.tres",
    ):
        assert (sample / rel).is_file(), rel
    enemies = sorted(p.stem for p in (sample / "game/data/enemies").glob("*.tres"))
    assert len(enemies) >= 2, enemies
    boot = (sample / "generated/scenes/bootstrap/boot.tscn").read_text(encoding="utf-8")
    assert 'hud_scene = "hud_metroidvania"' in boot


def test_the_text_of_the_archetype_is_in_the_translation_table(sample: Path) -> None:
    rows = (sample / "game/i18n/strings.tsv").read_text(encoding="utf-8")
    for key in ("MV_RESTED", "UI_SAVE_AT_STATION", "UI_NEEDS_ABILITY"):
        assert key in rows, key
    assert "BATTLE_ATTACK" not in rows and "ARPG_SET_QUICK" not in rows


def test_the_input_map_has_jump_and_dash(sample: Path) -> None:
    project = (sample / "project.godot").read_text(encoding="utf-8")
    for action in ("jump=", "dash=", "attack=", "interact="):
        assert action in project, action


def _snapshot(target: Path, folders: tuple[str, ...] = ("game", "generated")) -> dict[str, str]:
    out = {}
    for folder in folders:
        for p in sorted(q for q in (target / folder).rglob("*") if q.is_file()):
            out[p.relative_to(target).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_rebuilding_leaves_every_file_untouched(godot_exe: Path, sample: Path) -> None:
    before = _snapshot(sample)
    run = godot.run_godot(
        godot.find_console_exe(godot_exe),
        sample,
        ["--script", "res://generated/builder/build.gd"],
        timeout_s=godot.BUILD_TIMEOUT_S,
        log_name="rebuild",
        log_dir=sample / "rpggen" / "logs",
    )
    assert run.returncode == 0
    assert _snapshot(sample) == before


# ---------------------------------------------------------------- other packs


def _generate_pack(godot_exe: Path, pack: Path, tmp_path: Path):
    """Like the all-packs test: required roles the pack lacks get debug placeholders."""
    opened = archive.open_pack(pack, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = orchestrator.default_config_for_pack(pack, "Side " + pack.stem, archetype="metroidvania")
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    return orchestrator.run(cfg_path, tmp_path / "out", godot_exe, placeholders=missing)


def test_the_synthetic_platformer_pack_passes_the_sequence(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    result = _generate_pack(godot_exe, SYNTH / "platformer", tmp_path)
    assert result.ok, _errors(result)
    assert _smoke(tmp_path / "out") == M14_STEPS
    # the pack has no sign to read; everything else is tested for real
    assert set(_vacuous(tmp_path / "out")) <= {"sign_dialogue"}
    assert "ASSET-030" not in {i.code for i in result.issues}, "it has jump and fall animations"


def test_a_top_down_pack_plays_with_the_idle_frame_in_the_air(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`basic16` has no side-view tiles, no jump animation and no enemies: the side kit stands
    in for the tiles, ASSET-030 says what the air will look like, and the game still plays."""
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    result = _generate_pack(godot_exe, SYNTH / "basic16", tmp_path)
    assert result.ok, _errors(result)
    codes = {i.code for i in result.issues}
    assert "ASSET-030" in codes
    target = tmp_path / "out"
    assert _smoke(target) == M14_STEPS
    assert set(_vacuous(target)) <= {"sign_dialogue"}
    frames = target / "generated/sprite_frames"
    assert not any("jump" in p.read_text(encoding="utf-8") for p in frames.rglob("*.tres"))
    assert (target / "game/maps/rooms/room_01.tscn").is_file()


# ---------------------------------------------------------------- the stored plan (T14.06)


def _room_hashes(target: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (target / "game/maps/rooms").glob("*.tscn")
    }


def _without_exit(text: str, exit_id: str) -> str:
    """A room's scene text without the exit `exit_id`: its trigger, the trigger's shape and the
    spawn point one arrives at."""
    blocks = re.split(r"(?m)^(?=\[node )", text)
    kept = [
        b
        for b in blocks
        if not (
            b.startswith(f'[node name="{exit_id}" ') or f'parent="Triggers/{exit_id}"' in b[:200]
        )
    ]
    assert len(kept) == len(blocks) - 3, "the exit is a trigger, its shape and a spawn point"
    return "".join(kept)


def test_the_stored_plan_outlives_a_new_seed_a_new_room_and_a_lost_exit(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    target = tmp_path / "out"
    first = orchestrator.run_in_memory(_side_config(smoke=False), None, target, godot_exe)
    assert first.ok, _errors(first)
    assert first.world_repair is None, "a whole world: Godot is not started for a repair"
    built = _room_hashes(target)
    stored = jsonio.read(target / "rpggen/world_plan.json")["rooms"]
    assert sorted(built) == [f"{r}.tscn" for r in ROOMS]

    # another seed: the rooms exist, so the plan is the stored one and nothing is built
    reseeded = _side_config(smoke=False)
    reseeded.seed = first_seed = reseeded.seed + 4242
    again = orchestrator.run_in_memory(reseeded, None, target, godot_exe)
    assert again.ok, _errors(again)
    assert _room_hashes(target) == built
    assert jsonio.read(target / "rpggen/world_plan.json")["rooms"] == stored
    assert again.world_repair is None

    # a room added in the options: it is built beside the room it names, and the room that was
    # there gets the exit to it through the world repair (a room that exists is never rebuilt)
    bigger = _side_config(smoke=False)
    bigger.seed = first_seed
    bigger.starter_map = {"added_rooms": [{"name": "Annex", "join": "Room 6"}]}
    grown = orchestrator.run_in_memory(bigger, None, target, godot_exe)
    assert grown.ok, _errors(grown)
    annex = target / "game/maps/rooms/room_annex.tscn"
    assert annex.is_file()
    rooms = jsonio.read(target / "rpggen/world_plan.json")["rooms"]
    assert [r["id"] for r in rooms["list"]] == [*ROOMS, "room_annex"]
    assert rooms["list"][:6] == stored["list"], "the rooms that were there are as they were"
    repair = grown.world_repair
    assert repair is not None and repair.backup is not None
    assert {line["map"] for line in repair.repairs} == {"game/maps/rooms/room_06.tscn"}
    assert repair.offered == [] and repair.unfixable == []
    assert not [i for i in grown.issues if i.code in ("VAL-027", "VAL-028")], "joined: no warning"
    six = (target / "game/maps/rooms/room_06.tscn").read_text(encoding="utf-8")
    assert 'target_room = "res://game/maps/rooms/room_annex.tscn"' in six
    assert 'target_exit = "room_annex_exit_w"' in six
    assert 'spawn_id = &"room_06_exit_e"' in six
    assert 'name="Hermit"' in six, "what the room had is still there"
    after = _room_hashes(target)
    assert {k for k in built if after[k] != built[k]} == {"room_06.tscn"}
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "## World repairs" in report and "game/maps/rooms/room_06.tscn" in report
    # the mended room is still rpggen's
    assert "game/maps/rooms/room_06.tscn" in world_repair.unedited_maps(target)
    assert world_repair.run(target, godot_exe, dry_run=True).repairs == []

    # an exit removed by hand from a room: the room is its owner's now, so the run only warns
    five = target / "game/maps/rooms/room_05.tscn"
    whole = five.read_text(encoding="utf-8")
    five.write_text(_without_exit(whole, "room_05_exit_e"), encoding="utf-8", newline="\n")
    mine = five.read_bytes()
    warned = orchestrator.run_in_memory(bigger, None, target, godot_exe)
    assert warned.ok, _errors(warned)
    assert "VAL-028" in {i.code for i in warned.issues}
    assert all(i.severity.value != "error" for i in warned.issues if i.code == "VAL-028")
    assert five.read_bytes() == mine, "a room its owner changed is not touched"
    assert warned.world_repair is not None and warned.world_repair.repairs == []
    assert {line["map"] for line in warned.world_repair.offered} == {"game/maps/rooms/room_05.tscn"}

    # the same room as rpggen left it (its hash is the recorded one): the run mends it
    plan = world_plan.load(target)
    assert plan is not None
    digest = ledger.file_hash(five)
    plan["maps"]["room_05"]["map_hash"] = digest
    world_plan.save(target, plan)
    book = promote.load_ledger(target)
    book.files["game/maps/rooms/room_05.tscn"].sha256 = digest
    book.save(target / paths.LEDGER)
    mended = orchestrator.run_in_memory(bigger, None, target, godot_exe)
    assert mended.ok, _errors(mended)
    assert mended.world_repair is not None
    assert {line["map"] for line in mended.world_repair.repairs} == {"game/maps/rooms/room_05.tscn"}
    assert not [i for i in mended.issues if i.code == "VAL-028"]
    text = five.read_text(encoding="utf-8")
    assert 'spawn_id = &"room_05_exit_e"' in text
    assert 'target_room = "res://game/maps/rooms/room_06.tscn"' in text
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "game/maps/rooms/room_05.tscn" in report
