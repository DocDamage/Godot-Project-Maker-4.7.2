from __future__ import annotations

import logging
import os
import shutil
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, ids, jsonio, logging_setup, paths
from rpggen.core import (
    app_settings,
    archive,
    export_check,
    godot,
    godot_log,
    inventory,
    placeholders,
    preflight,
    promote,
    requirements,
    runtime_version,
    sound_slots,
    staging,
    vcs,
    world_plan,
    world_repair,
)
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import report as report_mod
from rpggen.core.ledger import Ledger
from rpggen.errors import CODES, Issue, IssueList, RpgGenError, Severity

log = logging.getLogger(__name__)

PHASES_M1 = [
    "preflight",
    "stage",
    "install",
    "catalog",
    "import",
    "build",
    "validate",
    "smoke",
    "export",
    "promote",
    "report",
]
REPORT_NAME = "generation_report.json"
SMOKE_STEPS_M1 = "res://generated/builder/smoke/smoke_steps_m1.gd"
SMOKE_STEPS_M4 = "res://generated/builder/smoke/smoke_steps_m4.gd"
SMOKE_STEPS_M6 = "res://generated/builder/smoke/smoke_steps_m6.gd"
# The M6 file composes the M1 and M4 steps in the right order (the game starts at the title).
SMOKE_STEPS = SMOKE_STEPS_M6
SMOKE_STEPS_TURN_BASED = "res://generated/builder/smoke/smoke_steps_turn_based.gd"
SMOKE_STEPS_ARPG = "res://generated/builder/smoke/smoke_steps_arpg.gd"
# The archetype's own steps run after the shared sequence (which ends in the starter map).
ARCHETYPE_SMOKE_STEPS = {"turn_based": SMOKE_STEPS_TURN_BASED, "arpg": SMOKE_STEPS_ARPG}


def smoke_steps_for(archetype: str) -> str:
    """Comma-separated steps scripts for the smoke run of a project with this archetype."""
    extra = ARCHETYPE_SMOKE_STEPS.get(archetype)
    return f"{SMOKE_STEPS},{extra}" if extra else SMOKE_STEPS


@dataclass
class Callbacks:
    on_phase: Callable[[str, int, int], None] = lambda name, i, n: None  # phase i of n
    on_log: Callable[[str], None] = lambda line: None
    is_cancelled: Callable[[], bool] = lambda: False
    on_skip: Callable[[str, str], None] = lambda phase, code: None  # a check that did not run
    # progress inside a Godot phase: (phase, i, n, label); n is 0 when only a label is known
    on_step: Callable[[str, int, int, str], None] = lambda phase, i, n, label: None
    # a regeneration that is about to write, replace or delete files asks first; False cancels
    confirm_promotion: Callable[[promote.PromotionSummary], bool] = lambda summary: True


@dataclass
class RunResult:
    ok: bool
    target: Path
    issues: list[Issue]
    report_path: Path | None
    failed_staging: Path | None
    failed_phase: str | None = None
    catalog: catalog_mod.Catalog | None = None
    cfg: config_mod.GeneratorConfig | None = None
    cancelled: bool = False
    timings: dict[str, float] = field(default_factory=dict)  # seconds per phase (never in a file)
    skipped: dict[str, str] = field(default_factory=dict)  # a phase that did not run -> issue code
    run_id: str = ""  # eight hex characters: the lines of this run in the application log
    world_repair: world_repair.RepairResult | None = None  # T13.24: what was mended, or offered


class _Stop(Exception):
    """Internal: a phase decided the run cannot continue (issues already recorded)."""


class _Cancelled(_Stop):
    """Internal: the user cancelled; staging is discarded and nothing is delivered."""


