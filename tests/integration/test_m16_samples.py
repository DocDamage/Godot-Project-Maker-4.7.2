"""Milestone M16 (T16.18): the three sample packs as their kinds, made the way *Try the sample*
makes them (the bundled profile, the starter the catalog suggests, the default options): the
*Star lane* pack as a shoot 'em up, the *Jungle line* pack as a run and gun (and again as
*Bionic*: the grapple, and no jump) and the *Dirt cup* pack as a racing game. Each is played
through by its own smoke sequence, leaves no note, regenerates without a change, and what it
wrote follows the schemas."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

# the sequence of each kind is listed once, in the tests of the kind (this folder is on the path)
from test_m16_racing import STEPS as RACING_STEPS
from test_m16_run_and_gun import STEPS as RUN_AND_GUN_STEPS
from test_m16_shmup import STEPS as SHMUP_STEPS

from rpggen import cli, jsonio, paths, schema
from rpggen.core import (
    archive,
    catalog,
    config,
    inventory,
    mapping,
    orchestrator,
    profiles,
    stage_plan,
    world_plan,
)
from rpggen.gui.models import project_model

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
# What a sample may say beside its errors and warnings, of which it has none: that its profile
# was found, and a picture drawn for it where the pack is minimal on purpose. What the computer
# lacks (ENV-: export templates, long paths) is not the sample's.
NOTES = {"ADAPT-003", "ASSET-031"}
Made = tuple[Path, orchestrator.RunResult]


# what a report says of the computer, not of the pack: a missing tool (ENV-) or a Godot
# that crashed while importing and was run again (BUILD-006)
MACHINE_NOTES = ("ENV-", "BUILD-006")


def _config(key: str, **starter_map) -> config.GeneratorConfig:
    sample = project_model.sample(key)
    assert sample.key == key
    pack = REPO / sample.folder
    profiles.install_profile(pack / sample.profile)
    opened = archive.open_pack(pack, set(), pack_id=sample.folder)
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        sample.name,
        [config.pack_ref_from_source(pack, sample.folder)],
        archetype=sample.archetype,
    )
    cfg.starter = mapping.default_starter(cat, sample.archetype)
    cfg.starter_map = dict(starter_map)
    return cfg


def _errors(result: orchestrator.RunResult) -> list[str]:
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
def made(
    godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory
) -> Callable[..., Made]:
    """``made(key, **options)``: the sample generated once for the tests of this file."""
    done: dict[str, Made] = {}

    def make(key: str, **starter_map) -> Made:
        name = key + "".join(f"_{k}" for k in sorted(starter_map))
        if name not in done:
            target = tmp_path_factory.mktemp(f"m16_{name}") / "out"
            result = orchestrator.run_in_memory(
                _config(key, **starter_map), None, target, godot_exe
            )
            assert result.ok, _errors(result)
            done[name] = (target, result)
        return done[name]

    return make


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _smoke_notes(target: Path) -> list[str]:
    """What the steps said of themselves in the smoke log (``INFO <step>: ...``)."""
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    return re.findall(r"INFO (\w+: .*)", log)


def _vacuous(target: Path) -> list[str]:
    """The steps that passed only because the game had nothing of theirs."""
    return [line for line in _smoke_notes(target) if "step passes" in line]


def _notes(result: orchestrator.RunResult) -> list[str]:
    """What the report says that a sample may not say."""
    return sorted(
        f"{i.code}: {i.message}"
        for i in result.issues
        if not i.code.startswith(MACHINE_NOTES)
        and (i.severity.value != "info" or i.code not in NOTES)
    )


def _drawn(result: orchestrator.RunResult) -> list[str]:
    return sorted(i.detail["role"] for i in result.issues if i.code == "ASSET-031")


def _archetypes(target: Path) -> list[str]:
    return sorted(p.name for p in (target / "addons/rpg_runtime/archetypes").iterdir())


def _follows_the_schemas(target: Path, godot_exe: Path, capsys, archetype: str) -> None:
    """What the run wrote, and the document of ``rpggen generate --json`` on the project (a
    run that finds nothing changed), each against its schema."""
    for rel in (paths.RESULTS_BUILD, paths.RESULTS_VALIDATE, paths.RESULTS_SMOKE):
        doc = jsonio.read(target / rel)
        schema.validate("results", doc)
        assert doc["ok"] is True, rel
    saved = jsonio.read(target / paths.CONFIG)
    schema.validate("config", saved)
    assert saved["archetype"] == archetype
    schema.validate("world_plan", jsonio.read(target / world_plan.PLAN_FILE))
    schema.validate("ledger", jsonio.read(target / paths.LEDGER))
    schema.validate("catalog", jsonio.read(target / paths.CATALOG))
    capsys.readouterr()
    code = cli.main(
        [
            "generate",
            "--config",
            str(target / paths.CONFIG),
            "--target",
            str(target),
            "--godot",
            str(godot_exe),
            "--json",
        ]
    )
    document = json.loads(capsys.readouterr().out)
    schema.validate("cli", document)
    assert code == 0 and document["ok"] is True and document["exit_code"] == 0
    assert document["command"] == "generate" and document["target"] == str(target)
    assert document["failed_phase"] is None
    assert not [i for i in document["issues"] if i["severity"] != "info"], document["issues"]
    assert orchestrator.REPEAT_CODE in {i["code"] for i in document["issues"]}, (
        "nothing changed since the sample was made: the checks are not repeated"
    )


def _nothing_moves(target: Path, cfg: config.GeneratorConfig, godot_exe: Path) -> None:
    """A second run of the same sample writes nothing again."""
    kept = {
        p.relative_to(target).as_posix(): p.read_bytes()
        for folder in ("generated/scenes", "game/data", "generated/data")
        for p in sorted((target / folder).rglob("*"))
        if p.is_file() and not p.name.endswith(".import")
    }
    assert len(kept) > 8
    plan = (target / world_plan.PLAN_FILE).read_bytes()
    again = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE]
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel
    assert (target / world_plan.PLAN_FILE).read_bytes() == plan


# ---------------------------------------------------------------- Star lane: a shoot 'em up


@pytest.mark.shmup
def test_the_star_lane_sample_is_played_through_as_a_shoot_em_up(made) -> None:
    target, result = made("shmup")
    assert _smoke(target) == SHMUP_STEPS
    assert _vacuous(target) == [], "the carrier, its power-up and the saved run are all there"
    assert _notes(result) == []
    assert _drawn(result) == [], "the pack has its own bullets, explosion and capsules"
    assert _archetypes(target) == ["arcade", "shmup"]
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "shmup" and saved["project_name"] == "Star Lane"
    stages = jsonio.read(target / "game/data/stages.json")["stages"]
    assert len(stages) == 3 and stages[0]["axis"] == "up"
    assert sum(1 for w in stages[0]["waves"] if w["enemy"] == "carrier") == 1
    ship = (target / "generated/scenes/shmup/ship.tscn").read_text(encoding="utf-8")
    assert "sprite_frames/sample_pack_shmup." in ship
    boss = (target / "generated/scenes/shmup/boss.tscn").read_text(encoding="utf-8")
    assert "sample_pack_shmup" in boss, "the boss of the pack"
    report = (target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "Result: SUCCESS" in report and "sample_pack_shmup" in report


@pytest.mark.shmup
def test_the_star_lane_sample_follows_the_schemas_and_regenerates_without_a_change(
    made, godot_exe: Path, capsys
) -> None:
    target, _result = made("shmup")
    _follows_the_schemas(target, godot_exe, capsys, "shmup")
    _nothing_moves(target, _config("shmup"), godot_exe)


# ---------------------------------------------------------------- Jungle line: a run and gun


@pytest.mark.run_and_gun
def test_the_jungle_line_sample_is_played_through_as_a_run_and_gun(made) -> None:
    target, result = made("gun")
    assert _smoke(target) == RUN_AND_GUN_STEPS
    assert _vacuous(target) == []
    assert _notes(result) == []
    assert _drawn(result) == [], "the pack has its own bullets, explosion and weapon icons"
    assert _archetypes(target) == ["arcade", "metroidvania", "run_and_gun"], (
        "the platform code the soldier is built on comes with it"
    )
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "run_and_gun" and saved["project_name"] == "Jungle Line"
    assert len(jsonio.read(target / "game/data/stages.json")["stages"]) == 3
    soldier = (target / "generated/scenes/run_and_gun/soldier.tscn").read_text(encoding="utf-8")
    assert "sprite_frames/sample_pack_gun." in soldier
    assert "can_jump = false" not in soldier and 'name="Grapple"' not in soldier
    # a gap was jumped: in the first stage, or in the first stage after it that has one
    said = _smoke_notes(target)
    crossed_later = [line for line in said if "the gap was crossed in stage" in line]
    put_off = [line for line in said if line.startswith("gap_is_crossed:")]
    assert len(crossed_later) == len(put_off), said
    assert not [line for line in said if "none was crossed" in line], said


@pytest.mark.run_and_gun
def test_the_jungle_line_sample_follows_the_schemas_and_regenerates_without_a_change(
    made, godot_exe: Path, capsys
) -> None:
    target, _result = made("gun")
    _follows_the_schemas(target, godot_exe, capsys, "run_and_gun")
    _nothing_moves(target, _config("gun"), godot_exe)


@pytest.mark.run_and_gun
def test_the_jungle_line_sample_is_played_through_as_bionic_on_the_rope(made) -> None:
    """The second run of the card: the grapple on and jumping off. Every gap of the plan has a
    block of the pack's ceiling tiles over it, and the soldier swings over one."""
    target, result = made("gun", **stage_plan.PRESETS["bionic"])
    assert _smoke(target) == RUN_AND_GUN_STEPS
    assert _vacuous(target) == []
    assert _notes(result) == [], "no VAL-030: nothing of the plan needs a jump"
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["starter_map"]["grapple"] is True and saved["starter_map"]["jump"] is False
    assert "grapple" in saved["input"]
    soldier = (target / "generated/scenes/run_and_gun/soldier.tscn").read_text(encoding="utf-8")
    assert "can_jump = false" in soldier and 'name="Grapple"' in soldier
    stored = world_plan.load(target)["stages"]
    assert stored["grapple"] is True and stored["jump"] is False
    assert stage_plan.check_grapple(stored) == []
    said = _smoke_notes(target)
    crossed_later = [line for line in said if "the gap was crossed in stage" in line]
    put_off = [line for line in said if line.startswith("gap_is_crossed:")]
    assert len(crossed_later) == len(put_off), said
    assert not [line for line in said if "none was crossed" in line], said


