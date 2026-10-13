from __future__ import annotations

import contextlib
import hashlib
import json
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
    iso_atlas,
    placeholders,
    preflight,
    promote,
    requirements,
    run_memory,
    runtime_version,
    sound_slots,
    staging,
    vcs,
    world_plan,
    world_repair,
)
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import ledger as ledger_mod
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
SMOKE_STEPS_METROIDVANIA = "res://generated/builder/smoke/smoke_steps_metroidvania.gd"
SMOKE_STEPS_FARM = "res://generated/builder/smoke/smoke_steps_farm.gd"
# The archetype's own steps run after the shared sequence (which ends in the starter map).
ARCHETYPE_SMOKE_STEPS = {
    "turn_based": SMOKE_STEPS_TURN_BASED,
    "arpg": SMOKE_STEPS_ARPG,
}
# An archetype whose world is not the top-down starter map has a whole sequence of its own (the
# shared one walks a village): the title screen and a new game are among its steps.
SMOKE_STEPS_SHMUP = "res://generated/builder/smoke/smoke_steps_shmup.gd"
SMOKE_STEPS_RUN_AND_GUN = "res://generated/builder/smoke/smoke_steps_run_and_gun.gd"
SMOKE_STEPS_RACING = "res://generated/builder/smoke/smoke_steps_racing.gd"
OWN_SMOKE_STEPS = {
    # a farm (T17.06) is a top-down game whose new game starts in the farmhouse: its file takes
    # the shared steps and runs them in the village, between its own
    "farm": SMOKE_STEPS_FARM,
    "racing": SMOKE_STEPS_RACING,
    "metroidvania": SMOKE_STEPS_METROIDVANIA,
    "shmup": SMOKE_STEPS_SHMUP,
    "run_and_gun": SMOKE_STEPS_RUN_AND_GUN,
}


def smoke_steps_for(archetype: str) -> str:
    """Comma-separated steps scripts for the smoke run of a project with this archetype."""
    if archetype in OWN_SMOKE_STEPS:
        return OWN_SMOKE_STEPS[archetype]
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
    # T15.20: a regeneration of the same inputs repeats nothing
    full_checks: bool = False  # --full: every phase runs whatever the ledger says
    godot_version: str = ""  # of the Godot that builds, read in preflight
    inputs_sha: str = ""  # the fingerprint of what this run is made from (after the catalog)
    repeat: bool | None = None  # None until it is worked out, before the import
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
    state.godot_version = ".".join(str(part) for part in version)
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
    else:
        # a config that was made in memory (the wizard's, a test's) was never read from a file:
        # what reading one refuses is refused here, before anything is built (T17.14: the
        # isometric view of a kind that has none, or whose maps are not made yet)
        config_mod.check_projection(
            {"projection": state.cfg.projection, "archetype": state.cfg.archetype}
        )
    sources = [Path(p.source) for p in state.cfg.packs]
    state.issues.extend(preflight.check_target(state.target, sources))
    if preflight.is_rpggen_project(state.target):
        # a generated project keeps its projection (T17.13): its maps are painted in one
        config_mod.check_projection_kept(state.cfg, Path(state.target))
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
        opened = archive.open_pack(Path(ref.source), used, pack_id=ref.pack_id, folder=ref.folder)
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
    # an isometric project needs isometric ground from a pack (T17.13): none is drawn
    iso_atlas.check_ground(catalog, state.cfg)
    if not state.cfg.sounds:
        # nothing was chosen (the command line, an older project): the packs' audio is used
        state.cfg.sounds = sound_slots.default_sounds(catalog, state.cfg.archetype)
    made_issues, stand_ins = add_run_made_assets(
        catalog, state.cfg, state.placeholders, state.staging.staging
    )
    state.issues.extend(made_issues)
    if stand_ins:
        state.cb.on_log(
            "side view: the packs have no "
            + ", ".join(k.replace("_", "-") for k in stand_ins)
            + " tile; generated ones are used"
        )
    # T15.20: what this run is made from, taken once the config has its defaults (the saved
    # config of the project has them too) and the catalog has what a run adds to it
    # (placeholders, stand-ins): a regeneration finds those of the last run in the project's
    # catalog, so only the finished catalog is the same from run to run. The dry run takes it
    # at the same point.
    state.inputs_sha = inputs_fingerprint(
        state.cfg, catalog, state.placeholders, state.repair_world
    )
    state.catalog = catalog
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