@dataclass
class _State:
    cfg_path: Path | None
    target: Path
    godot_exe: Path
    cb: Callbacks
    issues: IssueList = field(default_factory=IssueList)
    cfg: config_mod.GeneratorConfig | None = None
    catalog: catalog_mod.Catalog | None = None
    staging: staging.Staging | None = None
    log_dir: Path | None = None
    phases_done: list[str] = field(default_factory=list)
    opened: list[tuple[archive.OpenedPack, inventory.Inventory]] = field(default_factory=list)
    generated: dict[str, str] = field(default_factory=dict)
    placeholders: list[str] = field(default_factory=list)
    current_phase: str | None = None
    catalog_in: catalog_mod.Catalog | None = None  # in-memory catalog (user overrides) to build on
    force_while_open: bool = False  # regenerate even if a Godot editor seems to be open
    old_ledger: Ledger | None = None  # regeneration: the target's ledger before this run
    promotion: promote.PromotionResult | None = None
    git_message: str | None = None  # commit the result with this message (git init if needed)
    pack_files: set[str] = field(default_factory=set)  # every pack file installed this run
    accept_runtime_upgrade: bool = False  # confirm a major runtime version increase
    # None: the config's ``repair_world`` decides; False: the command line's --no-repair-world
    repair_world: bool | None = None
    world_repair: world_repair.RepairResult | None = None  # what the repair after promotion did
    runtime: runtime_version.UpgradeInfo | None = None  # templates' runtime vs. the target's
    timings: dict[str, float] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    run_id: str = field(default_factory=logging_setup.new_run_id)
    derive_tile_size: bool = False  # the --pack path: base_tile_size comes from the packs


# --------------------------------------------------------------------------- helpers


def _issues_from_results(results_path: Path, state: _State) -> bool:
    """Add the issues of a Godot results file; returns False when it is missing or has errors."""
    if not results_path.exists():
        return False
    data = jsonio.read(results_path)
    for item in data.get("issues", []):
        code = item.get("code", "")
        info = CODES.get(code)
        state.issues.append(
            Issue(
                code,
                Severity(item.get("severity", "error")),
                item.get("message", ""),
                item.get("fix") or (info.fix if info else ""),
                item.get("file"),
            )
        )
    return not any(i.get("severity") == "error" for i in data.get("issues", [])) and bool(
        data.get("ok", False)
    )


def _run_phase_godot(
    state: _State, args: list[str], timeout_s: int, log_name: str, phase: str
) -> godot.GodotRun:
    assert state.staging is not None and state.log_dir is not None
    forwarder = godot.LineForwarder(phase, state.cb.on_log, state.cb.on_step)
    try:
        run = godot.run_godot(
            state.godot_exe,
            state.staging.staging,
            args,
            timeout_s=timeout_s,
            log_name=log_name,
            log_dir=state.log_dir,
            is_cancelled=state.cb.is_cancelled,
            on_line=forwarder.feed,
        )
    finally:
        forwarder.close()
    # a Ctrl+C in the console reaches Godot too: if it died of that before the poll saw the
    # cancel, this is still a cancel and not a failed phase
    if run.cancelled or state.cb.is_cancelled():
        raise _Cancelled
    if run.timed_out:
        state.issues.add("BUILD-003", phase=phase, seconds=timeout_s)
        raise _Stop
    return run


def _skip(state: _State, phase: str, code: str, **detail: Any) -> None:
    """A check that did not run: remember it (never show it as passed) and add its note."""
    state.skipped[phase] = code
    if not any(i.code == code for i in state.issues):
        state.issues.add(code, **detail)
    state.cb.on_skip(phase, code)


def _results_path(state: _State, rel: str) -> Path:
    assert state.staging is not None
    return state.staging.staging / rel


# --------------------------------------------------------------------------- phases


def phase_preflight(state: _State) -> None:
    exe = Path(state.godot_exe)
    if not exe.exists():
        raise RpgGenError("ENV-001", path=str(exe))
    version = godot.detect_version(exe)
    for issue in godot.check_version(version):
        state.issues.append(issue)
    check_target(state)


def check_target(state: _State) -> None:
    """The part of preflight that needs no Godot: load the config, check the target and the
    packs, refuse a project that is open in an editor, and look at the runtime version. The dry
    run of ``rpggen generate --dry-run`` makes exactly these checks."""
    if state.cfg is None:
        assert state.cfg_path is not None
        state.cfg = config_mod.load(state.cfg_path)
    sources = [Path(p.source) for p in state.cfg.packs]
    state.issues.extend(preflight.check_target(state.target, sources))
    if (
        preflight.is_rpggen_project(state.target)
        and not state.force_while_open
        and promote.editor_open(state.target)
    ):
        raise RpgGenError("REGEN-005", path=str(state.target))
    info = runtime_version.check_upgrade(
        paths.templates_root(), state.target if preflight.is_rpggen_project(state.target) else None
    )
    state.runtime = info
    if info.needs_confirmation and not state.accept_runtime_upgrade:
        assert info.old is not None
        for line in info.changelog_text.splitlines():
            state.cb.on_log(line)
        raise RpgGenError("REGEN-006", old=info.old, new=info.new)


