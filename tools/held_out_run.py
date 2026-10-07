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
import shutil
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


def run_one(pack: Path, name: str, archetype: str, godot: Path, out: Path) -> dict[str, object]:
    from rpggen.core import orchestrator
    from rpggen.gui import workers
    from rpggen.gui.state import WizardState

    target = out / name / archetype
    if target.exists():
        shutil.rmtree(target)
    started = time.perf_counter()
    state = WizardState(pack_sources=[pack], target=None)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=orchestrator.Callbacks()))
    analysis_s = time.perf_counter() - started
    cfg = orchestrator.default_config_for_pack(pack, name, archetype=archetype)
    started = time.perf_counter()
    result = orchestrator.run_in_memory(
        cfg, state.catalog, target, godot, placeholders=["PLAYER", "GROUND"]
    )
    generation_s = time.perf_counter() - started
    errors = [i for i in result.issues if i.severity.value == "error"]
    warnings = [i for i in result.issues if i.severity.value == "warning"]
    return {
        "pack": name,
        "archetype": archetype,
        "analysis_s": round(analysis_s, 1),
        "generation_s": round(generation_s, 1),
        "passed": result.ok,
        "errors": [f"{i.code} {i.message}" for i in errors],
        "warnings": len(warnings),
        "target": str(target),
    }


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
