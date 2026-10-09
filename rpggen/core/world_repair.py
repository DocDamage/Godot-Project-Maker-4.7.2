"""World repair (T13.24): rpggen mends the maps it made; yours it mends when you ask.

The work is done by the project's own tool (``generated/builder/tools/world_repair.gd``), run
headless: it reads every map under ``game/maps``, finds the doors that lead nowhere and the maps
the starter map cannot reach, and adds spawn points and doors (or points a door at a map that
exists). This module decides **which maps the tool may write**:

* ``auto`` (after a generation): only the maps whose hash is still the ``map_hash`` the stored
  world plan recorded when rpggen built them. A map a person changed is never touched by itself;
  what it would need is *offered* instead.
* ``repair`` (the Results page's fix, ``rpggen-cli repair-world``): every map.

Before anything is written the maps go to ``.rpggen_backups`` (as the conflict resolver does), so
*Restore previous* undoes a repair. Nothing runs while a Godot editor has the project open.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import paths
from rpggen.core import godot, ledger, promote, world_plan
from rpggen.errors import RpgGenError

TOOL = "res://generated/builder/tools/world_repair.gd"
RESULT_FILE = "rpggen/world_repair.json"
MARK = "[rpggen] WORLD_REPAIR "
TIMEOUT_S = 180
MAPS_DIR = "game/maps"
# the validator's codes this module answers to
CODES = ("VAL-027", "VAL-028")


@dataclass
class RepairResult:
    """What a run did (or, for a dry run, would do). Every line is ``{kind, map, node, what}``."""

    repairs: list[dict[str, str]] = field(default_factory=list)  # written (or to be written)
    offered: list[dict[str, str]] = field(default_factory=list)  # on maps the run may not write
    unfixable: list[dict[str, str]] = field(default_factory=list)
    backup: Path | None = None
    dry_run: bool = False
    ran: bool = True  # False: there was nothing to look at (no tool, no maps)

    @property
    def maps(self) -> list[str]:
        """The project-relative maps the repairs change, sorted."""
        return sorted({line["map"] for line in self.repairs})

    def to_json(self) -> dict[str, Any]:
        return {
            "repairs": self.repairs,
            "offered": self.offered,
            "unfixable": self.unfixable,
            "backup": self.backup.name if self.backup else None,
            "dry_run": self.dry_run,
        }


def tool_path(target: Path) -> Path:
    return Path(target) / "generated" / "builder" / "tools" / "world_repair.gd"


def available(target: Path) -> bool:
    """True when the project has what a repair runs: the tool, the library it loads (part of
    the editor tools, which a project may be generated without) and maps to look at."""
    target = Path(target)
    library = target / "addons" / "rpg_project_tools" / "tools" / "world_repair.gd"
    return tool_path(target).is_file() and library.is_file() and (target / MAPS_DIR).is_dir()


def unedited_maps(target: Path) -> list[str]:
    """The maps (project-relative) rpggen built and nobody changed since: their hash is the
    ``map_hash`` of the stored world plan."""
    plan = world_plan.load(target)
    if plan is None:
        return []
    out = []
    # the areas of a top-down world, and the rooms of a metroidvania (T14.06)
    for area in [*plan["areas"], *(plan.get("rooms") or {}).get("list", [])]:
        entry = plan["maps"].get(area["id"])
        file = Path(target) / area["map"]
        if entry and file.is_file() and ledger.file_hash(file) == entry["map_hash"]:
            out.append(area["map"])
    return sorted(out)


def _parse(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        at = line.find(MARK)
        if at >= 0:
            try:
                data = json.loads(line[at + len(MARK) :])
            except ValueError:
                return None
            return data if isinstance(data, dict) else None
    return None


def _lines(data: dict[str, Any], key: str) -> list[dict[str, str]]:
    out = []
    for raw in data.get(key, []):
        if isinstance(raw, dict):
            out.append({k: str(raw.get(k, "")) for k in ("kind", "map", "node", "what")})
    return out


def _run_tool(
    target: Path, godot_exe: Path, only: list[str] | None, dry_run: bool
) -> dict[str, Any]:
    args = ["--script", TOOL, "--"]
    if dry_run:
        args.append("--dry-run")
    if only is not None:
        args.append("--only=" + ",".join(only))
    run = godot.run_godot(
        godot.find_console_exe(Path(godot_exe)),
        Path(target),
        args,
        timeout_s=TIMEOUT_S,
        log_name="world_repair",
        log_dir=Path(target) / "rpggen" / "logs",
    )
    data = _parse(run.stdout)
    if data is None:
        reason = "it timed out" if run.timed_out else f"exit code {run.returncode}"
        raise RpgGenError("BUILD-002", recipe="world_repair.gd", reason=f"no result ({reason})")
    return data


def _after_writing(target: Path, changed: list[str], unedited: set[str]) -> None:
    """A map rpggen has just mended is still rpggen's: its new hash goes into the world plan
    (so the next run may mend it again) and into the ledger (so it does not look edited)."""
    plan = world_plan.load(target)
    current = promote.load_ledger(target)
    touched = False
    for rel in changed:
        if rel not in unedited:
            continue
        digest = ledger.file_hash(Path(target) / rel)
        if plan is not None:
            for area in plan["areas"]:
                if area["map"] == rel and area["id"] in plan["maps"]:
                    plan["maps"][area["id"]]["map_hash"] = digest
        if rel in current.files:
            current.files[rel].sha256 = digest
            touched = True
    if plan is not None:
        world_plan.save(target, plan)
    if touched:
        current.save(Path(target) / paths.LEDGER)


def run(
    target: Path,
    godot_exe: Path,
    *,
    only: list[str] | None = None,
    dry_run: bool = False,
    force_while_open: bool = False,
) -> RepairResult:
    """Look at the world and mend it. ``only`` are the maps (project-relative) the tool may
    write; None means every map. ``dry_run`` writes nothing at all. ``REGEN-005`` when a Godot
    editor has the project open (unless ``force_while_open``)."""
    target = Path(target)
    if not available(target):
        return RepairResult(dry_run=dry_run, ran=False)
    if not dry_run and not force_while_open and promote.editor_open(target):
        raise RpgGenError("REGEN-005", path=str(target))
    preview = _run_tool(target, godot_exe, only, dry_run=True)
    result = RepairResult(
        repairs=_lines(preview, "repairs"),
        offered=_lines(preview, "skipped"),
        unfixable=_lines(preview, "unfixable"),
        dry_run=dry_run,
    )
    if dry_run or not result.repairs:
        return result
    unedited = set(unedited_maps(target))
    backup = promote._backup_dir(target)
    promote._backup_files(
        target, backup, [*result.maps, world_plan.PLAN_FILE, RESULT_FILE, paths.LEDGER]
    )
    done = _run_tool(target, godot_exe, only, dry_run=False)
    result.repairs = _lines(done, "repairs")
    result.offered = _lines(done, "skipped")
    result.unfixable = _lines(done, "unfixable")
    result.backup = backup
    _after_writing(target, result.maps, unedited)
    promote.rotate_backups(target, promote.KEEP_BACKUPS + 1)
    return result


def auto(target: Path, godot_exe: Path, *, force_while_open: bool = False) -> RepairResult:
    """After a generation: mend the maps rpggen made and nobody changed. Nothing runs for a
    project without a stored world plan (a 1.0 project): its maps are all its user's."""
    if world_plan.load(target) is None:
        return RepairResult(ran=False)
    return run(target, godot_exe, only=unedited_maps(target), force_while_open=force_while_open)