def phase_stage(state: _State) -> None:
    state.staging = staging.create_staging(Path(state.target))
    if state.staging.regenerate:
        state.old_ledger = promote.load_ledger(state.target)
        if state.catalog_in is None:
            state.catalog_in = catalog_mod.load(Path(state.target) / paths.CATALOG)
    state.log_dir = state.staging.staging / "rpggen" / "logs"
    state.log_dir.mkdir(parents=True, exist_ok=True)


def phase_install(state: _State) -> None:
    assert state.staging is not None and state.cfg is not None
    staging.install_templates(
        state.staging,
        paths.templates_root(),
        state.cfg.archetype,
        editor_tools=bool(state.cfg.features.get("editor_tools", True)),
    )
    used: set[str] = set()
    for ref in state.cfg.packs:
        if state.cb.is_cancelled():
            raise _Cancelled
        opened = archive.open_pack(Path(ref.source), used, pack_id=ref.pack_id)
        used.add(opened.pack_id)
        state.issues.extend(opened.issues)
        inv = inventory.build_inventory(opened)
        state.opened.append((opened, inv))
        state.pack_files.update(staging.install_pack(state.staging, opened.root, ref.pack_id, inv))


def phase_catalog(state: _State) -> None:
    assert state.staging is not None and state.cfg is not None and state.log_dir is not None
    work_dir = state.staging.staging / "rpggen" / "work"
    try:
        catalog, issues, generated = catalog_mod.assemble(
            state.opened,
            state.catalog_in,
            [],
            work_dir=work_dir,
            is_cancelled=state.cb.is_cancelled,
        )
    except catalog_mod.AssemblyCancelled:
        raise _Cancelled from None
    # archive issues were reported while opening the packs; do not list them twice
    known = {(i.code, i.message) for i in state.issues}
    state.issues.extend(i for i in issues if (i.code, i.message) not in known)
    staging.install_generated(state.staging, generated)
    shutil.rmtree(work_dir, ignore_errors=True)
    if state.derive_tile_size:
        derived = catalog_mod.dominant_tile_size(catalog)
        state.cfg.base_tile_size = derived or 16
        state.cb.on_log(f"base tile size {state.cfg.base_tile_size} (from the packs)")
    if state.placeholders:
        _written, placeholder_issues = placeholders.add_placeholder_assets(
            catalog, state.placeholders, state.cfg.base_tile_size, state.staging.staging
        )
        state.issues.extend(placeholder_issues)
    state.catalog = catalog
    if not state.cfg.sounds:
        # nothing was chosen (the command line, an older project): the packs' audio is used
        state.cfg.sounds = sound_slots.default_sounds(catalog)
    state.generated = generated
    _plan_world(state, catalog)
    if state.staging.regenerate:
        # Files of assets that vanished from their pack stay: tile set sources, scenes and
        # animations built from them keep loading until the user confirms the removal.
        assert state.old_ledger is not None
        keep = state.pack_files | {a.path for a in catalog.assets if a.status == "MISSING"}
        state.issues.extend(staging.prune_packs(state.staging, state.old_ledger, keep))
    # A required role without any asset stops generation before Godot runs.
    state.issues.extend(requirements.check(catalog, state.cfg))
    state.issues.extend(staging.write_project_files(state.staging, state.cfg, catalog))


