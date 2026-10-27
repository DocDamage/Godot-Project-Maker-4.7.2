"""T12.28: the command line as a tool for scripts: ``--json``, exit codes, ``--dry-run``."""

from __future__ import annotations

import json
import signal
from pathlib import Path
from typing import Any

import pytest

from rpggen import cli, cli_support, paths, schema
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import dry_run, godot, orchestrator, staging
from rpggen.errors import Issue, IssueList, RpgGenError, Severity

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("RPGGEN_GODOT", raising=False)
    return tmp_path / "cache"


def _error(code: str) -> Issue:
    return RpgGenError(code).issue  # a fatal error is always an error


def _call(capsys, *argv: str) -> tuple[int, dict[str, Any], str]:
    """``(exit code, the --json document, stderr)``; stdout must hold nothing but the document."""
    code = cli.main([*argv, "--json"])
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    schema.validate("cli", document)
    assert document["exit_code"] == code and document["ok"] == (code == 0)
    return code, document, captured.err


def _fake_godot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(godot, "detect_version", lambda exe: (4, 7, 2, "stable"))
    exe = tmp_path / "godot.exe"
    exe.write_text("not a real Godot", encoding="utf-8")
    return exe


def _fake_run(monkeypatch: pytest.MonkeyPatch, result: orchestrator.RunResult) -> None:
    monkeypatch.setattr(orchestrator, "run", lambda *a, **k: result)
    monkeypatch.setenv("RPGGEN_GODOT", "godot")


# ------------------------------------------------------------------------ exit codes


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("BUILD-001", 1),
        ("VAL-001", 1),
        ("SMOKE-001", 1),
        ("REGEN-004", 1),
        ("ENV-001", 3),
        ("ARCH-001", 3),
        ("CAT-001", 3),
        ("ASSET-010", 3),
        ("BUILD-005", 70),
    ],
)
def test_the_exit_code_follows_the_group_of_the_error(code: str, expected: int) -> None:
    assert cli_support.exit_code_for([_error(code)]) == expected


def test_the_exit_code_of_mixed_and_special_cases() -> None:
    issues = IssueList()
    issues.add("ENV-003")  # a warning: not what stopped the run
    issues.append(_error("VAL-001"))
    assert cli_support.exit_code_for(issues) == 1
    assert cli_support.exit_code_for([_error("ENV-001"), _error("VAL-001")]) == 3  # the first
    assert cli_support.exit_code_for([_error("VAL-001"), _error("BUILD-005")]) == 70  # any
    assert cli_support.exit_code_for([_error("ENV-001")], cancelled=True) == 4
    assert cli_support.exit_code_for([]) == 1  # failed without a reason: still a failure


def test_success_is_0_and_a_json_document_follows_the_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    issues = [Issue("ASSET-010", Severity.WARNING, "no NPC", "assign one", "a/b.png")]
    result = orchestrator.RunResult(
        True,
        tmp_path / "game",
        issues,
        None,
        None,
        timings={"preflight": 0.1, "build": 2.5},
        skipped={"export": "ENV-010"},
        run_id="0123abcd",
    )
    _fake_run(monkeypatch, result)
    code, doc, err = _call(
        capsys, "generate", "--pack", str(SYNTH / "basic16"), "--target", str(tmp_path / "game")
    )
    assert code == 0 and doc["command"] == "generate" and doc["dry_run"] is False
    assert doc["target"] == str(tmp_path / "game") and doc["run_id"] == "0123abcd"
    assert doc["failed_phase"] is None and doc["failed_staging"] is None
    assert doc["skipped"] == {"export": "ENV-010"}
    assert doc["timings"] == {"preflight": 0.1, "build": 2.5}
    assert doc["issues"] == [
        {
            "code": "ASSET-010",
            "severity": "warning",
            "message": "no NPC",
            "fix": "assign one",
            "file": "a/b.png",
        }
    ]
    assert "OK: project generated" in err and "WARNING ASSET-010" in err  # the human lines


def test_without_json_everything_stays_on_stdout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _fake_run(monkeypatch, orchestrator.RunResult(True, tmp_path / "g", [], None, None))
    assert cli.main(["generate", "--pack", str(SYNTH / "basic16"), "--target", "g"]) == 0
    captured = capsys.readouterr()
    assert "OK: project generated" in captured.out and captured.err == ""


