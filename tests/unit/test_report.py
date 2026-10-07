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
