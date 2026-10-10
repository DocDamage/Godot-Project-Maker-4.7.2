"""T15.20: a regeneration with nothing changed repeats no check. The parts that need no Godot;
the whole run is in tests/integration/test_regeneration.py (test_8, test_9)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import catalog as catalog_mod
from rpggen.core import config, ledger, orchestrator, promote, run_memory
from rpggen.core.ledger import Ledger, LedgerEntry
from rpggen.core.staging import Staging
from rpggen.errors import CODES

SHA = "a" * 64


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _project(tmp: Path) -> tuple[Path, Ledger]:
    target = tmp / "project"
    files = {
        "generated/tilesets/overworld.tres": "tiles",
        "addons/rpg_runtime/plugin.cfg": "runtime",
        "game/maps/starter_map.tscn": "the user's map",
        "project.godot": "settings",
    }
    entries = {}
    for rel, text in files.items():
        path = _write(target, rel, text)
        owner = "user_seed" if rel.startswith("game/") else "generated"
        entries[rel] = LedgerEntry(ledger.file_hash(path), "x", owner)  # type: ignore[arg-type]
    old = Ledger(entries, inputs_sha256=SHA, godot_version="4.7.2.stable")
    old.save(target / paths.LEDGER)
    _write(target, paths.CONFIG, "{}")
    return target, old


def _state(tmp: Path, target: Path, old: Ledger) -> orchestrator._State:
    state = orchestrator._State(None, target, tmp / "godot.exe", orchestrator.Callbacks())
    state.staging = Staging(target, target / ".rpggen_staging", "regenerate")
    state.old_ledger = old
    state.inputs_sha = SHA
    state.godot_version = "4.7.2.stable"
    return state


@pytest.fixture(autouse=True)
def _own_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


# ------------------------------------------------------------------ the ledger


def test_the_ledger_records_what_a_run_was_made_from() -> None:
    plain = Ledger()
    assert "inputs_sha256" not in plain.to_json() and "run_every_check" not in plain.to_json()
    assert Ledger.from_json(plain.to_json()).inputs_sha256 == ""  # a ledger from before 1.3.0
    full = Ledger(inputs_sha256=SHA, godot_version="4.7.2.stable", run_every_check=True)
    data = full.to_json()
    assert data["inputs_sha256"] == SHA and data["run_every_check"] is True
    again = Ledger.from_json(data)
    assert (again.inputs_sha256, again.godot_version, again.run_every_check) == (
        SHA,
        "4.7.2.stable",
        True,
    )
    assert data["ledger_version"] == 1  # the same ledger version: an optional addition


def test_edited_generated_files_are_found_and_the_users_own_are_not(tmp_path: Path) -> None:
    target, old = _project(tmp_path)
    assert ledger.edited_generated_files(target, old) == []
    _write(target, "game/maps/starter_map.tscn", "painted")  # the user's to edit
    _write(target, "project.godot", "my settings")  # merged, never a conflict
    assert ledger.edited_generated_files(target, old) == []
    _write(target, "generated/tilesets/overworld.tres", "tiles; my note")
    assert ledger.edited_generated_files(target, old) == ["generated/tilesets/overworld.tres"]
    (target / "addons/rpg_runtime/plugin.cfg").unlink()  # deleted without the ledger knowing
    assert len(ledger.edited_generated_files(target, old, limit=5)) == 2
    old.deleted_by_user.append("addons/rpg_runtime/plugin.cfg")  # ... a deletion it respects
    assert ledger.edited_generated_files(target, old, limit=5) == [
        "generated/tilesets/overworld.tres"
    ]


# ------------------------------------------------------------------ is it a repeat?


def test_a_repeat_needs_the_same_inputs_the_same_godot_and_an_untouched_project(
    tmp_path: Path,
) -> None:
    target, old = _project(tmp_path)

    def reason(change=None) -> str:  # noqa: ANN001
        state = _state(tmp_path, target, copy.deepcopy(old))
        if change is not None:
            change(state)
        return orchestrator.repeat_reason(state)

    assert reason() == ""  # a repeat
    assert "first generation" in reason(lambda s: setattr(s.staging, "mode", "new"))
    assert "asked for" in reason(lambda s: setattr(s, "full_checks", True))
    assert "asks for every check" in reason(
        lambda s: setattr(s.old_ledger, "run_every_check", True)
    )
    assert "before 1.3.0" in reason(lambda s: setattr(s.old_ledger, "inputs_sha256", ""))
    assert "changed" in reason(lambda s: setattr(s, "inputs_sha", "b" * 64))
    assert "another Godot" in reason(lambda s: setattr(s, "godot_version", "4.7.3.stable"))
    assert "errors" in reason(lambda s: s.issues.add("ENV-001", path="x"))
    run_memory.remember(target, ok=False)
    assert "failed or was cancelled" in reason()
    run_memory.remember(target, ok=True)
    assert reason() == ""
    _write(target, "generated/tilesets/overworld.tres", "edited")
    assert "overworld.tres was changed or deleted" in reason()


def test_is_repeat_is_worked_out_once_and_logged(tmp_path: Path) -> None:
    target, old = _project(tmp_path)
    state = _state(tmp_path, target, old)
    said: list[str] = []
    state.cb = orchestrator.Callbacks(on_log=said.append)
    assert orchestrator.is_repeat(state) is True and orchestrator.is_repeat(state) is True
    assert said == ["nothing changed since the last run: the checks are not repeated"]
    other = _state(tmp_path, target, old)
    other.full_checks = True
    other.cb = orchestrator.Callbacks(on_log=said.append)
    assert orchestrator.is_repeat(other) is False
    assert said[-1] == "a full run: every check was asked for"


def test_the_note_code_and_what_is_skipped() -> None:
    assert orchestrator.REPEAT_SKIPS == ("import", "build", "validate", "smoke", "export")
    info = CODES[orchestrator.REPEAT_CODE]
    assert orchestrator.REPEAT_CODE == "REGEN-011" and info.severity == "info"
    assert "Nothing changed since the last run" in info.message and "--full" in info.fix
    assert all(phase in orchestrator.PHASES_M1 for phase in orchestrator.REPEAT_SKIPS)
    assert "promote" not in orchestrator.REPEAT_SKIPS  # it runs, and has nothing to write


# ------------------------------------------------------------------ the fingerprint


def _inputs() -> tuple[config.GeneratorConfig, catalog_mod.Catalog]:
    ref = config.PackRef("basic16", "packs/basic16", "0" * 64, "folder")
    return config.default_for("T", [ref]), catalog_mod.Catalog([], [], [], [], [])


def test_the_fingerprint_follows_every_input() -> None:
    cfg, cat = _inputs()
    base = orchestrator.inputs_fingerprint(cfg, cat, [])
    assert len(base) == 64 and base == orchestrator.inputs_fingerprint(cfg, cat, [])
    assert base == orchestrator.inputs_fingerprint(copy.deepcopy(cfg), copy.deepcopy(cat), [])
    seed = copy.deepcopy(cfg)
    seed.seed += 1
    assert orchestrator.inputs_fingerprint(seed, cat, []) != base  # an option
    feature = copy.deepcopy(cfg)
    feature.features["save"] = not feature.features.get("save", True)
    assert orchestrator.inputs_fingerprint(feature, cat, []) != base
    assert orchestrator.inputs_fingerprint(cfg, cat, ["NPC"]) != base  # a placeholder
    assert orchestrator.inputs_fingerprint(cfg, cat, ["NPC", "ENEMY"]) == (
        orchestrator.inputs_fingerprint(cfg, cat, ["ENEMY", "NPC"])
    )


def test_the_fingerprint_follows_the_templates_and_the_version(monkeypatch) -> None:
    cfg, cat = _inputs()
    base = orchestrator.inputs_fingerprint(cfg, cat, [])
    assert len(orchestrator.templates_fingerprint()) == 64
    monkeypatch.setattr(orchestrator, "__version__", "9.9.9")
    assert orchestrator.inputs_fingerprint(cfg, cat, []) != base
    monkeypatch.undo()
    monkeypatch.setattr(orchestrator, "templates_fingerprint", lambda: "c" * 64)
    assert orchestrator.inputs_fingerprint(cfg, cat, []) != base  # a recipe or the runtime


# ------------------------------------------------------------------ promotion


def _files(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".rpggen_staging" not in p.parts
    }


def test_a_repeat_promotes_nothing_and_leaves_the_project_as_it_is(tmp_path: Path) -> None:
    target, _old = _project(tmp_path)
    stg = Staging(target, target / ".rpggen_staging", "regenerate")
    _write(stg.staging, "generated/tilesets/overworld.tres", "something half made")
    before = _files(target)
    asked: list[object] = []
    result = promote.promote(stg, asked.append, inputs_sha256="d" * 64, repeat=True)  # type: ignore[arg-type]
    assert asked == [] and not stg.staging.exists()
    assert _files(target) == before  # not even the ledger
    assert result.backup is None and result.issues == []
    plan = result.plan
    assert not (plan.write or plan.conflicts or plan.delete or plan.skipped_deleted)


def test_a_regeneration_records_the_inputs_and_keeps_the_projects_choice(tmp_path: Path) -> None:
    target, old = _project(tmp_path)
    stg = Staging(target, target / ".rpggen_staging", "regenerate")
    for rel in old.files:
        _write(stg.staging, rel, (target / rel).read_text(encoding="utf-8"))
    _write(stg.staging, "generated/tilesets/overworld.tres", "new tiles")
    seen: list[promote.PromotionSummary] = []

    def confirm(summary: promote.PromotionSummary) -> bool:
        seen.append(summary)
        assert summary.run_every_check is False  # what the ledger said
        summary.run_every_check = True  # the person ticked the box
        return True

    result = promote.promote(stg, confirm, inputs_sha256="e" * 64, godot_version="4.7.2.stable")
    assert len(seen) == 1 and result.plan.write == ["generated/tilesets/overworld.tres"]
    saved = Ledger.load(target / paths.LEDGER)
    assert saved.inputs_sha256 == "e" * 64 and saved.godot_version == "4.7.2.stable"
    assert saved.run_every_check is True
    # the next run reads the choice back into the summary
    stg2 = Staging(target, target / ".rpggen_staging", "regenerate")
    for rel in saved.files:
        _write(stg2.staging, rel, (target / rel).read_text(encoding="utf-8"))
    _write(stg2.staging, "generated/tilesets/overworld.tres", "newer tiles")
    seen.clear()
    promote.promote(stg2, lambda s: seen.append(s) or True, inputs_sha256="f" * 64)  # type: ignore[func-returns-value]
    assert seen[0].run_every_check is True
    assert Ledger.load(target / paths.LEDGER).run_every_check is True


def test_a_first_generation_records_the_inputs(tmp_path: Path) -> None:
    target = tmp_path / "new"
    target.mkdir()
    stg = Staging(target, target / ".rpggen_staging", "new")
    _write(stg.staging, "generated/a.tres", "a")
    promote.promote(stg, inputs_sha256=SHA, godot_version="4.7.2.stable")
    saved = Ledger.load(target / paths.LEDGER)
    assert saved.inputs_sha256 == SHA and saved.godot_version == "4.7.2.stable"


# ------------------------------------------------------------------ the memory of the last run


def test_the_outcome_of_the_last_run_is_kept_outside_the_project(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    assert not run_memory.last_run_failed(target)
    run_memory.remember(target, ok=False)
    assert run_memory.last_run_failed(target)
    assert list(target.iterdir()) == []  # a failed run writes nothing into the project
    assert not run_memory.last_run_failed(tmp_path / "another")
    run_memory.remember(target, ok=True)
    assert not run_memory.last_run_failed(target)
    run_memory.remember(target, ok=True)  # nothing to clear: no error


def test_the_command_line_has_full(tmp_path: Path, monkeypatch) -> None:
    from rpggen import cli

    seen: dict[str, object] = {}

    def fake_run(cfg_path, target, exe, cb=None, **options):  # type: ignore[no-untyped-def]
        seen.update(options)
        return orchestrator.RunResult(True, Path(target), [], None, None)

    monkeypatch.setattr(orchestrator, "run", fake_run)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    cfg = tmp_path / "generator_config.json"
    ref = config.PackRef("basic16", str(tmp_path), "0" * 64, "folder")
    config.save(config.default_for("T", [ref]), cfg)
    base = [
        "generate",
        "--config",
        str(cfg),
        "--target",
        str(tmp_path / "out"),
        "--godot",
        str(exe),
    ]
    assert cli.main(base) == 0 and seen["full_checks"] is False
    assert cli.main([*base, "--full"]) == 0 and seen["full_checks"] is True