def test_a_failed_generation_is_1_and_names_the_phase_and_the_kept_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    kept = tmp_path / "game" / ".rpggen_failed"
    result = orchestrator.RunResult(
        False,
        tmp_path / "game",
        [_error("VAL-001")],
        kept / "generation_report.json",
        kept,
        failed_phase="validate",
        timings={"validate": 1.0},
    )
    _fake_run(monkeypatch, result)
    code, doc, err = _call(
        capsys, "generate", "--pack", str(SYNTH / "basic16"), "--target", str(tmp_path / "game")
    )
    assert code == 1 and doc["failed_phase"] == "validate"
    assert doc["failed_staging"] == str(kept)
    assert [i["code"] for i in doc["issues"]] == ["VAL-001"] and doc["issues"][0]["fix"]
    assert "FAILED" in err and "kept for inspection" in err


def test_a_usage_error_is_2_and_the_document_says_what_was_wrong(capsys) -> None:
    code, doc, err = _call(capsys, "generate", "--pack", str(SYNTH / "basic16"))
    assert code == 2 and "--target" in doc["error"] and "--target" in err
    code, doc, _err = _call(capsys, "diagnose", "--target", str(Path("no") / "such" / "folder"))
    assert code == 2 and "not a folder" in doc["error"]


def test_an_unknown_preset_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("RPGGEN_GODOT", "godot")
    args = ["generate", "--pack", str(SYNTH / "basic16"), "--target", str(tmp_path / "t")]
    code, doc, _err = _call(capsys, *args, "--preset", "no such preset")
    assert code == 2 and "no saved preset" in doc["error"]


def test_a_missing_godot_is_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(godot, "auto_find_godot", lambda: None)
    code, doc, err = _call(
        capsys, "generate", "--pack", str(SYNTH / "basic16"), "--target", str(tmp_path / "t")
    )
    assert code == 3 and doc["issues"][0]["code"] == "ENV-001"
    assert "RPGGEN_GODOT" in doc["issues"][0]["message"] and "RPGGEN_GODOT" in err


def test_a_pack_that_is_not_there_is_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("RPGGEN_GODOT", "godot")
    code, doc, _err = _call(
        capsys, "generate", "--pack", str(tmp_path / "gone"), "--target", str(tmp_path / "t")
    )
    assert code == 3 and doc["issues"][0]["code"] == "ARCH-001"
    assert not (tmp_path / "t").exists()


def test_an_unreadable_pack_archive_is_3_for_analyze_too(tmp_path: Path, capsys) -> None:
    code, doc, _err = _call(capsys, "analyze", str(tmp_path / "missing.zip"))
    assert code == 3 and doc["issues"][0]["code"] == "ARCH-001"


def test_an_unexpected_exception_is_70_with_build_005(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    exe = _fake_godot(monkeypatch, tmp_path)

    def boom(state) -> None:
        raise ZeroDivisionError("the divisor was zero")

    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "catalog", boom)
    code, doc, _err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / "basic16"),
        "--target",
        str(tmp_path / "game"),
        "--godot",
        str(exe),
    )
    assert code == 70 and doc["failed_phase"] == "catalog"
    assert any(i["code"] == "BUILD-005" for i in doc["issues"])
    assert doc["failed_staging"] and Path(doc["failed_staging"]).is_dir()
    assert len(doc["run_id"]) == 8


def test_an_exception_outside_a_run_is_70_and_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    from rpggen.core import diagnostics

    def broken(*a: Any, **k: Any) -> None:
        raise OSError("the disk is gone")

    monkeypatch.setattr(diagnostics, "make_bundle", broken)
    folder = tmp_path / "p"
    folder.mkdir()
    code, doc, err = _call(capsys, "diagnose", "--target", str(folder))
    assert code == 70 and "the disk is gone" in doc["error"] and "INTERNAL ERROR" in err
    assert "Traceback" not in err