def add_run_made_assets(
    catalog: catalog_mod.Catalog,
    cfg: config_mod.GeneratorConfig,
    roles: list[str],
    root: Path,
) -> tuple[IssueList, list[str]]:
    """Add what a run makes itself to ``catalog`` and write the files under ``root``: a debug
    placeholder for every role of ``roles`` the packs lack, and for a metroidvania the side-view
    kit. Returns the issues (ASSET-011) and the kinds the kit stands in for."""
    issues = IssueList()
    if roles:
        _written, issues = placeholders.add_placeholder_assets(
            catalog, roles, cfg.base_tile_size, root, cfg.projection
        )
    stand_ins: list[str] = []
    if cfg.archetype in config_mod.SIDE_VIEW_KINDS:
        from rpggen.core import side_kit

        stand_ins = side_kit.add(catalog, cfg.base_tile_size, root)
    if cfg.archetype in requirements.ARCADE_KINDS:
        from rpggen.core import arcade_kit

        # what the kind needs and the packs lack is drawn; the note for each (ASSET-031) is
        # the requirement check's, which the dry run and the wizard have too
        arcade_kit.add(catalog, cfg.archetype, cfg.base_tile_size, root, cfg.projection)
    if cfg.archetype == "farm":
        from rpggen.core import farm_kit

        # the crops, the soil and the tools the packs lack are drawn (T17.02); the notes are
        # the requirement check's here too. An isometric farm's are drawn as large as one
        # step on its diamonds, the size its drawn people have (T17.14)
        farm_kit.add(catalog, farm_kit_tile(catalog, cfg), root, cfg.projection)
    if iso_atlas.wanted(cfg):
        from rpggen.core import iso_kit

        # the isometric packs have no people (T17.14): a hero, a villager and an enemy are
        # drawn for the roles no pack of the project fills; the notes are the requirement
        # check's here too. A race has no people (T17.15): its drawn enemy would be a rival's
        # picture, so nobody is drawn for it (the kit draws none for a view from above)
        race = cfg.archetype in requirements.ARCADE_KINDS
        people = config_mod.PROJECTION_TOP_DOWN if race else cfg.projection
        iso_kit.add(catalog, iso_atlas.project_footprint(catalog, cfg), root, people)
        # last, after everything that assigns the tile sets again: the single tiles of the
        # isometric packs are packed into atlases, and the project's tile set is theirs
        # (T17.13). A project that is seen from above gets none of it.
        iso_atlas.add(catalog, cfg, root)
    return issues, stand_ins


def farm_kit_tile(catalog: catalog_mod.Catalog, cfg: config_mod.GeneratorConfig) -> int:
    """What the drawn farm kit takes for a tile: the config's tile size, and for an isometric
    farm the length of one step on its diamonds (``iso_math.unit``: what the builder means by a
    tile there, and how wide ``iso_kit`` draws its people)."""
    if iso_atlas.wanted(cfg):
        from rpggen.core import iso_math

        footprint = iso_atlas.project_footprint(catalog, cfg)
        if footprint is not None:
            return iso_math.unit(int(footprint[0]), int(footprint[1]))
    return cfg.base_tile_size


# --------------------------------------------------------------------------- repeats (T15.20)

REPEAT_SKIPS = ("import", "build", "validate", "smoke", "export")  # what a repeat leaves out
REPEAT_CODE = "REGEN-011"
_templates_digest: dict[str, str] = {}


def templates_fingerprint() -> str:
    """A hash of the template project (the runtime, the builder with its ``RECIPE_VERSION``,
    the project files): what rpggen itself brings to a run. Worked out once per process."""
    root = paths.templates_root()
    key = str(root)
    if key not in _templates_digest:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if not path.is_file() or rel.startswith((".godot/", "tests/")):
                continue
            digest.update(rel.encode("utf-8") + b"\0" + ledger_mod.file_hash(path).encode("ascii"))
        _templates_digest[key] = digest.hexdigest()
    return _templates_digest[key]


