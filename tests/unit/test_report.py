from __future__ import annotations

import re
from pathlib import Path

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, report
from rpggen.core.promote import PromotionPlan
from rpggen.errors import Issue, Severity

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _catalog() -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / "basic16", set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


def _cfg() -> config.GeneratorConfig:
    ref = config.PackRef("basic16", str(SYNTH / "basic16"), "0" * 64, "folder")
    return config.default_for("T", [ref])


def _project(tmp_path: Path) -> Path:
    (tmp_path / "generated/scenes/actors").mkdir(parents=True, exist_ok=True)
    (tmp_path / "generated/scenes/actors/player.tscn").write_text("", encoding="utf-8")
    (tmp_path / "generated/scenes/objects").mkdir(parents=True, exist_ok=True)
    for n in range(3):
        (tmp_path / f"generated/scenes/objects/o{n}.tscn").write_text("", encoding="utf-8")
    jsonio.write(
        tmp_path / "rpggen/results/validation_results.json",
        {"items": [
            {"check": "resource_load", "target": "a", "ok": True},
            {"check": "resource_load", "target": "b", "ok": False},
            {"check": "scene_load", "target": "c", "ok": True},
        ]},
    )  # fmt: skip
    jsonio.write(
        tmp_path / "rpggen/results/smoke_results.json",
        {"items": [
            {"step": 1, "name": "boot", "ok": True, "ms": 412},
            {"step": 2, "name": "walk", "ok": False, "ms": 9},
        ]},
    )  # fmt: skip
    return tmp_path


def _md(
    tmp_path: Path, issues: list[Issue] | None = None, plan: PromotionPlan | None = None
) -> str:
    return report.build_markdown(
        _cfg(), _catalog(), issues or [], True, project=_project(tmp_path), plan=plan
    )


def test_sections_come_in_the_documented_order(tmp_path: Path) -> None:
    md = _md(tmp_path, plan=PromotionPlan())
    headings = re.findall(r"^## (.+)$", md, re.M)
    assert headings == [
        "What to review",
        "Packs and licenses",
        "Summary",
        "TileSets",
        "Scenes",
        "Animations",
        "Regeneration",
        "Validation",
        "Smoke test",
        "Issues",
    ]
    assert md.startswith("# Generation Report\n")
    assert "Result: SUCCESS" in md


def test_a_first_generation_has_no_regeneration_section(tmp_path: Path) -> None:
    assert "## Regeneration" not in _md(tmp_path)


def test_regeneration_lists_written_conflicts_deleted_and_removed(tmp_path: Path) -> None:
    plan = PromotionPlan(
        write=["generated/a.tres"],
        conflicts=["generated/b.tscn"],
        delete=["assets/packs/p/old.png"],
        skipped_deleted=["generated/c.tscn"],
    )
    md = _md(tmp_path, plan=plan)
    section = md.split("## Regeneration")[1].split("## Validation")[0]
    for rel in plan.write + plan.conflicts + plan.delete + plan.skipped_deleted:
        assert f"`{rel}`" in section
    assert ".rpggen-new" in section and "you deleted them" in section


def test_long_regeneration_lists_are_capped(tmp_path: Path) -> None:
    plan = PromotionPlan(write=[f"generated/f{n:03}.tres" for n in range(100)])
    section = _md(tmp_path, plan=plan).split("## Regeneration")[1].split("## Validation")[0]
    assert "(100)" in section and "... and 60 more" in section
    assert section.count("`generated/f") == report.LIST_CAP


def test_scenes_validation_and_smoke_come_from_the_project(tmp_path: Path) -> None:
    md = _md(tmp_path)
    assert "- generated/scenes/actors: 1" in md and "- generated/scenes/objects: 3" in md
    assert "| resource_load | 1 | 1 |" in md and "| scene_load | 1 | 0 |" in md
    assert "| 2 | walk | FAILED |" in md
    assert "412" not in md, "timings would make the report differ between identical runs"


def test_the_report_is_identical_for_identical_input(tmp_path: Path) -> None:
    assert _md(tmp_path) == _md(tmp_path)


def test_review_groups_conflicts_before_licenses_and_lists_every_warning(tmp_path: Path) -> None:
    cat = _catalog()
    cat.assets[0].status = "CONFLICT"
    issues = [
        Issue("ASSET-021", Severity.INFO, "Pack p has no license file.", "Check terms."),
        Issue("ASSET-020", Severity.WARNING, "RTP asset x.", "Replace it."),
        Issue("REGEN-001", Severity.WARNING, "File f kept.", "Merge manually."),
        Issue("ANIM-002", Severity.WARNING, "Direction assumed.", "Check it."),
    ]
    md = report.build_markdown(_cfg(), cat, issues, True, placeholders=["PLAYER"])
    review = md.split("## What to review")[1].split("## Packs and licenses")[0]
    order = [
        review.index(t) for t in ("**Conflicts**", "**Placeholders**", "**Licenses**", "**Other**")
    ]
    assert order == sorted(order)
    assert "REGEN-001" in review and "in CONFLICT" in review and "Fix: Replace it." in review
    assert "ANIM-002" in review
    assert "ASSET-021" not in review, "info items belong to the issues table only"
    assert "| ASSET-021 | info |" in md


def test_nothing_to_review(tmp_path: Path) -> None:
    cat = _catalog()
    for asset in cat.assets:
        asset.status = "CONFIRMED"
    md = report.build_markdown(_cfg(), cat, [], True)
    assert "Nothing needs review." in md


# ------------------------------------------------------------------------ skipped checks (T12.07)