def test_ctrl_c_is_4_and_nothing_is_delivered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    exe = _fake_godot(monkeypatch, tmp_path)
    seen: list[bool] = []

    def interrupted(state) -> None:
        signal.raise_signal(signal.SIGINT)  # the user presses Ctrl+C in the middle of a phase
        seen.append(state.cb.is_cancelled())

    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "catalog", interrupted)
    target = tmp_path / "game"
    code, doc, err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / "basic16"),
        "--target",
        str(target),
        "--godot",
        str(exe),
    )
    assert code == 4 and seen == [True]
    assert doc["cancelled"] is True and doc["failed_staging"] is None
    assert "CANCELLED" in err and "Stopping" in err
    assert not (target / staging.STAGING_NAME).exists()
    assert not (target / staging.FAILED_NAME).exists()
    assert not any(target.iterdir()) if target.exists() else True  # nothing was delivered


def test_the_handler_is_removed_again_and_a_second_ctrl_c_raises() -> None:
    before = signal.getsignal(signal.SIGINT)
    with cli_support.interruptible() as is_cancelled:
        assert not is_cancelled()
        signal.raise_signal(signal.SIGINT)
        assert is_cancelled()
        with pytest.raises(KeyboardInterrupt):
            signal.raise_signal(signal.SIGINT)
    assert signal.getsignal(signal.SIGINT) is before


def test_a_keyboard_interrupt_that_gets_through_is_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("RPGGEN_GODOT", "godot")

    def raising(*a: Any, **k: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(orchestrator, "run", raising)
    code, doc, _err = _call(
        capsys, "generate", "--pack", str(SYNTH / "basic16"), "--target", str(tmp_path / "t")
    )
    assert code == 4 and doc["error"] == "cancelled"


# ------------------------------------------------------------------------ restore, diagnose, analyze


def test_restore_without_a_backup_is_1_and_json_names_the_code(tmp_path: Path, capsys) -> None:
    code, doc, _err = _call(capsys, "restore", "--target", str(tmp_path))
    assert code == 1 and doc["issues"][0]["code"] == "REGEN-004"
    assert doc["saved_state"] is None and doc["backup"] is None


def test_diagnose_json_names_the_bundle(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "project"
    (folder / "rpggen").mkdir(parents=True)
    bundle = tmp_path / "bundle.zip"
    code, doc, err = _call(capsys, "diagnose", "--target", str(folder), "--out", str(bundle))
    assert code == 0 and doc["bundle"] == str(bundle) and bundle.is_file()
    assert "diagnostic bundle written" in err


def test_analyze_json_lists_the_assets_with_their_decisions(tmp_path: Path, capsys) -> None:
    out = tmp_path / "catalog.json"
    code, doc, err = _call(
        capsys,
        "analyze",
        str(SYNTH / "gutter32"),
        "--out",
        str(out),
        "--expected",
        str(SYNTH / "gutter32.expected.json"),
    )
    assert code == 0 and doc["mode"] == "pack" and doc["catalog_file"] == str(out)
    row = next(r for r in doc["assets"] if r["path"].endswith("tiles/world.png"))
    assert row["grid"]["cell"] == [32, 32] and row["status"] and row["confidence"] > 0
    assert doc["accuracy"]["correct"] == doc["accuracy"]["total"] == 5
    assert "tiles/world.png" in err  # the table is a human line


def test_analyze_corpus_json(tmp_path: Path, capsys) -> None:
    report = tmp_path / "accuracy_report.json"
    code, doc, _err = _call(capsys, "analyze", "--corpus", str(SYNTH), "--report", str(report))
    assert code == 0 and doc["mode"] == "corpus" and doc["passed"] is True
    assert doc["groups"]["grid"] >= doc["thresholds"]["grid"]


# ------------------------------------------------------------------------ the dry run


def _no_godot_no_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*a: Any, **k: Any) -> None:
        raise AssertionError("a dry run must not do this")

    monkeypatch.setattr(godot, "detect_version", forbidden)
    monkeypatch.setattr(godot, "run_godot", forbidden)
    monkeypatch.setattr(staging, "create_staging", forbidden)
    # no Godot on this machine, whatever its PATH holds (the summary reports "godot": None)
    monkeypatch.setattr(godot, "auto_find_godot", lambda platform=None: [])
    monkeypatch.delenv("RPGGEN_GODOT", raising=False)


def test_a_dry_run_makes_nothing_and_starts_no_godot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _no_godot_no_staging(monkeypatch)
    target = tmp_path / "not_yet" / "game"
    code, doc, err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / "objects_in_sheet"),
        "--target",
        str(target),
        "--dry-run",
        "--placeholder",
        "PLAYER",
        "--placeholder",
        "GROUND",
    )
    assert code == 0 and doc["dry_run"] is True and doc["failed_phase"] is None
    assert not target.exists() and not target.parent.exists()  # a missing target stays missing
    summary = doc["summary"]
    assert summary["regeneration"] is False and summary["tile_size"] == 16
    assert summary["tile_size_from"] == "packs" and summary["godot"] is None
    assert summary["roles"]["BUILDING"] == {"count": 1, "need": "recommended"}
    assert summary["placeholders"] == ["PLAYER"]  # GROUND is there: no placeholder for it
    assert summary["map"]["size"] == [40, 24]
    assert summary["map"]["counts"]["buildings"] == 1  # the house cut from the sheet
    assert set(doc["timings"]) == {"preflight", "catalog", "plan"}
    assert [i["message"] for i in doc["issues"] if i["code"] == "ASSET-011"] == [
        "Placeholder used for role PLAYER."
    ]
    assert "Dry run: nothing was written" in err and "40 x 24 tiles; 1 buildings" in err


