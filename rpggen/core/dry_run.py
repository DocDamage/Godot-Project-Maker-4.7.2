"""``rpggen generate --dry-run`` (T12.28): what a generation would find, and nothing is made.

It runs the checks of preflight that need no Godot, opens and analyses the packs, makes the
requirement check and plans the starter map, then reports. It creates no staging, runs no Godot
and leaves the target as it is: the packs are read, and the work folder of the analysis lives in
the system's temporary folder until the function returns.
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import paths
from rpggen.core import archive, inventory, map_preview, orchestrator, preflight, requirements
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.errors import Issue, IssueList, RpgGenError

log = logging.getLogger(__name__)

# What the plan counts, in the order of the summary.
PLAN_COUNTS = ("buildings", "npcs", "enemies", "chests", "decorations")


@dataclass
class DryRunResult:
    ok: bool
    target: Path
    issues: list[Issue]
    summary: dict[str, Any] = field(default_factory=dict)
    failed_phase: str | None = None  # the phase of a real run that would have stopped
    cancelled: bool = False
    timings: dict[str, float] = field(default_factory=dict)


class _Cancelled(Exception):
    pass


def _need(role: str, archetype: str) -> str:
    if role in requirements.REQUIRED.get(archetype, requirements.REQUIRED["turn_based"]):
        return "required"
    return "recommended" if role in requirements.recommended(archetype) else "optional"


def _roles(catalog: catalog_mod.Catalog, archetype: str) -> dict[str, dict[str, Any]]:
    counts = requirements.role_counts(catalog)
    names = (
        set(counts)
        | set(requirements.REQUIRED.get(archetype, []))
        | set(requirements.recommended(archetype))
    )
    return {
        name: {"count": counts.get(name, 0), "need": _need(name, archetype)}
        for name in sorted(names)
    }


def _placeholder_issues(issues: IssueList, roles: list[str]) -> IssueList:
    """The requirement issues of a run that was told to make placeholders: a missing role it
    would fill is reported as the info a real run reports (ASSET-011), not as missing."""
    out = IssueList()
    for issue in issues:
        role = issue.detail.get("role")
        if issue.code == "ASSET-010" and role in roles:
            out.add("ASSET-011", role=role)
        else:
            out.append(issue)
    return out


def run(
    cfg_path: Path,
    target: Path,
    *,
    godot_exe: Path | None = None,
    placeholders: list[str] | None = None,
    force_while_open: bool = False,
    accept_runtime_upgrade: bool = False,
    derive_tile_size: bool = False,
    is_cancelled: Any = lambda: False,
) -> DryRunResult:
    """Look at what ``orchestrator.run`` would do for ``cfg_path`` and ``target``.

    ``godot_exe`` is only looked for, never started. ``placeholders`` are the roles a real run
    would fill with debug placeholders.
    """
    roles_to_fill = [r.upper() for r in placeholders or []]
    state = orchestrator._State(
        Path(cfg_path), Path(target), Path(godot_exe or ""), orchestrator.Callbacks()
    )
    state.force_while_open = force_while_open
    state.accept_runtime_upgrade = accept_runtime_upgrade

    def result(failed_phase: str | None = None, cancelled: bool = False) -> DryRunResult:
        return DryRunResult(
            ok=not cancelled and not state.issues.has_errors(),
            target=Path(target),
            issues=list(state.issues),
            summary=summary,
            failed_phase=failed_phase,
            cancelled=cancelled,
            timings=dict(state.timings),
        )

    summary: dict[str, Any] = {}
    phase = "preflight"
    started = time.monotonic()
    try:
        if godot_exe is not None and not Path(godot_exe).exists():
            state.issues.add("ENV-001", path=str(godot_exe))
        orchestrator.check_target(state)
        state.timings[phase] = round(time.monotonic() - started, 2)
        if state.issues.has_errors():
            return result(phase)
        assert state.cfg is not None
        cfg = state.cfg

        phase, started = "catalog", time.monotonic()
        catalog = _analyse(state, derive_tile_size, is_cancelled)
        state.issues.extend(_placeholder_issues(requirements.check(catalog, cfg), roles_to_fill))
        state.timings[phase] = round(time.monotonic() - started, 2)
        summary = _summary(state, catalog, roles_to_fill, derive_tile_size, godot_exe)
        if state.issues.has_errors():
            return result(phase)

        phase, started = "plan", time.monotonic()
        summary["map"] = _plan(cfg, catalog)
        state.timings[phase] = round(time.monotonic() - started, 2)
        return result()
    except _Cancelled:
        return result(phase, cancelled=True)
    except catalog_mod.AssemblyCancelled:
        return result(phase, cancelled=True)
    except RpgGenError as exc:
        state.issues.append(exc.issue)
        return result(phase)
    except Exception as exc:  # noqa: BLE001 - as in a real run: a report, not a traceback
        log.error("unexpected error in the dry run (%s)", phase, exc_info=exc)
        reason = f"{type(exc).__name__}: {exc}".strip()
        state.issues.add("BUILD-005", phase=f"dry run, {phase}", reason=reason[:300])
        return result(phase)


def _analyse(
    state: orchestrator._State, derive_tile_size: bool, is_cancelled: Any
) -> catalog_mod.Catalog:
    """Open and analyse the packs the way the catalog phase does, without installing anything."""
    assert state.cfg is not None
    used: set[str] = set()
    for ref in state.cfg.packs:
        if is_cancelled():
            raise _Cancelled
        opened = archive.open_pack(Path(ref.source), used, pack_id=ref.pack_id)
        used.add(opened.pack_id)
        state.issues.extend(opened.issues)
        state.opened.append((opened, inventory.build_inventory(opened)))
    previous = None
    if preflight.is_rpggen_project(state.target):  # a regeneration builds on the user's decisions
        previous = catalog_mod.load(state.target / paths.CATALOG)
    with tempfile.TemporaryDirectory(prefix="rpggen_dry_") as work:
        catalog, issues, _generated = catalog_mod.assemble(
            state.opened, previous, [], work_dir=Path(work) / "work", is_cancelled=is_cancelled
        )
    known = {(i.code, i.message) for i in state.issues}
    state.issues.extend(i for i in issues if (i.code, i.message) not in known)
    if derive_tile_size:
        state.cfg.base_tile_size = catalog_mod.dominant_tile_size(catalog) or 16
    return catalog


def _summary(
    state: orchestrator._State,
    catalog: catalog_mod.Catalog,
    placeholders: list[str],
    derive_tile_size: bool,
    godot_exe: Path | None,
) -> dict[str, Any]:
    cfg = state.cfg
    assert cfg is not None
    inactive = {"UNUSED", "MISSING"}
    return {
        "project_name": cfg.project_name,
        "archetype": cfg.archetype,
        "regeneration": preflight.is_rpggen_project(state.target),
        "godot": str(godot_exe) if godot_exe is not None else None,
        "packs": [p.pack_id for p in cfg.packs],
        "tile_size": cfg.base_tile_size,
        "tile_size_from": "packs" if derive_tile_size else "config",
        "resolution": list(cfg.resolution),
        "assets": sum(1 for a in catalog.assets if a.status not in inactive),
        "objects": sum(1 for o in catalog.objects if o.status not in inactive),
        "tilesets": len(catalog.tilesets),
        "roles": _roles(catalog, cfg.archetype),
        "placeholders": sorted(
            r for r in placeholders if requirements.role_counts(catalog).get(r, 0) == 0
        ),
    }


def _plan(cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog) -> dict[str, Any]:
    """The starter map a real run would build: its size, what stands on it and the planner's
    warnings (for instance a building that does not fit). For a metroidvania, the world of
    rooms: how many, how large, and what the options make of it."""
    if cfg.archetype == "metroidvania":
        from rpggen.core import room_plan

        try:
            rooms = room_plan.plan(cfg.starter_map_options(), cfg.seed, catalog)
            added = cfg.starter_map_options().get("added_rooms", [])
            if added:
                rooms, _ids = room_plan.extend(rooms, added, cfg.seed)
        except room_plan.RoomPlanError as error:
            nothing = dict.fromkeys(PLAN_COUNTS, 0)
            return {"size": [0, 0], "world": "", "counts": nothing, "warnings": [str(error)]}
        every = rooms["list"]
        return {
            "size": list(rooms["room_size"]),
            "world": room_plan.summary(rooms),
            "rooms": [r["id"] for r in every],
            # what stands in the rooms, under the names the starter map's plan uses
            "counts": {
                "buildings": 0,
                "npcs": sum(1 for r in every if r.get("npc")),
                "enemies": sum(len(r.get("enemies", [])) for r in every),
                "chests": sum(1 for r in every if r.get("chest")),
                "decorations": sum(len(r.get("decorations", [])) for r in every),
            },
            "warnings": [],
        }
    imported = next(
        (m for m in catalog.maps if m["id"] == cfg.imported_map_selection()["starter"]), None
    )
    if imported is not None:  # the planner is skipped: the starter map is that map
        return {
            "size": list(imported["size"]),
            "imported": imported["id"],
            "counts": {},
            "warnings": [],
        }
    building = map_preview.building_info_for(catalog, cfg.starter.get("building", ""))
    plan = map_preview.plan(cfg.starter_map_options(), cfg.seed, building, cfg.archetype)
    return {
        "size": list(plan["size"]),
        "counts": {name: len(plan[name]) for name in PLAN_COUNTS},
        "warnings": list(plan["warnings"]),
    }


def format_summary(summary: dict[str, Any]) -> list[str]:
    """The human lines of a dry run's summary."""
    if not summary:
        return []

    def row(label: str, text: str) -> str:
        return f"{label + chr(58):<14}{text}"

    kind = f"{summary['archetype']}{', regeneration' if summary['regeneration'] else ''}"
    size = summary["resolution"]
    lines = [
        row("project", f"{summary['project_name']} ({kind})"),
        row("packs", ", ".join(summary["packs"])),
        row(
            "tile size",
            f"{summary['tile_size']} px (from the {summary['tile_size_from']}), "
            f"resolution {size[0]} x {size[1]}",
        ),
        row(
            "catalog",
            f"{summary['assets']} assets, {summary['objects']} objects, "
            f"{summary['tilesets']} tile sets",
        ),
    ]
    roles = summary["roles"]
    for need in ("required", "recommended", "optional"):
        found = [f"{n} {r['count']}" for n, r in roles.items() if r["need"] == need and r["count"]]
        absent = [n for n, r in roles.items() if r["need"] == need and not r["count"]]
        if found or absent:
            missing = f"  (missing: {', '.join(absent)})" if absent else ""
            lines.append(row(need, (", ".join(found) or "none") + missing))
    if summary["placeholders"]:
        lines.append(row("placeholders", ", ".join(summary["placeholders"])))
    if "map" in summary:
        plan = summary["map"]
        if "world" in plan:
            size = plan["size"]
            lines.append(row("world", f"{plan['world']}; rooms of {size[0]} x {size[1]} tiles"))
            lines.extend(row("", f"note: {w}") for w in plan["warnings"])
            return lines
        if "imported" in plan:
            size = plan["size"]
            lines.append(
                row("starter map", f"{plan['imported']} (imported), {size[0]} x {size[1]} tiles")
            )
            return lines
        counts = ", ".join(f"{plan['counts'][n]} {n}" for n in PLAN_COUNTS)
        lines.append(row("starter map", f"{plan['size'][0]} x {plan['size'][1]} tiles; {counts}"))
        lines.extend(row("", f"note: {w}") for w in plan["warnings"])
    return lines
