"""GENERATION_REPORT.md: the human-readable result of a run (T3.13 writes the basic sections,
T5.08 completes it). The text is deterministic: no timestamps."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from rpggen import __version__
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.errors import Issue, Severity

REPORT_MD = "GENERATION_REPORT.md"
_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


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
) -> str:
    godot = godot_version or (cfg.godot_version if cfg else "")
    archetype = cfg.archetype if cfg else "?"
    lines = [
        "# Generation Report",
        "",
        f"- Generator: rpggen {__version__} · Godot {godot} · Archetype {archetype}"
        f" · Result: {'SUCCESS' if ok else 'FAILED'}",
    ]
    if failed_phase:
        lines.append(f"- Failed in phase: {failed_phase}")
    lines += ["", "## What to review", ""]
    review = sorted(
        (i for i in issues if i.severity is not Severity.INFO),
        key=lambda i: (_ORDER[i.severity], i.code, i.message),
    )
    extras = []
    if placeholders:
        extras.append(f"Placeholder assets are in use for: {', '.join(sorted(placeholders))}.")
    if catalog:
        pending = sum(1 for a in catalog.assets if a.status == "NEEDS_REVIEW")
        conflicts = sum(1 for a in catalog.assets if a.status == "CONFLICT")
        if conflicts:
            extras.append(f"{conflicts} asset(s) are in CONFLICT and need a decision.")
        if pending:
            extras.append(f"{pending} asset(s) are still NEEDS_REVIEW.")
    if not review and not extras:
        lines.append("Nothing needs review.")
    for text in extras:
        lines.append(f"- {text}")
    for issue in review:
        fix = f" Fix: {issue.fix}" if issue.fix else ""
        lines.append(f"- **{issue.code}** ({issue.severity}): {issue.message}{fix}")

    lines += ["", "## Packs and licenses", ""]
    if catalog and catalog.packs:
        for pack in catalog.packs:
            licenses = ", ".join(pack.license_files) or "none found"
            lines.append(f"- **{pack.pack_id}** — licenses: {licenses}")
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
            "Assets by role: " + ", ".join(f"{r} {n}" for r, n in sorted(by_role.items())),
        ]

    lines += ["", "## Issues", ""]
    if issues:
        lines += ["| Code | Severity | Message | Fix |", "| --- | --- | --- | --- |"]
        for issue in sorted(issues, key=lambda i: (_ORDER[i.severity], i.code, i.message)):
            lines.append(
                f"| {issue.code} | {issue.severity} | {_cell(issue.message)} | {_cell(issue.fix)} |"
            )
    else:
        lines.append("No issues.")
    return "\n".join(lines) + "\n"
