from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, ids, jsonio, paths
from rpggen.core import (
    archive,
    godot,
    godot_log,
    inventory,
    placeholders,
    preflight,
    requirements,
    staging,
)
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import report as report_mod
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
    "promote",
    "report",
]
REPORT_NAME = "generation_report.json"
SMOKE_STEPS_M1 = "res://generated/builder/smoke/smoke_steps_m1.gd"


@dataclass
class Callbacks:
    on_phase: Callable[[str, int, int], None] = lambda name, i, n: None  # phase i of n
    on_log: Callable[[str], None] = lambda line: None
    is_cancelled: Callable[[], bool] = lambda: False


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


class _Stop(Exception):
    """Internal: a phase decided the run cannot continue (issues already recorded)."""


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
    run = godot.run_godot(
        state.godot_exe,
        state.staging.staging,
        args,
        timeout_s=timeout_s,
        log_name=log_name,
        log_dir=state.log_dir,
    )
    if run.timed_out:
        state.issues.add("BUILD-003", phase=phase, seconds=timeout_s)
        raise _Stop
    return run


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
    if state.cfg is None:
        assert state.cfg_path is not None
        state.cfg = config_mod.load(state.cfg_path)
    sources = [Path(p.source) for p in state.cfg.packs]
    state.issues.extend(preflight.check_target(state.target, sources))


def phase_stage(state: _State) -> None:
    state.staging = staging.create_staging(Path(state.target))
    state.log_dir = state.staging.staging / "rpggen" / "logs"
    state.log_dir.mkdir(parents=True, exist_ok=True)


def phase_install(state: _State) -> None:
    assert state.staging is not None and state.cfg is not None
    staging.install_templates(state.staging, paths.templates_root())
    used: set[str] = set()
    for ref in state.cfg.packs:
        opened = archive.open_pack(Path(ref.source), used, pack_id=ref.pack_id)
        used.add(opened.pack_id)
        state.issues.extend(opened.issues)
        inv = inventory.build_inventory(opened)
        state.opened.append((opened, inv))
        staging.install_pack(state.staging, opened.root, ref.pack_id, inv)


def phase_catalog(state: _State) -> None:
    assert state.staging is not None and state.cfg is not None and state.log_dir is not None
    work_dir = state.staging.staging / "rpggen" / "work"
    catalog, issues, generated = catalog_mod.assemble(
        state.opened, state.catalog_in, [], work_dir=work_dir
    )
    # archive issues were reported while opening the packs; do not list them twice
    known = {(i.code, i.message) for i in state.issues}
    state.issues.extend(i for i in issues if (i.code, i.message) not in known)
    staging.install_generated(state.staging, generated)
    shutil.rmtree(work_dir, ignore_errors=True)
    if state.placeholders:
        _written, placeholder_issues = placeholders.add_placeholder_assets(
            catalog, state.placeholders, state.cfg.base_tile_size, state.staging.staging
        )
        state.issues.extend(placeholder_issues)
    state.catalog = catalog
    state.generated = generated
    # A required role without any asset stops generation before Godot runs.
    state.issues.extend(requirements.check(catalog, state.cfg))
    staging.write_project_files(state.staging, state.cfg, catalog)


def phase_import(state: _State) -> None:
    assert state.staging is not None and state.log_dir is not None
    run = godot.run_godot(
        godot.find_console_exe(state.godot_exe),
        state.staging.staging,
        ["--import"],
        timeout_s=godot.IMPORT_TIMEOUT_S,
        log_name="import",
        log_dir=state.log_dir,
    )
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


def _sabotage(state: _State) -> None:
    """Test hook, honored only when RPGGEN_DEV=1: breaks the player script before validation."""
    assert state.staging is not None
    if (
        os.environ.get("RPGGEN_DEV") == "1"
        and os.environ.get("RPGGEN_TEST_SABOTAGE") == "broken_player"
    ):
        target = state.staging.staging / "addons/rpg_runtime/actors/player_controller.gd"
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