def test_the_report_names_the_checks_that_did_not_run() -> None:
    text = report.build_markdown(
        _cfg(), _catalog(), [], True, skipped={"export": "ENV-010", "smoke": "VAL-021"}
    )
    assert "## Checks not run" in text
    assert "**export** (ENV-010): Export templates for 4.7.2 not installed" in text
    assert "**smoke** (VAL-021): The smoke test is turned off in the config" in text
    assert "## Checks not run" not in report.build_markdown(_cfg(), _catalog(), [], True)


def _state(tmp_path: Path, **validation: bool):
    from types import SimpleNamespace

    from rpggen.core import orchestrator

    skipped: list[tuple[str, str]] = []
    cb = orchestrator.Callbacks(on_skip=lambda phase, code: skipped.append((phase, code)))
    state = orchestrator._State(None, tmp_path / "out", Path("godot"), cb)
    state.cfg = _cfg()
    state.cfg.validation.update(validation)
    state.staging = SimpleNamespace(staging=tmp_path / "stg")  # type: ignore[assignment]
    state.log_dir = tmp_path / "logs"
    return state, skipped


def test_an_export_without_templates_is_a_skipped_check(tmp_path: Path, monkeypatch) -> None:
    from rpggen.core import export_check, orchestrator

    monkeypatch.setenv("RPGGEN_EXPORT_TEMPLATES_DIR", str(tmp_path / "none"))
    monkeypatch.setattr(export_check.godot, "detect_version", lambda exe: (4, 7, 2, "stable"))
    state, seen = _state(tmp_path)
    orchestrator.phase_export(state)
    assert state.skipped == {"export": "ENV-010"} and seen == [("export", "ENV-010")]
    assert [i.code for i in state.issues] == ["ENV-010"]
    assert not state.issues.has_errors()


def test_turned_off_checks_are_skipped_with_their_own_note(tmp_path: Path) -> None:
    from rpggen.core import orchestrator

    state, seen = _state(tmp_path, smoke_test=False, export_check=False)
    orchestrator._run_smoke(state)
    orchestrator.phase_export(state)
    assert state.skipped == {"smoke": "VAL-021", "export": "VAL-022"}
    assert seen == [("smoke", "VAL-021"), ("export", "VAL-022")]
    assert sorted(i.code for i in state.issues) == ["VAL-021", "VAL-022"]
    assert all(i.severity is Severity.INFO for i in state.issues)


def test_the_results_and_the_report_json_carry_the_skips(tmp_path: Path) -> None:
    from rpggen.core import orchestrator

    state, _seen = _state(tmp_path, smoke_test=False)
    orchestrator._run_smoke(state)
    data = orchestrator._report_data(state, True)
    assert data["skipped"] == {"smoke": "VAL-021"}
    state.skipped.clear()
    assert "skipped" not in orchestrator._report_data(state, True)  # nothing to report: no key


# ------------------------------------------------------------------------ git outcomes (T12.12)


def _git_state(tmp_path: Path, message: str | None):
    from types import SimpleNamespace

    from rpggen.core import orchestrator, promote

    target = tmp_path / "out"
    (target / "rpggen").mkdir(parents=True)
    state = orchestrator._State(None, target, Path("godot"), orchestrator.Callbacks())
    state.cfg = _cfg()
    state.staging = SimpleNamespace(staging=tmp_path / "stg", regenerate=True)  # type: ignore[assignment]
    state.promotion = promote.PromotionResult(
        promote.PromotionPlan(write=["a.txt"]), None, [], None
    )  # type: ignore[arg-type]
    state.git_message = message
    return state


def test_a_failed_commit_is_a_warning_on_the_result_and_in_the_report(
    tmp_path: Path, monkeypatch
) -> None:
    from rpggen.core import orchestrator, vcs

    state = _git_state(tmp_path, "rpggen: regenerate project")
    monkeypatch.setattr(vcs, "is_repository", lambda target: True)
    monkeypatch.setattr(vcs, "foreign_changes", lambda target, files: False)
    monkeypatch.setattr(
        vcs,
        "commit",
        lambda target, message, files=None: vcs.CommitResult(False, reason="hook said no"),
    )
    orchestrator.phase_report(state)
    issues = {i.code: i for i in state.issues}
    assert issues["REGEN-007"].severity is Severity.WARNING
    assert "hook said no" in issues["REGEN-007"].message
    text = (state.target / "GENERATION_REPORT.md").read_text(encoding="utf-8")
    assert "REGEN-007" in text  # the report was written again with the failure in it


def test_the_users_own_changes_are_named_in_a_note_and_only_our_files_are_committed(
    tmp_path: Path, monkeypatch
) -> None:
    from rpggen.core import orchestrator, vcs

    state = _git_state(tmp_path, "rpggen: regenerate project")
    seen: dict = {}
    monkeypatch.setattr(vcs, "is_repository", lambda target: True)
    monkeypatch.setattr(vcs, "foreign_changes", lambda target, files: True)

    def commit(target, message, files=None):
        seen["files"] = files
        return vcs.CommitResult(True, committed=True)

    monkeypatch.setattr(vcs, "commit", commit)
    orchestrator.phase_report(state)
    assert [i.code for i in state.issues] == ["REGEN-008"]
    assert "a.txt" in seen["files"] and "rpggen/ownership_ledger.json" in seen["files"]
    assert (
        "GENERATION_REPORT.md" in seen["files"] and "rpggen/generation_report.json" in seen["files"]
    )


def test_without_a_commit_message_git_is_not_touched(tmp_path: Path, monkeypatch) -> None:
    from rpggen.core import orchestrator, vcs

    state = _git_state(tmp_path, None)
    monkeypatch.setattr(vcs, "commit", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        vcs, "foreign_changes", lambda *a, **k: (_ for _ in ()).throw(AssertionError())
    )
    orchestrator.phase_report(state)
    assert not [i for i in state.issues if i.code.startswith("REGEN-00")]
