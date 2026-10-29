"""Record one held-out validation run (T10.09): a pack, generated for both archetypes.

    python tools/held_out_run.py --pack "C:\\Packs\\unseen_pack" --name unseen1 \\
        --godot "C:\\Godot\\Godot_v4.7.2-stable_win64_console.exe" [--out validation_runs]

For each archetype the pack is analyzed and generated headless (validation and smoke test
included) into ``<out>/<name>/<archetype>``. The result row is appended to
``<out>/results.md``: pack, archetype, analysis time, generation time, pass/fail and the errors
and warnings. A person adds the two columns the program cannot measure: the **time to first
paint** (wizard start to painting tiles in Godot) and the **number of manual audit edits**, and
files tickets for the bugs found. The release can ship when all 10 runs pass and the median time
to first paint is under 10 minutes.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

HEADER = (
    "| pack | archetype | analysis s | generation s | passed | errors | warnings | "
    "first paint (min) | audit edits | bugs |\n"
    "|------|-----------|-----------:|-------------:|:------:|-------:|---------:|"
    "------------------:|------------:|------|\n"
)


def run_target(out: Path, name: str, archetype: str) -> Path:
    """Every trial has a fresh target. Never erase a previous project or failed run."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("name must be a short folder name using letters, digits, - or _")
    if archetype not in ("turn_based", "arpg"):
        raise ValueError("unsupported held-out archetype")
    target = (out / name / archetype).resolve()
    if out.resolve() not in target.parents:
        raise ValueError("run target escapes the output folder")
    if target.exists() or target.with_suffix(".run.json").exists():
        raise FileExistsError(f"Previous trial exists; use a new --out folder: {target}")
    return target


def run_one(pack: Path, name: str, archetype: str, godot: Path, out: Path) -> dict[str, object]:
    from rpggen import jsonio
    from rpggen.core import catalog as catalog_mod
    from rpggen.core import orchestrator
    from rpggen.gui import workers
    from rpggen.gui.state import WizardState

    target = run_target(out, name, archetype)
    target.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "pack": name,
        "source": str(pack.resolve()),
        "archetype": archetype,
        "target": str(target),
        "state": "analyzing",
        "placeholders_requested": ["PLAYER", "GROUND"],
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "working_tree": subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO, text=True
        ).splitlines(),
    }
    evidence_path = target.with_suffix(".run.json")
    jsonio.write(evidence_path, evidence)
    started = time.perf_counter()
    state = WizardState(pack_sources=[pack], target=None)
    analysis = workers.analyze_packs(state, callbacks=orchestrator.Callbacks())
    workers.apply_analysis(state, analysis)
    analysis_s = time.perf_counter() - started
    evidence.update(
        state="generating",
        analysis_s=round(analysis_s, 3),
        inventories=[inv.to_json() for inv in analysis.inventories],
    )
    jsonio.write(evidence_path, evidence)
    if state.catalog is not None:
        catalog_mod.save(state.catalog, target.with_suffix(".catalog.json"))
    cfg = orchestrator.default_config_for_pack(pack, name, archetype=archetype)
    started = time.perf_counter()
    result = orchestrator.run_in_memory(
        cfg, state.catalog, target, godot, placeholders=["PLAYER", "GROUND"]
    )
    generation_s = time.perf_counter() - started
    all_issues = [*analysis.issues, *result.issues]
    errors = [i for i in all_issues if i.severity.value == "error"]
    warnings = [i for i in all_issues if i.severity.value == "warning"]
    row_data = {
        "pack": name,
        "archetype": archetype,
        "analysis_s": round(analysis_s, 1),
        "generation_s": round(generation_s, 1),
        "passed": result.ok and not errors,
        "errors": [f"{i.code} {i.message}" for i in errors],
        "warnings": len(warnings),
        "target": str(target),
    }
    evidence.update(
        state="finished",
        result=row_data,
        phase_timings=result.timings,
        failed_phase=result.failed_phase,
        failed_staging=str(result.failed_staging or ""),
        issues=[
            {"code": i.code, "severity": i.severity.value, "message": i.message} for i in all_issues
        ],
    )
    jsonio.write(evidence_path, evidence)
    return row_data


def row(r: dict[str, object]) -> str:
    errors = r["errors"]
    assert isinstance(errors, list)
    bugs = "; ".join(errors)[:200].replace("|", "/")
    return (
        f"| {r['pack']} | {r['archetype']} | {r['analysis_s']} | {r['generation_s']} | "
        f"{'yes' if r['passed'] else 'NO'} | {len(errors)} | {r['warnings']} |  |  | {bugs} |\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--name", required=True, help="short name used in the table")
    parser.add_argument("--godot", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("validation_runs"))
    args = parser.parse_args(argv)
    godot = args.godot or (
        Path(os.environ["RPGGEN_GODOT"]) if os.environ.get("RPGGEN_GODOT") else None
    )
    if godot is None:
        print("held_out_run: pass --godot or set RPGGEN_GODOT")
        return 2
    try:
        for archetype in ("turn_based", "arpg"):
            run_target(args.out, args.name, archetype)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    args.out.mkdir(parents=True, exist_ok=True)
    table = args.out / "results.md"
    if not table.exists():
        table.write_text(HEADER, encoding="utf-8")
    failed = 0
    for archetype in ("turn_based", "arpg"):
        r = run_one(args.pack, args.name, archetype, godot, args.out)
        with open(table, "a", encoding="utf-8") as fh:
            fh.write(row(r))
        print(row(r), end="")
        failed += 0 if r["passed"] else 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