def test_a_dry_run_reports_what_would_stop_a_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _no_godot_no_staging(monkeypatch)
    args = ["generate", "--pack", str(SYNTH / "rpgmaker_like"), "--target", str(tmp_path / "g")]
    code, doc, err = _call(capsys, *args, "--dry-run")  # the pack has no GROUND
    assert code == 3 and doc["failed_phase"] == "catalog"  # ASSET: the input
    error = next(i for i in doc["issues"] if i["severity"] == "error")
    assert error["code"] == "ASSET-010" and "GROUND" in error["message"]
    assert "FAILED: a generation would stop in the catalog phase" in err
    assert "map" not in doc["summary"]  # the plan is made only for a config that could run
    assert not (tmp_path / "g").exists()


def test_a_dry_run_looks_for_godot_but_never_starts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _no_godot_no_staging(monkeypatch)
    args = ["generate", "--pack", str(SYNTH / "objects_in_sheet"), "--dry-run", "--placeholder"]
    args = [*args, "PLAYER", "--placeholder", "GROUND", "--target", str(tmp_path / "g")]
    code, doc, _err = _call(capsys, *args, "--godot", str(tmp_path / "no_godot.exe"))
    assert code == 3 and doc["failed_phase"] == "preflight"
    assert doc["issues"][0]["code"] == "ENV-001"
    exe = tmp_path / "godot.exe"
    exe.write_text("x", encoding="utf-8")
    code, doc, _err = _call(capsys, *args, "--godot", str(exe))
    assert code == 0 and doc["summary"]["godot"] == str(exe)


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_a_dry_run_of_a_regeneration_leaves_the_project_as_it_was(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    target = tmp_path / "game"
    cfg = orchestrator.default_config_for_pack(SYNTH / "basic16", "Game")
    (target / "rpggen").mkdir(parents=True)
    config_mod.save(cfg, target / paths.CONFIG)
    from rpggen import analyze_cmd

    cat, _issues = analyze_cmd.analyze_pack(SYNTH / "basic16")
    catalog_mod.save(cat, target / paths.CATALOG)
    (target / "project.godot").write_text("; the user's file\n", encoding="utf-8")
    before = _tree(target)
    siblings = sorted(p.name for p in tmp_path.iterdir())
    _no_godot_no_staging(monkeypatch)
    code, doc, _err = _call(
        capsys,
        "generate",
        "--config",
        str(target / paths.CONFIG),
        "--target",
        str(target),
        "--dry-run",
        "--force-while-open",
    )
    assert code == 0, doc["issues"]
    assert doc["summary"]["regeneration"] is True and doc["summary"]["tile_size_from"] == "config"
    assert _tree(target) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == siblings  # no staging next to it either


def test_a_dry_run_in_a_folder_that_belongs_to_someone_else_is_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    target = tmp_path / "documents"
    target.mkdir()
    (target / "thesis.docx").write_text("precious", encoding="utf-8")
    code, doc, _err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / "objects_in_sheet"),
        "--target",
        str(target),
        "--dry-run",
    )
    assert code == 3 and doc["failed_phase"] == "preflight"
    assert any(i["code"] == "ENV-009" for i in doc["issues"])
    assert [p.name for p in target.iterdir()] == ["thesis.docx"]