# ---------------------------------------------------------------- Dirt cup: a racing game


@pytest.mark.racing
def test_the_dirt_cup_sample_is_played_through_as_a_racing_game(made) -> None:
    target, result = made("race")
    assert _smoke(target) == RACING_STEPS
    assert _vacuous(target) == []
    assert _notes(result) == []
    assert [i.code for i in result.issues if i.code in ("ASSET-031", "ASSET-032")] == [], (
        "the pack has its own car in sixteen headings and its own road"
    )
    assert _archetypes(target) == ["arcade", "racing"]
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "racing" and saved["project_name"] == "Dirt Cup"
    tracks = jsonio.read(target / "game/data/stages.json")["stages"]
    assert len(tracks) == 4 and all(len(t["checkpoints"]) >= 3 for t in tracks)
    car = (target / "generated/scenes/racing/car.tscn").read_text(encoding="utf-8")
    assert "sample_pack_race" in car
    for n in (1, 2, 3):
        assert (target / f"generated/scenes/racing/rival_{n}.tscn").is_file()
    # the lap of the sequence: every checkpoint, and a rival passed
    lap = [line for line in _smoke_notes(target) if line.startswith("race_is_driven")]
    assert len(lap) == 1, lap
    found = re.search(r"(\d+) checkpoints, from place (\d+) to place (\d+) at best", lap[0])
    assert found is not None, lap
    assert int(found[1]) == len(tracks[0]["checkpoints"])
    assert int(found[2]) == 4 and int(found[3]) < 4


@pytest.mark.racing
def test_the_dirt_cup_sample_follows_the_schemas_and_regenerates_without_a_change(
    made, godot_exe: Path, capsys
) -> None:
    target, _result = made("race")
    _follows_the_schemas(target, godot_exe, capsys, "racing")
    _nothing_moves(target, _config("race"), godot_exe)