def inputs_fingerprint(
    cfg: config_mod.GeneratorConfig,
    catalog: catalog_mod.Catalog,
    placeholders: list[str],
    repair_world: bool | None = None,
) -> str:
    """What a generation is made from, as one hash: the catalog (every pack file's hash, the
    audit's decisions, the rules and the objects), the config (the mapping, the options, the
    seed), the roles filled with placeholders, whether the world is mended after the build
    (``repair_world`` is the run's own switch; None leaves it to the config), the templates
    and the generator's version. Two runs with the same fingerprint and the same Godot build
    the same project."""
    payload = {
        "generator": __version__,
        "templates": templates_fingerprint(),
        "config": cfg.to_json(),
        "catalog": catalog.to_json(),
        "placeholders": sorted(placeholders),
        "repair_world": cfg.repair_world if repair_world is None else repair_world,
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repeat_reason(state: _State) -> str:
    """Why this run is **not** a repeat of the last one ("" when it is): every phase runs then.
    A repeat is a regeneration of the same inputs with the same Godot over a project in which
    nobody touched a file since the last run, a generated one or one of their own, and that
    run succeeded."""
    if state.staging is None or not state.staging.regenerate or state.old_ledger is None:
        return "a first generation"
    if state.full_checks:
        return "every check was asked for"
    old = state.old_ledger
    if old.run_every_check:
        return "the project asks for every check"
    if not old.inputs_sha256:
        return "the project was made by a version before 1.3.0"
    if old.inputs_sha256 != state.inputs_sha:
        return "the packs, the audit, the options or rpggen changed"
    if old.godot_version != state.godot_version:
        return "another Godot"
    if state.issues.has_errors():
        return "the run has errors"
    if run_memory.last_run_failed(Path(state.target)):
        return "the last run failed or was cancelled"
    edited = ledger_mod.edited_generated_files(Path(state.target), old)
    if edited:
        return f"{edited[0]} was changed or deleted"
    if run_memory.own_files_changed(Path(state.target)):
        return "a file of your own (game/, project.godot) changed since the last run"
    return ""


def is_repeat(state: _State) -> bool:
    if state.repeat is None:
        reason = repeat_reason(state)
        state.repeat = not reason
        state.cb.on_log(
            "nothing changed since the last run: the checks are not repeated"
            if state.repeat
            else f"a full run: {reason}"
        )
    return state.repeat


def _plan_world(state: _State, catalog: catalog_mod.Catalog) -> None:
    """``starter_map.areas`` (T13.20): the world plan goes into the staging copy, where the
    recipes read it. A project whose world exists keeps its stored plan; new rows are added."""
    assert state.staging is not None and state.cfg is not None
    if state.cfg.archetype == "metroidvania":
        _plan_rooms(state, catalog)
        return
    if state.cfg.archetype in ("shmup", "run_and_gun", "racing"):
        _plan_stages(state)
        return
    root = state.staging.staging
    # the crops of a farm are a section of the same file: what is stored of them is read before
    # the areas are planned, and put back after
    farm = state.cfg.archetype == "farm"
    stored_farm = ((world_plan.load(root) or {}).get("farm") if farm else None) or None
    _plan_areas(state, catalog)
    if farm:
        # in this order: the map is a part of the section the crops make, and the people's
        # tastes are for what the crops give
        _plan_crops(state, catalog, stored_farm)
        _plan_farm_map(state, catalog)
        _plan_people(state, catalog, stored_farm)
        _plan_animals(state, catalog, stored_farm)
        _plan_forage(state, catalog, stored_farm)  # after the map: its places lie on it


def _plan_areas(state: _State, catalog: catalog_mod.Catalog) -> None:
    """The areas of a top-down world, when the config has any (see ``_plan_world``)."""
    assert state.staging is not None and state.cfg is not None
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


def _plan_crops(state: _State, catalog: catalog_mod.Catalog, stored: dict[str, Any] | None) -> None:
    """A farm's crops (T17.05): planned once from the growth strips of the packs and the seed,
    stored as the section ``farm`` of the project's plan file, and never planned again; a crop
    the packs have gained is appended. ``stored`` is the section the project had."""
    from rpggen.core import crop_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    try:
        section, notes = crop_plan.for_project(
            stored, state.cfg.starter_map_options(), state.cfg.seed, crop_plan.facts_of(catalog)
        )
    except crop_plan.CropPlanError as exc:
        state.issues.add("CAT-002", file="config", reason=f"/starter_map: {exc}")
        raise _Stop from None
    # what the other planners of a farm keep in the section stays (a fresh crop plan has neither)
    for key in ("map", "people", "animals", "forage"):
        if stored and key in stored and key not in section:
            section[key] = stored[key]
    plan = world_plan.load(root) or crop_plan.world(section, state.cfg.seed)
    plan["farm"] = section
    world_plan.save(root, plan)
    state.cb.on_log("farm: " + crop_plan.summary(section))
    for note in notes:
        state.cb.on_log("farm: " + note)


FARM_ANIMAL_HOUSES = ("coop", "barn")


def _building_fact(catalog: catalog_mod.Catalog, obj: Any) -> dict[str, Any]:
    """``{"size", "door"}`` in cells of a building of the packs (``map_preview.building_info``)."""
    from rpggen.core import map_preview

    overworld = map_preview._overworld(catalog)
    tile = int(overworld.tile_size[0]) if overworld is not None else map_preview.Art.tile_px
    _x, _y, wide, high = obj.region
    size, door = map_preview.building_geometry((wide, high), obj.door, tile)
    return {"size": list(size), "door": list(door)}


def _iso_farm_facts(
    cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog
) -> dict[str, Any]:
    """``farm_facts`` of an isometric farm (T17.14): its buildings are the pictures an isometric
    pack drew as buildings, each on the cells its catalog entry says (``stands_on``), the door
    before the middle of its south side (``map_preview.iso_building_geometry``); and its water
    is a pond when a pack has an isometric water tile, else a well."""
    from rpggen.core import farm_plan, map_preview

    def tags(asset: Any) -> set[str]:
        return {str(t) for t in catalog_mod.effective(asset).get("tags") or []}

    def fact(asset: Any) -> dict[str, Any]:
        size, door = map_preview.iso_building_geometry(
            catalog_mod.effective(asset).get("stands_on")
        )
        return {"size": list(size), "door": list(door)}

    chosen = cfg.starter.get("building", "")
    buildings = map_preview.iso_buildings(catalog, chosen)
    own: dict[str, Any] = {}
    for kind in FARM_ANIMAL_HOUSES:
        found = next((b for b in buildings if kind in tags(b)), None)
        own[kind] = fact(found) if found is not None else None
    houses = [b for b in buildings if b.id == chosen or not tags(b) & set(FARM_ANIMAL_HOUSES)]
    water = any(
        catalog_mod.effective(a).get("role") == "WATER"
        and a.status not in ("UNUSED", "MISSING")
        and catalog_mod.fits_projection(a, cfg.projection)
        for a in catalog.assets
    )
    return farm_plan.facts_of(
        house=fact((houses or buildings)[0]) if buildings else None,
        water=water,
        coop=own["coop"],
        barn=own["barn"],
    )


def farm_facts(cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog) -> dict[str, Any]:
    """What the farm's planner needs to know of the packs (``farm_plan.facts_of``): the
    footprint of the farmhouse (the starter building, as the village has it; one tagged as a
    coop or a barn only when the packs have no other), of a coop and a barn of their own (a
    ``BUILDING`` object tagged so), and whether they have water tiles: a pond, else a well.
    The plan is the same grid of cells in both views; only these facts are the view's."""
    from rpggen.core import farm_plan, map_preview

    if cfg.projection == config_mod.PROJECTION_ISOMETRIC:
        return _iso_farm_facts(cfg, catalog)

    def tags(obj: Any) -> set[str]:
        return {str(t) for t in (getattr(obj, "tags", None) or [])}

    chosen = cfg.starter.get("building", "")
    buildings = map_preview.starter_buildings(catalog, chosen)
    own: dict[str, Any] = {}
    for kind in FARM_ANIMAL_HOUSES:
        found = next((b for b in buildings if kind in tags(b)), None)
        own[kind] = _building_fact(catalog, found) if found is not None else None
    houses = [b for b in buildings if b.id == chosen or not tags(b) & set(FARM_ANIMAL_HOUSES)]
    house = _building_fact(catalog, (houses or buildings)[0]) if buildings else None
    return farm_plan.facts_of(
        house=house,
        water=world_plan._has_role(catalog, ("WATER",)),
        coop=own["coop"],
        barn=own["barn"],
    )


def _plan_farm_map(state: _State, catalog: catalog_mod.Catalog) -> None:
    """A farm's own map (T17.06): planned once from the options, the seed and the buildings of
    the packs, stored as ``farm.map`` beside the crops, and never planned again once the map
    exists (the rule of T14.06). What keeps the stored farm from being worked is ``VAL-031``, a
    line each: a plan that somebody changed is reported, not replaced (a fresh one that fails
    is planned again by the planner itself, and its notes say so)."""
    from rpggen.core import farm_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    try:
        section, notes = farm_plan.for_project(
            root, state.cfg.starter_map_options(), state.cfg.seed, farm_facts(state.cfg, catalog)
        )
        plan = farm_plan.attach(world_plan.load(root) or {}, section)
    except farm_plan.FarmPlanError as exc:
        state.issues.add("CAT-002", file="config", reason=f"/starter_map: {exc}")
        raise _Stop from None
    for problem in farm_plan.check(section):
        state.issues.add("VAL-031", problem=problem)
    world_plan.save(root, plan)
    state.cb.on_log("farm: " + farm_plan.summary(section))
    for note in notes:
        state.cb.on_log("farm: " + note)


def people_facts(
    cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog, farm: dict[str, Any]
) -> dict[str, Any]:
    """What the people's planner needs to know (``people_plan.facts_of``): the ``NPC`` assets,
    how many houses the village's own plan has, whether somebody keeps a shop there (the demo's
    villager opens it, with the ``shops`` feature), and what can be given: what the crops give,
    and the potion of the demo. The village has no water, so nobody goes to a pond."""
    from rpggen.core import map_preview, people_plan

    building = map_preview.building_info_for(
        catalog, cfg.starter.get("building", ""), cfg.projection
    )
    village = map_preview.plan(cfg.starter_map_options(), cfg.seed, building, cfg.archetype)
    demo = bool(cfg.features.get("demo", True))
    items = [str(crop["produce"]) for crop in farm.get("crops", [])]
    return people_plan.facts_of(
        catalog,
        houses=len(village["buildings"]),
        shop=demo and bool(cfg.features.get("shops", True)),
        pond=False,
        items=[*items, *(["potion"] if demo else [])],
    )


def _plan_people(
    state: _State, catalog: catalog_mod.Catalog, stored: dict[str, Any] | None
) -> None:
    """The people of a farm's village (T17.09): planned once from the ``NPC`` assets and the
    seed, stored as ``farm.people``, and never planned again; an NPC the packs have gained is
    appended. ``stored`` is the section the project had."""
    from rpggen.core import people_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    plan = world_plan.load(root)
    assert plan is not None, "the crops are planned first"
    facts = people_facts(state.cfg, catalog, plan["farm"])
    try:
        people, notes = people_plan.for_project(
            (stored or {}).get("people"), state.cfg.starter_map_options(), state.cfg.seed, facts
        )
    except people_plan.PeoplePlanError as exc:
        state.issues.add("CAT-002", file="config", reason=f"/starter_map: {exc}")
        raise _Stop from None
    plan["farm"] = people_plan.store(plan["farm"], people, notes)
    world_plan.save(root, plan)
    state.cb.on_log("farm: " + people_plan.summary(people))
    for note in notes:
        state.cb.on_log("farm: " + note)


def _plan_forage(
    state: _State, catalog: catalog_mod.Catalog, stored: dict[str, Any] | None
) -> None:
    """A farm's fish and forage (T17.10): planned once from the ``ITEM`` pictures tagged
    ``fish`` and ``forage`` (the packs', else the drawn ones of the kit), the seed and the
    farm's own map, stored as ``farm.forage``, and never planned again; what the packs have
    gained is appended. ``stored`` is the section the project had. The farm's map is read, not
    changed: the places where things lie are cells of it that are free."""
    from rpggen.core import forage_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    plan = world_plan.load(root)
    assert plan is not None, "the crops are planned first"
    section, notes = forage_plan.for_project(
        (stored or {}).get("forage"),
        state.cfg.starter_map_options(),
        state.cfg.seed,
        forage_plan.facts_of(catalog),
        plan["farm"].get("map"),
    )
    plan["farm"] = forage_plan.store(plan["farm"], section)
    world_plan.save(root, plan)
    state.cb.on_log("farm: " + forage_plan.summary(section))
    for note in notes:
        state.cb.on_log("farm: " + note)


def _plan_animals(
    state: _State, catalog: catalog_mod.Catalog, stored: dict[str, Any] | None
) -> None:
    """The animals of a farm (T17.07): planned once from the ``ANIMAL`` sprites of the packs for
    the animal houses the farm's own plan has, stored as ``farm.animals``, and never planned
    again; a kind or a colour the packs have gained is appended. A farm without an animal house
    has no such key. ``stored`` is the section the project had."""
    from rpggen.core import animal_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    plan = world_plan.load(root)
    assert plan is not None, "the crops are planned first"
    houses = [h["kind"] for h in animal_plan.houses_of(plan["farm"].get("map"))]
    animals, notes = animal_plan.for_project(
        (stored or {}).get("animals"),
        state.cfg.starter_map_options(),
        state.cfg.seed,
        animal_plan.facts_of(catalog, houses),
    )
    if animals is None:
        return
    plan["farm"] = animal_plan.store(plan["farm"], animals)
    world_plan.save(root, plan)
    state.cb.on_log("farm: " + animal_plan.summary(animals))
    for note in notes:
        state.cb.on_log("farm: " + note)


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


def _plan_stages(state: _State) -> None:
    """A shoot 'em up's stages (T16.06): planned once from the options and the seed, stored in
    the project's plan file, and never planned again once the game has its list of stages. A
    stored plan that cannot be finished (somebody changed it) is reported, not replaced."""
    from rpggen.core import stage_plan, track_plan, wave_plan

    assert state.staging is not None and state.cfg is not None
    root = state.staging.staging
    # the shoot 'em up plans waves in the air, the run and gun chunks of ground (T16.10), the
    # racing game loops of road (T16.13)
    planner: Any = {"run_and_gun": stage_plan, "racing": track_plan}.get(
        state.cfg.archetype, wave_plan
    )
    facts = planner.facts_of(state.cfg.resolution, state.cfg.base_tile_size)
    try:
        plan, notes = planner.for_project(
            root, state.cfg.starter_map_options(), state.cfg.seed, facts
        )
    except (wave_plan.WavePlanError, stage_plan.StagePlanError, track_plan.TrackPlanError) as exc:
        state.issues.add("CAT-002", file="config", reason=f"/starter_map: {exc}")
        raise _Stop from None
    for problem in planner.check(plan["stages"]):
        stage, _, what = problem.partition(": ")
        state.issues.add("VAL-029", stage=stage, problem=what)
    if planner is stage_plan:
        # a soldier that does not jump needs something to swing from and to climb (T16.11)
        jump = stage_plan.normalized(state.cfg.starter_map_options())["jump"]
        for problem in stage_plan.check_grapple(plan["stages"], jump):
            stage, _, what = problem.partition(": ")
            state.issues.add("VAL-030", stage=stage, problem=what)
    world_plan.save(root, plan)
    state.cb.on_log("stages: " + planner.summary(plan["stages"]))
    for note in [*plan["notes"], *notes]:
        state.cb.on_log("stages: " + note)


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


def _world_picture(state: _State, root: Path) -> None:
    """The picture of a metroidvania (T14.10): its world of rooms seen from the side, drawn from
    the stored plan (the rooms are painted from that plan, cell by cell). It has the name of the
    starter map's picture, so the Results page and the welcome view show it the same way."""
    try:
        plan = world_plan.load(root)
        rooms = (plan or {}).get("rooms")
        stages = (plan or {}).get("stages") or {}
        tracks = stages if stages.get("kind") == "racing" else None
        if not rooms and not tracks:
            return
        from rpggen.core import map_preview

        (root / STARTER_PICTURE).parent.mkdir(parents=True, exist_ok=True)
        if rooms:
            picture = map_preview.render_world(rooms, scale=4)
        else:  # a racing game: its tracks from above, side by side (T16.13)
            assert tracks is not None
            picture = map_preview.render_tracks(tracks, scale=4)
        picture.save(root / STARTER_PICTURE, format="PNG")
        state.cb.on_log(f"world picture written to {STARTER_PICTURE}")
    except Exception as exc:  # noqa: BLE001 - the picture is a nicety
        state.cb.on_log(f"world picture skipped: {exc}")


def _with_farm_picture(village: Any, root: Path) -> Any:
    """The picture of a farm's world (T17.06): the farm as its stored plan has it on the left,
    the village as it was built on the right, at the same height. The village alone while the
    project has no plan of its farm."""
    from PIL import Image

    from rpggen.core import farm_plan, map_preview

    stored = farm_plan.stored_in(world_plan.load(root))
    if not stored:
        return village
    rows = max(1, int(stored["size"][1]))
    farm = map_preview.render_farm(stored, scale=max(2, village.height // rows)).convert("RGBA")
    gap = 8
    out = Image.new(
        "RGBA", (farm.width + gap + village.width, max(farm.height, village.height)), (0, 0, 0, 0)
    )
    out.paste(farm, (0, 0))
    out.paste(village.convert("RGBA"), (farm.width + gap, 0))
    return out


def _starter_picture(state: _State) -> None:
    """A picture of the starter map as it was really built (T11.27), for the Results page.

    Headless Godot cannot take a screenshot, so a Godot script dumps the cells and the entities
    and the picture is drawn here. Any problem is a line in the log, never a failed generation."""
    assert state.staging is not None and state.log_dir is not None
    root = state.staging.staging
    if not (root / "game" / "maps" / "starter_map.tscn").is_file():
        _world_picture(state, root)
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
        if state.cfg is not None and state.cfg.archetype == "farm":
            image = _with_farm_picture(image, root)
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
        state.promotion = promote.promote(
            state.staging,
            state.cb.confirm_promotion,
            inputs_sha256=state.inputs_sha,
            godot_version=state.godot_version,
            repeat=bool(state.repeat),
        )
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


# the phases whose failure Godot explains in a log, and the codes those failures carry
_CAUSE_CODES = ("BUILD-", "VAL-", "SMOKE-", "EXPORT-")


def _attach_cause(state: _State) -> None:
    """T15.21: say why the failed phase failed. The first error of its Godot log goes into the
    ``detail`` of that phase's error issues as ``cause`` (what Godot said), ``log`` (the log
    file's name) and ``file`` (the ``res://`` path it names), so that the Results page and the
    report can show the cause and offer the log and the asset."""
    phase = state.current_phase
    log_dir = getattr(state, "log_dir", None)
    if not phase or log_dir is None:
        return
    logs = sorted(Path(log_dir).glob(f"godot_{phase}*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return
    log_path = logs[-1]
    try:
        cause = godot_log.first_error(log_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return
    for issue in state.issues:
        if issue.severity is not Severity.ERROR or not issue.code.startswith(_CAUSE_CODES):
            continue
        issue.detail.setdefault("log", log_path.name)
        if cause is not None:
            issue.detail.setdefault("cause", cause.sentence())
            if cause.path:
                issue.detail.setdefault("file", cause.path)


def _fail(state: _State) -> RunResult:
    failed: Path | None = None
    report: Path | None = None
    with contextlib.suppress(Exception):  # the cause is a help, never a second failure
        _attach_cause(state)
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
    full_checks: bool = False,
) -> RunResult:
    """Generate a project from ``cfg_path`` into ``target`` through staging.

    ``placeholders`` lists roles for which a debug placeholder asset is created when the packs
    have none. ``force_while_open`` regenerates even if a Godot editor seems to have the
    project open. ``derive_tile_size`` replaces the config's ``base_tile_size`` with the tile
    size of the packs (the command line's ``--pack``, which has no better source).
    ``full_checks`` runs every phase of a regeneration even when nothing changed (T15.20).
    """
    cb = cb or Callbacks()
    state = _State(Path(cfg_path), Path(target), Path(godot_exe), cb)
    state.placeholders = list(placeholders or [])
    state.force_while_open = force_while_open
    state.git_message = git_message
    state.accept_runtime_upgrade = accept_runtime_upgrade
    state.derive_tile_size = derive_tile_size
    state.repair_world = repair_world
    state.full_checks = full_checks
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
    full_checks: bool = False,
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
    state.full_checks = full_checks
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
        run_memory.remember(Path(state.target), result.ok)  # a failure is followed by a full run
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
            if name in REPEAT_SKIPS and is_repeat(state):
                _skip(state, name, REPEAT_CODE)  # T15.20: nothing changed, nothing to redo
                continue
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