def test_the_dry_run_plan_matches_the_planner(tmp_path: Path) -> None:
    """The building comes from the catalog alone, with the numbers ``load_art`` would find."""
    from rpggen.core import archive, inventory, map_preview

    opened = archive.open_pack(SYNTH / "objects_in_sheet", set())
    cat, _issues, _generated = catalog_mod.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    info = map_preview.building_info_for(cat)
    house = map_preview.starter_buildings(cat)[0]
    tile = int(cat.tilesets[0].tile_size[0])
    size, door = map_preview.building_geometry((house.region[2], house.region[3]), house.door, tile)
    assert info == {"size": list(size), "door": list(door)} and size[0] >= 1 and size[1] >= 1
    assert map_preview.building_info_for(cat, "no such building") == info  # falls back
    assert dry_run.PLAN_COUNTS == ("buildings", "npcs", "enemies", "chests", "decorations")


# ------------------------------------------------------------------------ --confirm (T12.40)


def _summary():  # type: ignore[no-untyped-def]
    from rpggen.core import promote

    return promote.PromotionSummary(
        ["generated/a.tres"], ["generated/b.tres"], [], [], ".rpggen_backups/20260101-000000"
    )


def _confirm_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys, *extra: str):
    exe = _fake_godot(monkeypatch, tmp_path)
    answers: list[bool] = []

    def promote_phase(state) -> None:
        if not state.cb.confirm_promotion(_summary()):
            answers.append(False)
            raise orchestrator._Cancelled
        answers.append(True)

    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "catalog", promote_phase)
    code, doc, err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / "basic16"),
        "--target",
        str(tmp_path / "game"),
        "--godot",
        str(exe),
        *extra,
    )
    return code, answers, err


def test_confirm_answered_n_cancels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    code, answers, err = _confirm_run(monkeypatch, tmp_path, capsys, "--confirm")
    assert code == 4 and answers == [False]
    assert "conflict: generated/b.tres" in err and "1 .rpggen-new" in err


def test_confirm_answered_y_goes_on_and_no_confirm_never_asks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    _code, answers, _err = _confirm_run(monkeypatch, tmp_path, capsys, "--confirm")
    assert answers == [True]

    def boom(prompt: str = "") -> str:
        raise AssertionError("asked")

    monkeypatch.setattr("builtins.input", boom)
    (tmp_path / "two").mkdir()
    _code, answers, _err = _confirm_run(monkeypatch, tmp_path / "two", capsys)
    assert answers == [True]  # without --confirm the callback says yes by itself


def test_confirm_without_a_terminal_is_a_no(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    code, answers, err = _confirm_run(monkeypatch, tmp_path, capsys, "--confirm")
    assert code == 4 and answers == [False] and "No terminal" in err


def test_a_dry_run_of_a_metroidvania_plans_the_world_of_rooms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """T14.10: the command line takes the archetype, and the dry run says what world it makes."""
    _no_godot_no_staging(monkeypatch)
    target = tmp_path / "cave"
    code, doc, err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / "platformer"),
        "--archetype",
        "metroidvania",
        "--target",
        str(target),
        "--dry-run",
    )
    assert code == 0 and doc["failed_phase"] is None, doc["issues"]
    summary = doc["summary"]
    assert summary["archetype"] == "metroidvania"
    assert summary["roles"]["BOSS"]["need"] == "recommended"
    assert "BUILDING" not in summary["roles"] or summary["roles"]["BUILDING"]["need"] == "optional"
    plan = summary["map"]
    assert plan["world"] == "6 rooms, 2 abilities, a guardian"
    assert plan["size"] == [40, 23] and len(plan["rooms"]) == 6
    assert "(metroidvania)" in err
    assert "world:        6 rooms, 2 abilities, a guardian; rooms of 40 x 23 tiles" in err
    assert not target.exists()