def phase_smoke(state: _State) -> None:
    assert state.cfg is not None
    if not state.cfg.validation.get("smoke_test", True):
        return
    run = _run_phase_godot(
        state,
        ["--", "--rpg-smoke", f"--rpg-smoke-steps={SMOKE_STEPS_M1}"],
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


def phase_promote(state: _State) -> None:
    assert state.staging is not None
    staging.promote(state.staging)


def _report_data(state: _State, ok: bool) -> dict[str, Any]:
    return {
        "report_version": 1,
        "generator_version": __version__,
        "ok": ok,
        "phases_completed": list(state.phases_done),
        "issues": state.issues.to_json(),
    }


def phase_report(state: _State) -> None:
    ok = not state.issues.has_errors()
    path = Path(state.target) / "rpggen" / REPORT_NAME
    jsonio.write(path, _report_data(state, ok))
    _write_markdown(state, Path(state.target) / report_mod.REPORT_MD, ok)


def _write_markdown(state: _State, path: Path, ok: bool) -> None:
    text = report_mod.build_markdown(
        state.cfg,
        state.catalog,
        list(state.issues),
        ok,
        failed_phase=None if ok else state.current_phase,
        placeholders=state.placeholders,
        summary=report_mod.counts(state.catalog, list(state.issues), path.parent if ok else None),
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
    "promote": phase_promote,
    "report": phase_report,
}


# --------------------------------------------------------------------------- entry point


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
    )


def run(
    cfg_path: Path,
    target: Path,
    godot_exe: Path,
    cb: Callbacks | None = None,
    placeholders: list[str] | None = None,
) -> RunResult:
    """Generate a project from ``cfg_path`` into ``target`` through staging.

    ``placeholders`` lists roles for which a debug placeholder asset is created when the packs
    have none.
    """
    cb = cb or Callbacks()
    state = _State(Path(cfg_path), Path(target), Path(godot_exe), cb)
    state.placeholders = list(placeholders or [])
    return _execute(state)


def run_in_memory(
    cfg: config_mod.GeneratorConfig,
    catalog: catalog_mod.Catalog | None,
    target: Path,
    godot_exe: Path,
    cb: Callbacks | None = None,
    placeholders: list[str] | None = None,
) -> RunResult:
    """``run`` for a config and catalog that only exist in memory (the wizard's).

    ``catalog`` carries the user's overrides, rules and objects: it is the ``previous`` of the
    assemble phase, so everything the user decided survives the re-analysis of the packs.
    """
    state = _State(None, Path(target), Path(godot_exe), cb or Callbacks())
    state.cfg = cfg
    state.catalog_in = catalog
    state.placeholders = list(placeholders or [])
    return _execute(state)


def _execute(state: _State) -> RunResult:
    cb = state.cb
    n = len(PHASES_M1)
    try:
        for i, name in enumerate(PHASES_M1, start=1):
            if cb.is_cancelled():
                return _fail(state)
            state.current_phase = name
            cb.on_phase(name, i, n)
            cb.on_log(f"phase {i}/{n}: {name}")
            PHASE_FUNCS[name](state)
            state.phases_done.append(name)
            if name != "report" and state.issues.has_errors():
                return _fail(state)
    except _Stop:
        return _fail(state)
    except RpgGenError as exc:
        state.issues.append(exc.issue)
        return _fail(state)
    except BaseException:
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
    )


def default_config_for_pack(
    pack_dir: Path, name: str, tile_size: int = 16
) -> config_mod.GeneratorConfig:
    """Config for a single pack folder or archive (used by ``rpggen generate --pack``)."""
    pack_dir = Path(pack_dir)
    stem = pack_dir.name if pack_dir.is_dir() else pack_dir.stem
    pack_id = ids.pack_id_from_name(stem, set())
    ref = config_mod.pack_ref_from_source(pack_dir, pack_id)
    return config_mod.default_for(name, [ref], base_tile_size=tile_size)