def _plan_world(state: _State, catalog: catalog_mod.Catalog) -> None:
    """``starter_map.areas`` (T13.20): the world plan goes into the staging copy, where the
    recipes read it. A project whose world exists keeps its stored plan; new rows are added."""
    assert state.staging is not None and state.cfg is not None
    if state.cfg.archetype == "metroidvania":
        _plan_rooms(state, catalog)
        return
    areas = state.cfg.starter_map.get("areas")
    if not areas:
        return
    root = state.staging.staging
    try:
        plan, notes = world_plan.for_project(
            root,
            areas,
            state.cfg.seed,
            catalog,
            tuple(state.cfg.starter_map.get("size", (40, 30))),
        )
    except world_plan.WorldPlanError as exc:
        state.issues.add("CAT-002", file="config", reason=f"/starter_map/areas: {exc}")
        raise _Stop from None
    world_plan.save(root, plan)
    state.cb.on_log("world: " + world_plan.summary(plan))
    for note in [*plan["notes"], *notes]:
        state.cb.on_log("world: " + note)


def _plan_rooms(state: _State, catalog: catalog_mod.Catalog) -> None:
    """A metroidvania's rooms (T14.06): planned once from the *Starter world* options and the
    seed, stored like the world of areas, and never planned again once a room exists."""
    from rpggen.core import room_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    try:
        plan, notes = room_plan.for_project(
            root, state.cfg.starter_map_options(), state.cfg.seed, catalog
        )
    except room_plan.RoomPlanError as exc:
        state.issues.add("CAT-002", file="config", reason=f"/starter_map: {exc}")
        raise _Stop from None
    world_plan.save(root, plan)
    state.cb.on_log("world: " + room_plan.summary(plan["rooms"]))
    for note in [*plan["notes"], *notes]:
        state.cb.on_log("world: " + note)


def _record_world_hashes(state: _State) -> None:
    """After the build: the hash of every area map rpggen has just made, so that a later run
    can tell a map nobody edited from one a person changed (T13.24)."""
    assert state.staging is not None
    root = state.staging.staging
    plan = world_plan.load(root)
    if plan is None:
        return
    if world_plan.record_hashes(root, plan, state.target if state.staging.regenerate else None):
        world_plan.save(root, plan)


def phase_import(state: _State) -> None:
    assert state.staging is not None and state.log_dir is not None
    forwarder = godot.LineForwarder("import", state.cb.on_log, state.cb.on_step)
    try:
        run = godot.run_godot(
            godot.find_console_exe(state.godot_exe),
            state.staging.staging,
            ["--import"],
            timeout_s=godot.IMPORT_TIMEOUT_S,
            log_name="import",
            log_dir=state.log_dir,
            is_cancelled=state.cb.is_cancelled,
            on_line=forwarder.feed,
        )
    finally:
        forwarder.close()
    if run.cancelled or state.cb.is_cancelled():
        raise _Cancelled
    if run.timed_out:
        state.issues.add("BUILD-003", phase="import", seconds=godot.IMPORT_TIMEOUT_S)
        raise _Stop
    if run.returncode != 0:
        state.issues.add("BUILD-001", code=run.returncode)
        raise _Stop


def phase_build(state: _State) -> None:
    run = _run_phase_godot(
        state,
        ["--script", "res://generated/builder/build.gd"],
        godot.BUILD_TIMEOUT_S,
        "build",
        "build",
    )
    results = _results_path(state, paths.RESULTS_BUILD)
    ok = _issues_from_results(results, state)
    if not results.exists():
        state.issues.add(
            "BUILD-002", recipe="build.gd", reason=f"no results written (exit {run.returncode})"
        )
        raise _Stop
    if not ok or run.returncode != 0:
        if not state.issues.has_errors():
            state.issues.add("BUILD-002", recipe="build.gd", reason=f"exit code {run.returncode}")
        raise _Stop
    _record_world_hashes(state)


def _sabotage(state: _State) -> None:
    """Test hook, honored only when RPGGEN_DEV=1: breaks the player script before validation."""
    assert state.staging is not None
    if (
        os.environ.get("RPGGEN_DEV") == "1"
        and os.environ.get("RPGGEN_TEST_SABOTAGE") == "broken_player"
    ):
        target = state.staging.staging / "addons/rpg_runtime/actors/actor.gd"
        with open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("\nthis is not valid gdscript !!!\n")