@pytest.mark.parametrize(
    ("pack", "archetype", "text"),
    [
        ("shooter", "shmup", r"3 stages, \d+ waves, 3 bosses"),
        ("gunner", "run_and_gun", r"3 stages, \d+ waves, 3 bosses"),
        ("racer", "racing", r"4 tracks of 3 laps, 3 rivals"),
    ],
)
def test_a_dry_run_of_an_arcade_kind_describes_its_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys, pack: str, archetype: str, text: str
) -> None:
    """T16.16: ``--archetype`` takes the three keys, and the dry run says what would be planned."""
    import re

    _no_godot_no_staging(monkeypatch)
    code, doc, err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / pack),
        "--archetype",
        archetype,
        "--target",
        str(tmp_path / "game"),
        "--dry-run",
    )
    assert code == 0, err
    summary = doc["summary"]
    assert summary["archetype"] == archetype
    assert re.fullmatch(text, summary["map"]["stages"]), summary["map"]
    assert re.search(r"^stages:\s+" + text + "$", err, re.MULTILINE), err
    assert not (tmp_path / "game").exists()


def test_an_unknown_archetype_is_a_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["generate", "--pack", str(SYNTH / "shooter"), "--archetype", "pinball"])
    assert raised.value.code == 2
    assert "--archetype" in capsys.readouterr().err


# ------------------------------------------------------------------------ a farm (T17.16)


@pytest.mark.parametrize(
    ("pack", "projection"),
    [("ranch", "top_down"), ("iso_miniature", "isometric")],
)
def test_a_dry_run_of_a_farm_describes_its_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys, pack: str, projection: str
) -> None:
    """T17.16: ``--archetype farm`` and ``--projection isometric``, and the dry run says what
    farm would be planned beside its village."""
    import re

    _no_godot_no_staging(monkeypatch)
    code, doc, err = _call(
        capsys,
        "generate",
        "--pack",
        str(SYNTH / pack),
        "--archetype",
        "farm",
        "--projection",
        projection,
        "--target",
        str(tmp_path / "game"),
        "--dry-run",
    )
    assert code == 0, err
    summary = doc["summary"]
    assert summary["archetype"] == "farm"
    # a new farm builds the houses of the packs' animals (T18.05): the ranch has hens and cows
    houses = ", a coop, a barn" if pack == "ranch" else "(, a coop)?(, a barn)?"
    text = (
        r"a farm of 40 x 30 with a plot of 96 cells, a (pond|well)"
        + houses
        + r", \d+ crops, \d+ people, 4 festivals"
    )
    assert re.fullmatch(text, summary["map"]["farm"]), summary["map"]
    # the starter map is the village: nobody to fight, and the demo's villager alone
    assert summary["map"]["counts"]["enemies"] == 0 and summary["map"]["counts"]["npcs"] == 1
    assert re.search(r"^farm:\s+" + text + "$", err, re.MULTILINE), err
    assert re.search(r"^village:\s+40 x 24 tiles; ", err, re.MULTILINE), err
    assert not (tmp_path / "game").exists()


def test_the_crops_and_the_people_of_a_dry_run_are_those_of_the_packs() -> None:
    """Four crops of the ``ranch`` can grow; a pack without one gets the three drawn ones, and
    a village without an NPC three people who share the stand-in."""
    from rpggen.core import archive, catalog, config, inventory, options

    def plans(pack: str) -> dict:
        opened = archive.open_pack(SYNTH / pack, set())
        cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
        ref = config.PackRef(pack, pack, "0" * 64, "folder")
        return options.plan_farm(config.default_for("F", [ref], archetype="farm"), cat)

    ranch = plans("ranch")
    assert ranch["crops"] == 4 and ranch["people"] == 3 and not ranch["stored"]
    assert options.farm_text(ranch).endswith(", 4 crops, 3 people, 4 festivals")
    assert plans("basic16")["crops"] == 3, "the drawn turnip, carrot and berry"
    none = options.plan_farm(config.default_for("F", [], archetype="farm"), None)
    assert (none["crops"], none["people"]) == (3, 3)


def test_an_unknown_projection_is_a_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["generate", "--pack", str(SYNTH / "ranch"), "--projection", "sideways"])
    assert raised.value.code == 2
    assert "--projection" in capsys.readouterr().err