def needed(codes: list[str]) -> bool:
    """True when a validation reported something a repair could mend."""
    return any(code in CODES for code in codes)


def report_lines(result: RepairResult | None) -> list[str]:
    """The *World repairs* section of the report ([] when nothing was done or offered)."""
    if result is None or not (result.repairs or result.offered or result.unfixable):
        return []
    lines = ["", "## World repairs", ""]
    for line in result.repairs:
        lines.append(f"- {line['map']}: {line['what']}.")
    if result.backup is not None:
        lines.append(
            f"- The maps as they were are in `.rpggen_backups/{result.backup.name}`; "
            "*Restore previous* puts them back."
        )
    for line in result.offered:
        lines.append(
            f"- Not done ({line['map']} was changed by you): {line['what']}. "
            "*Repair the world…* on the Results page does it."
        )
    for line in result.unfixable:
        lines.append(f"- Cannot be mended: {line['what']}.")
    return lines


def summary(result: RepairResult) -> str:
    """One line for a log or the command line."""
    if not result.ran:
        return "world repair: nothing to look at"
    verb = "would make" if result.dry_run else "made"
    parts = [f"{verb} {len(result.repairs)} repair{'s' if len(result.repairs) != 1 else ''}"]
    if result.offered:
        parts.append(f"{len(result.offered)} offered for maps you changed")
    if result.unfixable:
        parts.append(f"{len(result.unfixable)} cannot be mended")
    return "world repair: " + ", ".join(parts)