def phase_validate(state: _State) -> None:
    _sabotage(state)
    run = _run_phase_godot(
        state,
        ["--script", "res://generated/builder/validate.gd"],
        godot.VALIDATE_TIMEOUT_S,
        "validate",
        "validate",
    )
    results = _results_path(state, paths.RESULTS_VALIDATE)
    ok = _issues_from_results(results, state)
    scanned = godot_log.scan(run.log_path.read_text(encoding="utf-8", errors="replace"))
    state.issues.extend(scanned)
    if not results.exists() and not state.issues.has_errors():
        state.issues.add("VAL-013", line=f"validate wrote no results (exit {run.returncode})")
    if not ok or scanned or run.returncode != 0 or state.issues.has_errors():
        if not state.issues.has_errors():
            state.issues.add("VAL-013", line=f"validate exited with {run.returncode}")
        raise _Stop


STARTER_VIEW = "rpggen/results/starter_map_cells.json"
STARTER_PICTURE = "rpggen/results/starter_map.png"


def _starter_picture(state: _State) -> None:
    """A picture of the starter map as it was really built (T11.27), for the Results page.

    Headless Godot cannot take a screenshot, so a Godot script dumps the cells and the entities
    and the picture is drawn here. Any problem is a line in the log, never a failed generation."""
    assert state.staging is not None and state.log_dir is not None
    root = state.staging.staging
    if not (root / "game" / "maps" / "starter_map.tscn").is_file():
        return
    view_path = root / STARTER_VIEW
    try:
        run = godot.run_godot(
            godot.find_console_exe(state.godot_exe),
            root,
            [
                "--script",
                "res://generated/builder/tools/dump_map_view.gd",
                "--",
                f"--out={view_path}",
            ],
            timeout_s=60,
            log_name="map_view",
            log_dir=state.log_dir,
            is_cancelled=state.cb.is_cancelled,
        )
        if run.cancelled or state.cb.is_cancelled():
            raise _Cancelled
        if run.returncode != 0 or not view_path.is_file():
            state.cb.on_log("starter map picture skipped: Godot could not dump the map")
            return
        from rpggen.core import map_preview

        image = map_preview.render_view(jsonio.read(view_path), root, 2)
        image.save(root / STARTER_PICTURE, format="PNG")
        state.cb.on_log(f"starter map picture written to {STARTER_PICTURE}")
    except _Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001 - the picture is a nicety
        state.cb.on_log(f"starter map picture skipped: {exc}")


def phase_smoke(state: _State) -> None:
    _run_smoke(state)
    _starter_picture(state)


def _run_smoke(state: _State) -> None:
    assert state.cfg is not None
    if not state.cfg.validation.get("smoke_test", True):
        _skip(state, "smoke", "VAL-021")
        return
    run = _run_phase_godot(
        state,
        ["--", "--rpg-smoke", f"--rpg-smoke-steps={smoke_steps_for(state.cfg.archetype)}"],
        godot.SMOKE_TIMEOUT_S,
        "smoke",
        "smoke",
    )
    results = _results_path(state, paths.RESULTS_SMOKE)
    ok = _issues_from_results(results, state)
    scanned = godot_log.scan(run.log_path.read_text(encoding="utf-8", errors="replace"))
    # Smoke steps report their own failures through SMOKE-* issues; log scanning adds the rest.
    state.issues.extend(i for i in scanned if i.code == "VAL-013")
    if not results.exists():
        state.issues.add(
            "SMOKE-001",
            step=0,
            name="startup",
            detail=f"no results written (exit {run.returncode})",
        )
        raise _Stop
    if not ok or scanned or run.returncode != 0:
        if not state.issues.has_errors():
            state.issues.add("SMOKE-001", step=0, name="exit", detail=f"exit code {run.returncode}")
        raise _Stop


def phase_export(state: _State) -> None:
    """Optional: export the staged project once to prove it exports (needs export templates)."""
    assert state.cfg is not None and state.staging is not None and state.log_dir is not None
    if not state.cfg.validation.get("export_check", True):
        _skip(state, "export", "VAL-022")
        return
    issues, ran = export_check.run_check(
        state.godot_exe,
        state.staging.staging,
        state.cfg.project_name,
        state.log_dir,
        is_cancelled=state.cb.is_cancelled,
        targets=state.cfg.selected_export_targets(),
    )
    if state.cb.is_cancelled():
        raise _Cancelled
    state.issues.extend(issues)
    if not ran:  # no target had export templates: no test export happened
        state.skipped["export"] = "ENV-010"
        state.cb.on_skip("export", "ENV-010")
    if any(i.severity is Severity.ERROR for i in issues):
        raise _Stop


