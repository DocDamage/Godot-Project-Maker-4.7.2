"""GENERATION_REPORT.md: the human-readable result of a run (T3.13 wrote the basic sections,
T5.08 completes it). The text is deterministic: no timestamps and no timings, so an unchanged
project produces an identical report."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rpggen import __version__, jsonio, paths
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import labels, licenses
from rpggen.errors import Issue, Severity

if TYPE_CHECKING:
    from rpggen.core.promote import PromotionPlan

REPORT_MD = "GENERATION_REPORT.md"
LIST_CAP = 40  # entries per list in the Regeneration section
_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
_CONFLICT_CODES = {"REGEN-001", "TILE-004"}
_LICENSE_CODES = {"ASSET-020", "ASSET-021", "ASSET-028"}


def counts(
    catalog: catalog_mod.Catalog | None, issues: list[Issue], target: Path | None = None
) -> dict[str, int]:
    """The numbers shown on the results page and in the report's summary."""
    active = [a for a in catalog.assets if a.status != "UNUSED"] if catalog else []
    animated = [a for a in active if catalog_mod.effective(a).get("animations")]
    scenes = 0
    if target is not None and target.exists():
        for folder in ("generated", "game"):
            scenes += sum(1 for _ in (target / folder).rglob("*.tscn"))
    return {
        "assets": len(active),
        "tilesets": len(catalog.tilesets) if catalog else 0,
        "scenes": scenes,
        "animation_sets": len(animated),
        "warnings": sum(1 for i in issues if i.severity is Severity.WARNING),
        "errors": sum(1 for i in issues if i.severity is Severity.ERROR),
    }


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _skipped_lines(skipped: dict[str, str], issues: list[Issue]) -> list[str]:
    """ "Checks not run": a check that was skipped is never reported as passed. The reason is
    the text of the run's issues with that code (they can name a target), else the code's."""
    if not skipped:
        return []
    from rpggen.errors import CODES

    lines = ["", "## Checks not run", ""]
    for phase, code in sorted(skipped.items()):
        info = CODES.get(code)
        said = list(dict.fromkeys(i.message for i in issues if i.code == code))
        reason = " ".join(said) if said else (info.message if info else code)
        fix = f" {info.fix}" if info and info.fix and info.fix != "—" else ""
        lines.append(f"- **{phase}** ({code}): {reason}{fix}")
    return lines


