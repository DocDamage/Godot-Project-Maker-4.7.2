"""Two smoke runs at one time (T17.18). Godot keeps `user://` by the project's *name*, and every
kind's steps saved into `user://smoke_saves`: two runs of projects of one name at one time read
and replaced each other's saves (`save_overwrite_confirm`, `mutate_then_load`, `[RPG-SAVE]
verification of user://smoke_saves/slot_0.tmp failed`). Each run now saves into a folder named
after its run id, which the orchestrator passes on the command line."""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import config, godot, orchestrator, profiles

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
RESULTS = "rpggen/results/smoke_results.json"


def _smoke(godot_exe: Path, project: Path, run_id: str) -> tuple[godot.GodotRun, dict]:
    (project / RESULTS).unlink(missing_ok=True)
    run = godot.run_godot(
        godot.find_console_exe(godot_exe),
        project,
        orchestrator.smoke_args("turn_based", run_id),
        timeout_s=godot.SMOKE_TIMEOUT_S,
        log_name=f"smoke_{run_id}",
        log_dir=project.parent / "logs",
    )
    results = jsonio.read(project / RESULTS) if (project / RESULTS).is_file() else {}
    return run, results


def test_two_smoke_runs_of_one_project_name_at_one_time_both_pass(
    godot_exe: Path, tmp_path: Path
) -> None:
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    cfg = config.default_for(
        "Two At Once", [config.pack_ref_from_source(SAMPLE, "sample_pack")], archetype="turn_based"
    )
    first = tmp_path / "one" / "out"
    result = orchestrator.run_in_memory(cfg, None, first, godot_exe)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    second = tmp_path / "two" / "out"
    shutil.copytree(first, second)  # the same project, so the same name and the same `user://`

    ids = ("aaaa0001", "bbbb0002")
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(
            pool.map(lambda pair: _smoke(godot_exe, *pair), zip((first, second), ids, strict=True))
        )

    for (run, results), run_id in zip(runs, ids, strict=True):
        failed = [(i["name"], i["detail"]) for i in results.get("items", []) if not i["ok"]]
        assert results.get("ok") is True, (run_id, failed, results.get("issues"))
        assert run.returncode == 0 and not run.timed_out
        log = run.log_path.read_text(encoding="utf-8", errors="replace")
        assert "[RPG-SAVE]" not in log, "no save of one run was touched by the other"
        assert "SCRIPT ERROR" not in log
        names = [i["name"] for i in results["items"]]
        assert {"save_slot_1", "save_overwrite_confirm", "mutate_then_load"} <= set(names)