def phase_promote(state: _State) -> None:
    assert state.staging is not None
    try:
        state.promotion = promote.promote(state.staging, state.cb.confirm_promotion)
    except promote.PromotionDeclined:
        raise _Cancelled from None  # the work folder goes, the project is as it was
    state.issues.extend(state.promotion.issues)


def _report_data(state: _State, ok: bool) -> dict[str, Any]:
    return {
        "report_version": 1,
        "generator_version": __version__,
        "runtime_version": state.runtime.new if state.runtime else "",
        "ok": ok,
        "phases_completed": list(state.phases_done),
        "run_id": state.run_id,
        **({"skipped": dict(sorted(state.skipped.items()))} if state.skipped else {}),
        "issues": state.issues.to_json(),
    }


def _commit_files(state: _State) -> list[str]:
    """What rpggen wrote or deleted in the target: the promoted files, the conflict copies, the
    ledger and the reports. Only these are committed in a repository that already existed."""
    found = {paths.LEDGER, f"rpggen/{REPORT_NAME}", report_mod.REPORT_MD}
    if state.promotion is not None:
        plan = state.promotion.plan
        found |= set(plan.write) | set(plan.delete)
        found |= {f"{rel}.rpggen-new" for rel in plan.conflicts}
    return sorted(found)


def _repair_world(state: _State) -> None:
    """After a successful promotion (T13.24): when the validator found a door that leads nowhere
    or a map that cannot be reached, mend the maps rpggen made and nobody changed. What a map of
    the user's would need is only listed. A failure here never fails the generation."""
    assert state.cfg is not None
    wanted = state.cfg.repair_world if state.repair_world is None else state.repair_world
    if not wanted or state.issues.has_errors():
        return
    if not world_repair.needed([i.code for i in state.issues]):
        return
    try:
        result = world_repair.auto(
            Path(state.target), state.godot_exe, force_while_open=state.force_while_open
        )
    except RpgGenError as exc:
        state.cb.on_log(f"world repair: not done ({exc.issue.message})")
        return
    if not result.ran:
        return
    state.world_repair = result
    state.cb.on_log(world_repair.summary(result))
    for line in result.repairs:
        state.cb.on_log(f"world repair: {line['map']}: {line['what']}")
    if result.repairs and not result.offered and not result.unfixable:
        # everything the validator warned about is mended: the warnings are history
        kept = [i for i in state.issues if i.code not in world_repair.CODES]
        state.issues[:] = kept


def phase_report(state: _State) -> None:
    _repair_world(state)
    ok = not state.issues.has_errors()
    target = Path(state.target)
    path = target / "rpggen" / REPORT_NAME
    assert state.staging is not None
    plan = state.promotion.plan if state.promotion and state.staging.regenerate else None
    unchanged = plan is not None and not (
        plan.write or plan.conflicts or plan.delete or plan.skipped_deleted
    )
    existing_repo = bool(state.git_message) and vcs.is_repository(target)
    files = _commit_files(state) if existing_repo else None
    if files is not None and vcs.foreign_changes(target, files):
        state.issues.add("REGEN-008")  # the user's own uncommitted work stays out of the commit
    # A regeneration that changed nothing leaves the report as it was: the project is identical.
    repaired = state.world_repair is not None and bool(state.world_repair.repairs)
    write_report = repaired or not (unchanged and path.is_file())
    if write_report:
        jsonio.write(path, _report_data(state, ok))
        _write_markdown(state, target / report_mod.REPORT_MD, ok, plan)
    if state.git_message:
        committed = vcs.commit(target, state.git_message, files)
        if not committed.ok:
            state.issues.add("REGEN-007", reason=committed.reason)
            jsonio.write(path, _report_data(state, ok))  # the report tells that it failed
            _write_markdown(state, target / report_mod.REPORT_MD, ok, plan)