def build_markdown(
    cfg: config_mod.GeneratorConfig | None,
    catalog: catalog_mod.Catalog | None,
    issues: list[Issue],
    ok: bool,
    *,
    godot_version: str = "",
    failed_phase: str | None = None,
    placeholders: list[str] | None = None,
    summary: dict[str, int] | None = None,
    project: Path | None = None,
    plan: PromotionPlan | None = None,
    runtime_version: str = "",
    skipped: dict[str, str] | None = None,
) -> str:
    """The report. ``project`` is the folder holding the generated files and result files;
    ``plan`` is the promotion plan of a regeneration; ``skipped`` maps a phase that did not run
    to the code that says why."""
    godot = godot_version or (cfg.godot_version if cfg else "")
    archetype = cfg.archetype if cfg else "?"
    lines = [
        "# Generation Report",
        "",
        f"- Generator: rpggen {__version__} · Runtime {runtime_version or '?'}"
        f" · Godot {godot} · Archetype {archetype}"
        f" · Result: {'SUCCESS' if ok else 'FAILED'}",
    ]
    if failed_phase:
        lines.append(f"- Failed in phase: {failed_phase}")
    lines += ["", "## What to review", ""]
    lines += _review_lines(catalog, issues, placeholders or [])

    lines += ["", "## Packs and licenses", ""]
    if catalog and catalog.packs:
        for pack in catalog.packs:
            license_files = ", ".join(pack.license_files) or "none found"
            source = (
                next((p.source for p in cfg.packs if p.pack_id == pack.pack_id), "") if cfg else ""
            )
            name = Path(source).name if source else ""
            origin = f" — source: {name}" if name else ""
            lines.append(f"- **{pack.pack_id}**{origin} — licenses: {license_files}")
            found = pack.effective_license()
            credit = "credit required" if found.attribution_required else "no credit required"
            who = f", by {found.author}" if found.author else ""
            lines.append(f"  - {licenses.label(found.license_id)}{who} ({credit})")
            lines += [f"  - warning: {w}" for w in pack.warnings]
    else:
        lines.append("No packs were read.")

    lines += ["", "## Summary", "", "| What | Count |", "| --- | --- |"]
    numbers = summary or counts(catalog, issues)
    for key, label in (
        ("assets", "Assets processed"),
        ("tilesets", "TileSets"),
        ("scenes", "Scenes"),
        ("animation_sets", "Animation sets"),
        ("warnings", "Warnings"),
        ("errors", "Errors"),
    ):
        lines.append(f"| {label} | {numbers.get(key, 0)} |")
    if catalog:
        by_role = Counter(
            str(catalog_mod.effective(a).get("role", "NONE"))
            for a in catalog.assets
            if a.status != "UNUSED"
        )
        lines += [
            "",
            "Assets by role: "
            + ", ".join(f"{labels.role_label(r)} {n}" for r, n in sorted(by_role.items())),
        ]

    lines += _tileset_lines(catalog)
    lines += _world_lines(project)
    lines += _scene_lines(project)
    lines += _animation_lines(catalog)
    if plan is not None:
        lines += _regeneration_lines(plan)
    lines += _validation_lines(project)
    lines += _smoke_lines(project)
    lines += _skipped_lines(skipped or {}, issues)

    lines += ["", "## Issues", ""]
    if issues:
        lines += [
            "| Code | Severity | File | Message | Fix |",
            "| --- | --- | --- | --- | --- |",
        ]
        for issue in sorted(issues, key=lambda i: (_ORDER[i.severity], i.code, i.message)):
            lines.append(
                f"| {issue.code} | {issue.severity} | {_cell(issue.file or '')} "
                f"| {_cell(issue.message)} | {_cell(issue.fix)} |"
            )
    else:
        lines.append("No issues.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- sections


def _bullet(issue: Issue) -> str:
    fix = f" Fix: {issue.fix}" if issue.fix else ""
    return f"- **{issue.code}** ({issue.severity}): {issue.message}{fix}"


def _review_lines(
    catalog: catalog_mod.Catalog | None, issues: list[Issue], placeholders: list[str]
) -> list[str]:
    """Every warning with its fix, grouped by priority: conflicts, placeholders, needs-review
    assets, assumed doors, licenses, everything else."""
    ordered = sorted(
        (i for i in issues if i.severity is not Severity.INFO),
        key=lambda i: (_ORDER[i.severity], i.code, i.message),
    )
    groups: list[tuple[str, list[str]]] = []
    groups.append(("Errors", [_bullet(i) for i in ordered if i.severity is Severity.ERROR]))
    conflicts = [_bullet(i) for i in ordered if i.code in _CONFLICT_CODES]
    if catalog:
        conflicts += [
            f"- Asset `{a.id}` is in CONFLICT and needs a decision in the audit."
            for a in sorted(catalog.assets, key=lambda a: a.id)
            if a.status == "CONFLICT"
        ]
    groups.append(("Conflicts", conflicts))
    if placeholders:
        names = ", ".join(sorted(placeholders))
        groups.append(("Placeholders", [f"- Placeholder assets are in use for: {names}."]))
    pending = sorted(a.id for a in catalog.assets if a.status == "NEEDS_REVIEW") if catalog else []
    if pending:
        shown = ", ".join(f"`{a}`" for a in pending[:10]) + (" ..." if len(pending) > 10 else "")
        groups.append(
            ("Assets to review", [f"- {len(pending)} asset(s) are NEEDS_REVIEW: {shown}."])
        )
    doors = (
        sorted(
            o.id
            for o in catalog.objects
            if o.role == "BUILDING" and o.status != "UNUSED" and not o.door
        )
        if catalog
        else []
    )
    groups.append(
        (
            "Assumed doors",
            [f"- `{d}` has no door point; the bottom center is assumed." for d in doors],
        )
    )
    groups.append(("Licenses", [_bullet(i) for i in ordered if i.code in _LICENSE_CODES]))
    handled = _CONFLICT_CODES | _LICENSE_CODES
    groups.append(
        (
            "Other",
            [
                _bullet(i)
                for i in ordered
                if i.severity is Severity.WARNING and i.code not in handled
            ],
        )
    )
    out: list[str] = []
    for title, items in groups:
        if items:
            out += [f"**{title}**", "", *items, ""]
    if not out:
        return ["Nothing needs review."]
    return out[:-1]


def _tileset_lines(catalog: catalog_mod.Catalog | None) -> list[str]:
    lines = ["", "## TileSets", ""]
    if not catalog or not catalog.tilesets:
        return [*lines, "No TileSets."]
    for tdef in catalog.tilesets:
        size = "x".join(str(v) for v in tdef.tile_size)
        lines.append(f"- **{tdef.name}** — tile size {size}, {len(tdef.sources)} source(s)")
        for src in sorted(tdef.sources, key=lambda s: int(s["source_id"])):
            lines.append(f"  - source {src['source_id']}: `{src['asset']}`")
        terrains = ", ".join(t["name"] for t in tdef.terrain_sets) or "none"
        lines.append(f"  - terrains: {terrains}")
    return lines


def _world_lines(project: Path | None) -> list[str]:
    """The world of areas (T13.20): what it is made of, and what the planner had to change."""
    from rpggen.core import world_plan

    plan = world_plan.load(Path(project)) if project else None
    if plan is None:
        return []
    lines = ["", "## World", "", f"- {world_plan.summary(plan)}"]
    key = plan.get("key")
    if key:
        holder = world_plan.area_of(plan, key["area"])
        opens = world_plan.area_of(plan, key["opens"])
        if holder and opens:
            lines.append(f"- The key to {opens['name']} lies in a chest in {holder['name']}.")
    lines += [f"- {note}" for note in plan.get("notes", [])]
    return lines


def _scene_lines(project: Path | None) -> list[str]:
    lines = ["", "## Scenes", ""]
    root = Path(project) / "generated" / "scenes" if project else None
    if root is None or not root.is_dir():
        return [*lines, "No generated scenes."]
    found = sorted(
        (d.name, sum(1 for _ in d.rglob("*.tscn"))) for d in root.iterdir() if d.is_dir()
    )
    rows = [f"- generated/scenes/{name}: {n}" for name, n in found if n]
    return [*lines, *(rows or ["No generated scenes."])]


def _animation_lines(catalog: catalog_mod.Catalog | None) -> list[str]:
    lines = ["", "## Animations", ""]
    rows: list[str] = []
    for asset in catalog.assets if catalog else []:
        if asset.status == "UNUSED":
            continue
        anims = catalog_mod.effective(asset).get("animations")
        if anims:
            rows.append(f"- `{asset.id}`: {', '.join(sorted(anims))}")
    return [*lines, *(rows or ["No animated assets."])]


def _capped(title: str, items: list[str]) -> list[str]:
    if not items:
        return [f"- {title}: none"]
    shown = [f"  - `{rel}`" for rel in items[:LIST_CAP]]
    more = [f"  - ... and {len(items) - LIST_CAP} more"] if len(items) > LIST_CAP else []
    return [f"- {title} ({len(items)}):", *shown, *more]


def _regeneration_lines(plan: PromotionPlan) -> list[str]:
    lines = ["", "## Regeneration", ""]
    lines += _capped("Written", sorted(plan.write))
    lines += _capped(
        "Kept because you changed them (the new version is next to them as .rpggen-new)",
        sorted(plan.conflicts),
    )
    lines += _capped("Not recreated because you deleted them", sorted(plan.skipped_deleted))
    lines += _capped("Removed (no longer generated, untouched by you)", sorted(plan.delete))
    return lines


def _read_results(project: Path | None, rel: str) -> dict[str, Any] | None:
    if project is None:
        return None
    path = Path(project) / rel
    if not path.is_file():
        return None
    data = jsonio.read(path)
    return data if isinstance(data, dict) else None


def _validation_lines(project: Path | None) -> list[str]:
    lines = ["", "## Validation", ""]
    data = _read_results(project, paths.RESULTS_VALIDATE)
    if data is None:
        return [*lines, "No validation results."]
    tally: dict[str, list[int]] = {}
    for item in data.get("items", []):
        row = tally.setdefault(str(item.get("check", "?")), [0, 0])
        row[0 if item.get("ok") else 1] += 1
    if not tally:
        return [*lines, "No checks ran."]
    lines += ["| Check | Passed | Failed |", "| --- | --- | --- |"]
    return lines + [f"| {name} | {p} | {f} |" for name, (p, f) in sorted(tally.items())]


def _smoke_lines(project: Path | None) -> list[str]:
    """The step table. Timings are left out so an unchanged project gives an identical report."""
    lines = ["", "## Smoke test", ""]
    data = _read_results(project, paths.RESULTS_SMOKE)
    if data is None:
        return [*lines, "The smoke test did not run."]
    items = data.get("items", [])
    if not items:
        return [*lines, "No steps ran."]
    lines += ["| Step | Name | Result |", "| --- | --- | --- |"]
    return lines + [
        f"| {i.get('step', '')} | {_cell(str(i.get('name', '')))} "
        f"| {'ok' if i.get('ok') else 'FAILED'} |"
        for i in items
    ]