def _write_markdown(
    state: _State, path: Path, ok: bool, plan: promote.PromotionPlan | None = None
) -> None:
    text = report_mod.build_markdown(
        state.cfg,
        state.catalog,
        list(state.issues),
        ok,
        failed_phase=None if ok else state.current_phase,
        placeholders=state.placeholders,
        summary=report_mod.counts(state.catalog, list(state.issues), path.parent if ok else None),
        project=path.parent,
        plan=plan,
        runtime_version=state.runtime.new if state.runtime else "",
        skipped=state.skipped,
        world_repair=state.world_repair,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


PHASE_FUNCS: dict[str, Callable[[_State], None]] = {
    "preflight": phase_preflight,
    "stage": phase_stage,
    "install": phase_install,
    "catalog": phase_catalog,
    "import": phase_import,
    "build": phase_build,
    "validate": phase_validate,
    "smoke": phase_smoke,
    "export": phase_export,
    "promote": phase_promote,
    "report": phase_report,
}


# --------------------------------------------------------------------------- entry point


def _cancel(state: _State) -> RunResult:
    """A cancelled run: staging is deleted (no .rpggen_failed folder) and nothing is delivered."""
    if state.staging is not None and state.staging.staging.exists():
        shutil.rmtree(state.staging.staging, ignore_errors=True)
    return RunResult(
        False,
        Path(state.target),
        list(state.issues),
        None,
        None,
        failed_phase=state.current_phase,
        catalog=state.catalog,
        cfg=state.cfg,
        cancelled=True,
        timings=dict(state.timings),
        skipped=dict(state.skipped),
    )


def _fail(state: _State) -> RunResult:
    failed: Path | None = None
    report: Path | None = None
    if state.staging is not None and state.staging.staging.exists():
        failed = staging.discard(state.staging)
        report = failed / REPORT_NAME
        jsonio.write(report, _report_data(state, False))
        _write_markdown(state, failed / report_mod.REPORT_MD, False)
    return RunResult(
        False,
        Path(state.target),
        list(state.issues),
        report,
        failed,
        failed_phase=state.current_phase,
        catalog=state.catalog,
        cfg=state.cfg,
        timings=dict(state.timings),
        skipped=dict(state.skipped),
    )


def run(
    cfg_path: Path,
    target: Path,
    godot_exe: Path,
    cb: Callbacks | None = None,
    placeholders: list[str] | None = None,
    force_while_open: bool = False,
    git_message: str | None = None,
    accept_runtime_upgrade: bool = False,
    derive_tile_size: bool = False,
    repair_world: bool | None = None,
) -> RunResult:
    """Generate a project from ``cfg_path`` into ``target`` through staging.

    ``placeholders`` lists roles for which a debug placeholder asset is created when the packs
    have none. ``force_while_open`` regenerates even if a Godot editor seems to have the
    project open. ``derive_tile_size`` replaces the config's ``base_tile_size`` with the tile
    size of the packs (the command line's ``--pack``, which has no better source).
    """
    cb = cb or Callbacks()
    state = _State(Path(cfg_path), Path(target), Path(godot_exe), cb)
    state.placeholders = list(placeholders or [])
    state.force_while_open = force_while_open
    state.git_message = git_message
    state.accept_runtime_upgrade = accept_runtime_upgrade
    state.derive_tile_size = derive_tile_size
    state.repair_world = repair_world
    return _execute(state)


def run_in_memory(
    cfg: config_mod.GeneratorConfig,
    catalog: catalog_mod.Catalog | None,
    target: Path,
    godot_exe: Path,
    cb: Callbacks | None = None,
    placeholders: list[str] | None = None,
    force_while_open: bool = False,
    git_message: str | None = None,
    accept_runtime_upgrade: bool = False,
    repair_world: bool | None = None,
) -> RunResult:
    """``run`` for a config and catalog that only exist in memory (the wizard's).

    ``catalog`` carries the user's overrides, rules and objects: it is the ``previous`` of the
    assemble phase, so everything the user decided survives the re-analysis of the packs.
    """
    state = _State(None, Path(target), Path(godot_exe), cb or Callbacks())
    state.cfg = cfg
    state.catalog_in = catalog
    state.placeholders = list(placeholders or [])
    state.force_while_open = force_while_open
    state.git_message = git_message
    state.accept_runtime_upgrade = accept_runtime_upgrade
    state.repair_world = repair_world
    return _execute(state)


def _crash(state: _State, exc: Exception) -> RunResult:
    """An exception nobody planned for: the traceback goes to ``rpggen/logs/crash.log`` of the
    kept work folder, the run fails with BUILD-005 (naming the phase) and both reports are
    written, so that the wizard shows Results with "Export diagnostic bundle" and the command
    line prints the issue instead of a traceback."""
    log.error("unexpected error in phase %s", state.current_phase, exc_info=exc)
    if state.staging is not None and state.staging.staging.exists():
        crash = state.staging.staging / "rpggen" / "logs" / "crash.log"
        crash.parent.mkdir(parents=True, exist_ok=True)
        crash.write_text("".join(traceback.format_exception(exc)), encoding="utf-8", newline="\n")
    reason = f"{type(exc).__name__}: {exc}".strip()
    state.issues.add("BUILD-005", phase=state.current_phase or "unknown", reason=reason[:300])
    return _fail(state)


def _execute(state: _State) -> RunResult:
    """Run every phase; each log record made meanwhile carries the run's id."""
    with logging_setup.run_context(state.run_id):
        log.info("generation %s started for %s", state.run_id, state.target)
        result = _run_phases(state)
        log.info("generation %s finished: ok=%s", state.run_id, result.ok)
        _remember_times(state)
    result.run_id = state.run_id
    return result


def _remember_times(state: _State) -> None:
    """The times of the phases that finished go into this computer's history (T13.07), after a
    failed or cancelled run too: the next run's estimate comes from it."""
    done = {name: state.timings[name] for name in state.phases_done if name in state.timings}
    if not done:
        return
    assets = len(state.catalog.assets) if state.catalog is not None else 0
    app_settings.store().update(lambda s: app_settings.add_phase_times(s, done, assets))


def _run_phases(state: _State) -> RunResult:
    cb = state.cb
    n = len(PHASES_M1)
    try:
        for i, name in enumerate(PHASES_M1, start=1):
            if cb.is_cancelled():
                return _cancel(state)
            state.current_phase = name
            cb.on_phase(name, i, n)
            cb.on_log(f"phase {i}/{n}: {name}")
            started = time.monotonic()
            try:
                PHASE_FUNCS[name](state)
            finally:
                state.timings[name] = round(time.monotonic() - started, 2)
            state.phases_done.append(name)
            if name != "report" and state.issues.has_errors():
                return _fail(state)
    except _Cancelled:
        return _cancel(state)
    except _Stop:
        return _fail(state)
    except RpgGenError as exc:
        state.issues.append(exc.issue)
        return _fail(state)
    except Exception as exc:  # noqa: BLE001 - an unexpected error is a report, not a traceback
        return _crash(state, exc)
    except BaseException:  # Ctrl+C, SystemExit: the work folder goes, the signal goes on
        if state.staging is not None and state.staging.staging.exists():
            staging.discard(state.staging)
        raise
    report_path = Path(state.target) / "rpggen" / REPORT_NAME
    return RunResult(
        True,
        Path(state.target),
        list(state.issues),
        report_path,
        None,
        catalog=state.catalog,
        cfg=state.cfg,
        timings=dict(state.timings),
        skipped=dict(state.skipped),
        world_repair=state.world_repair,
    )


def default_config_for_pack(
    pack_dir: Path, name: str, tile_size: int = 16, archetype: str = "turn_based"
) -> config_mod.GeneratorConfig:
    """Config for a single pack folder or archive (used by ``rpggen generate --pack``)."""
    pack_dir = Path(pack_dir)
    stem = pack_dir.name if pack_dir.is_dir() else pack_dir.stem
    pack_id = ids.pack_id_from_name(stem, set())
    ref = config_mod.pack_ref_from_source(pack_dir, pack_id)
    return config_mod.default_for(name, [ref], archetype=archetype, base_tile_size=tile_size)
