from __future__ import annotations

import os
from pathlib import Path

import psutil
import pytest

from rpggen import paths
from rpggen.core import ledger, promote
from rpggen.core.ledger import Ledger, LedgerEntry
from rpggen.core.staging import BACKUPS_NAME, Staging
from rpggen.errors import RpgGenError


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _entry(root: Path, rel: str, owner: str) -> LedgerEntry:
    return LedgerEntry(ledger.file_hash(root / rel), "r", owner)  # type: ignore[arg-type]


def _files(root: Path, skip: tuple[str, ...] = ()) -> dict[str, bytes]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith(skip):
            out[rel] = p.read_bytes()
    return out


class Project:
    """A target with an earlier generation recorded in its ledger, and a staging copy."""

    def __init__(self, tmp: Path) -> None:
        self.target = tmp / "t"
        self.stg = tmp / "s"
        files = {
            "generated/untouched.tres": "v1",
            "generated/modified.tres": "v1",
            "generated/deleted.tres": "v1",
            "generated/removed.tres": "v1",
            "generated/edited_removed.tres": "v1",
            "game/maps/m.tscn": "seed",
            "project.godot": "base",
        }
        for rel, text in files.items():
            _write(self.target, rel, text)
            _write(self.stg, rel, text)
        self.old = Ledger(
            {
                rel: _entry(
                    self.target, rel, "user_seed" if rel.startswith("game/") else "generated"
                )
                for rel in files
            }
        )

    def user_edit(self, rel: str, text: str = "mine") -> None:
        _write(self.target, rel, text)

    def user_delete(self, rel: str) -> None:
        (self.target / rel).unlink()

    def staging_sets(self, rel: str, text: str) -> None:
        _write(self.stg, rel, text)

    def staging_drops(self, rel: str) -> None:
        (self.stg / rel).unlink()

    def plan(self) -> promote.PromotionPlan:
        new = ledger.scan(self.stg, self.target, self.old)
        return promote.plan(self.target, self.stg, self.old, new)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path)


def test_unchanged_files_need_nothing(project: Project) -> None:
    assert project.plan() == promote.PromotionPlan()


def test_untouched_and_absent_files_are_written(project: Project) -> None:
    project.staging_sets("generated/untouched.tres", "v2")
    project.staging_sets("generated/brand_new.tres", "new")
    assert project.plan().write == ["generated/brand_new.tres", "generated/untouched.tres"]


def test_a_user_modified_file_is_a_conflict(project: Project) -> None:
    project.user_edit("generated/modified.tres")
    project.staging_sets("generated/modified.tres", "v2")
    plan = project.plan()
    assert plan.conflicts == ["generated/modified.tres"]
    assert plan.write == []
    assert [i.code for i in plan.issues()] == ["REGEN-001"]


def test_a_modified_file_equal_to_the_new_version_is_left_alone(project: Project) -> None:
    project.user_edit("generated/modified.tres", "v2")
    project.staging_sets("generated/modified.tres", "v2")
    assert project.plan() == promote.PromotionPlan()


def test_a_user_deleted_file_is_not_recreated(project: Project) -> None:
    project.user_delete("generated/deleted.tres")
    project.staging_sets("generated/deleted.tres", "v2")
    plan = project.plan()
    assert plan.skipped_deleted == ["generated/deleted.tres"]
    assert [i.code for i in plan.issues()] == ["REGEN-002"]
    committed = promote.final_ledger(project.target, project.old, ledger.scan(project.stg), plan)
    assert "generated/deleted.tres" not in committed.files
    assert committed.deleted_by_user == ["generated/deleted.tres"]
    # and it stays skipped on the next run, when the ledger no longer lists it
    again = promote.plan(project.target, project.stg, committed, ledger.scan(project.stg))
    assert again.skipped_deleted == ["generated/deleted.tres"]


def test_a_recreated_file_leaves_deleted_by_user(project: Project) -> None:
    project.old.deleted_by_user.append("generated/back.tres")
    _write(project.target, "generated/back.tres", "the user made it again")
    candidate = ledger.scan(project.stg)
    committed = promote.final_ledger(
        project.target, project.old, candidate, promote.PromotionPlan()
    )
    assert committed.deleted_by_user == []


def test_user_seed_files_are_only_ever_created(project: Project) -> None:
    project.user_edit("game/maps/m.tscn", "painted")
    project.staging_sets("game/maps/m.tscn", "regenerated seed")
    project.staging_sets("game/maps/new.tscn", "new seed")
    plan = project.plan()
    assert plan.write == ["game/maps/new.tscn"]
    assert plan.conflicts == []
    project.user_delete("game/maps/m.tscn")
    assert project.plan().skipped_deleted == ["game/maps/m.tscn"], "a deleted seed stays deleted"


def test_dropped_generated_files_are_deleted_only_when_untouched(project: Project) -> None:
    project.staging_drops("generated/removed.tres")
    project.staging_drops("generated/edited_removed.tres")
    project.user_edit("generated/edited_removed.tres")
    plan = project.plan()
    assert plan.delete == ["generated/removed.tres"]
    assert plan.conflicts == []


def test_user_created_files_are_never_touched(project: Project) -> None:
    _write(project.target, "generated/mine.tres", "mine")
    _write(project.stg, "generated/mine.tres", "generator version")
    plan = project.plan()
    assert "generated/mine.tres" not in plan.write + plan.conflicts + plan.delete


def test_project_godot_is_merged_never_a_conflict(project: Project) -> None:
    project.user_edit("project.godot", "user settings")
    project.staging_sets("project.godot", "user settings + builder keys")
    plan = project.plan()
    assert plan.write == ["project.godot"] and plan.conflicts == []


def test_conflicts_keep_the_old_hash_in_the_committed_ledger(project: Project) -> None:
    project.user_edit("generated/modified.tres")
    project.staging_sets("generated/modified.tres", "v2")
    project.staging_sets("generated/untouched.tres", "v2")
    plan = project.plan()
    committed = promote.final_ledger(project.target, project.old, ledger.scan(project.stg), plan)
    old = project.old.files
    assert committed.files["generated/modified.tres"] == old["generated/modified.tres"]
    assert (
        committed.files["generated/untouched.tres"].sha256 != old["generated/untouched.tres"].sha256
    )


def test_a_kept_user_edit_stays_modified_in_the_ledger(project: Project) -> None:
    """The recipe skipped the file, so staging holds the user's edit: it must not be adopted."""
    project.user_edit("generated/modified.tres")
    project.staging_sets("generated/modified.tres", "mine")
    plan = project.plan()
    assert plan == promote.PromotionPlan()
    committed = promote.final_ledger(project.target, project.old, ledger.scan(project.stg), plan)
    assert (
        committed.files["generated/modified.tres"] == project.old.files["generated/modified.tres"]
    )


# --------------------------------------------------------------------------- execute


def _promote(project: Project) -> promote.PromotionResult:
    return promote.promote(Staging(project.target, project.stg, "regenerate"))


def _prepare_regeneration(project: Project) -> None:
    project.staging_sets("generated/untouched.tres", "v2")
    project.staging_sets("generated/brand_new.tres", "new")
    project.staging_drops("generated/removed.tres")
    project.user_edit("generated/modified.tres")
    project.staging_sets("generated/modified.tres", "v2")
    _write(project.stg, ".godot/imported/b.ctex", "new cache")
    _write(project.stg, ".godot/editor/state.cfg", "staging editor state")
    _write(project.target, ".godot/editor/state.cfg", "user editor state")
    _write(project.stg, "rpggen/results/build_results.json", "{}")
    project.old.save(project.target / paths.LEDGER)


def test_execute_backs_up_applies_and_commits_the_ledger_last(project: Project) -> None:
    _prepare_regeneration(project)
    result = _promote(project)
    t = project.target
    assert (t / "generated/untouched.tres").read_text() == "v2"
    assert (t / "generated/brand_new.tres").read_text() == "new"
    assert not (t / "generated/removed.tres").exists()
    assert (t / "generated/modified.tres").read_text() == "mine", "conflict: the user's file stays"
    assert (t / "generated/modified.tres.rpggen-new").read_text() == "v2"
    assert (t / "game/maps/m.tscn").read_text() == "seed"
    assert (t / ".godot/imported/b.ctex").read_text() == "new cache"
    assert (t / ".godot/editor/state.cfg").read_text() == "user editor state", "editor state kept"
    assert (t / "rpggen/results/build_results.json").is_file()
    assert not project.stg.exists(), "staging is removed"
    new_ledger = Ledger.load(t / paths.LEDGER)
    assert new_ledger.files == result.ledger.files
    assert "generated/brand_new.tres" in new_ledger.files
    assert "generated/removed.tres" not in new_ledger.files
    backup = result.backup
    assert backup is not None and backup.parent == t / BACKUPS_NAME
    assert (backup / "generated/untouched.tres").read_text() == "v1"
    assert (backup / "generated/removed.tres").read_text() == "v1"
    assert (backup / paths.LEDGER).is_file(), "the old ledger is in the backup"
    assert not (backup / "generated/brand_new.tres").exists(), "new files have nothing to back up"
    assert sorted(i.code for i in result.issues) == ["REGEN-001"]


def test_a_failure_in_the_middle_restores_the_target(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_regeneration(project)
    before = _files(project.target)
    real = promote._atomic_replace
    calls = {"n": 0}

    def flaky(src: Path, dst: Path) -> None:
        calls["n"] += 1
        if calls["n"] == 3:
            raise PermissionError("locked by the editor")
        real(src, dst)

    monkeypatch.setattr(promote, "_atomic_replace", flaky)
    with pytest.raises(RpgGenError) as exc:
        _promote(project)
    assert exc.value.code == "REGEN-004" and "locked" in exc.value.issue.message
    assert calls["n"] >= 3
    assert _files(project.target, skip=(BACKUPS_NAME,)) == before
    assert not list(project.target.rglob("*.rpggen-tmp")), "no temp file is left behind"
    assert project.stg.exists(), "staging is kept for the failure report"


def test_permission_errors_are_retried(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    project.staging_sets("generated/untouched.tres", "v2")
    project.old.save(project.target / paths.LEDGER)
    real = promote.os.replace
    calls = {"n": 0}

    def flaky(src: str | Path, dst: str | Path) -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("antivirus")
        real(src, dst)

    monkeypatch.setattr(promote.os, "replace", flaky)
    monkeypatch.setattr(promote, "RETRY_SLEEP_S", 0)
    _promote(project)
    assert (project.target / "generated/untouched.tres").read_text() == "v2"


def test_only_the_three_newest_backups_are_kept(tmp_path: Path) -> None:
    names = ("20260101-000001", "20260101-000002", "20260101-000003", "20260101-000004")
    for name in names:
        (tmp_path / BACKUPS_NAME / name).mkdir(parents=True)
    promote.rotate_backups(tmp_path)
    assert [p.name for p in promote.list_backups(tmp_path)] == list(names[1:])


def test_a_regeneration_without_changes_makes_no_backup(project: Project) -> None:
    project.old.save(project.target / paths.LEDGER)
    result = _promote(project)
    assert result.backup is None
    assert not (project.target / BACKUPS_NAME).exists()


def test_a_first_generation_moves_staging_into_the_empty_target(tmp_path: Path) -> None:
    target = tmp_path / "t"
    stg = target / ".rpggen_staging"
    _write(stg, "generated/a.tres", "a")
    _write(stg, "game/m.tscn", "m")
    _write(stg, "rpggen/logs/x.log", "log")
    result = promote.promote(Staging(target, stg, "new"))
    assert (target / "generated/a.tres").read_text() == "a"
    assert not stg.exists()
    assert sorted(Ledger.load(target / paths.LEDGER).files) == ["game/m.tscn", "generated/a.tres"]
    assert result.backup is None


def test_a_project_without_a_ledger_gets_a_baseline(project: Project) -> None:
    assert not (project.target / paths.LEDGER).exists()
    assert "generated/untouched.tres" in promote.load_ledger(project.target).files


# --------------------------------------------------------------------------- restore


def test_restore_returns_to_the_previous_generation(project: Project) -> None:
    _prepare_regeneration(project)
    skip = (".godot/", BACKUPS_NAME, "rpggen/results/")
    before = _files(project.target, skip)
    _promote(project)
    safety = promote.restore(project.target)
    assert safety is not None and safety.is_dir()
    after = _files(project.target, skip)
    after.pop("generated/modified.tres.rpggen-new")  # the conflict file of the undone run
    assert after == before
    assert "generated/brand_new.tres" not in after, "files the later generation created are removed"


def test_restore_keeps_files_the_user_changed_since(project: Project) -> None:
    _prepare_regeneration(project)
    _promote(project)
    (project.target / "generated/brand_new.tres").write_text("the user edited it", encoding="utf-8")
    promote.restore(project.target)
    assert (project.target / "generated/brand_new.tres").read_text() == "the user edited it"


def test_restore_without_a_backup_is_regen_004(tmp_path: Path) -> None:
    with pytest.raises(RpgGenError) as exc:
        promote.restore(tmp_path)
    assert exc.value.code == "REGEN-004"


def test_restore_makes_a_safety_backup_of_what_it_replaces(project: Project) -> None:
    _prepare_regeneration(project)
    _promote(project)
    safety = promote.restore(project.target)
    assert safety is not None
    assert (safety / "generated/untouched.tres").read_text() == "v2", "the regenerated version"


# --------------------------------------------------------------------------- editor check


class _Proc:
    """What ``psutil.process_iter`` yields: an object whose ``info`` holds the asked attributes."""

    def __init__(self, name: str, cmdline: list[str] | None, cwd: str | None = None) -> None:
        self.info = {"name": name, "cmdline": cmdline, "cwd": cwd}


class _Denied:
    @property
    def info(self) -> dict:
        raise psutil.AccessDenied(1)


def _running(monkeypatch: pytest.MonkeyPatch, *procs: object) -> None:
    monkeypatch.setattr(psutil, "process_iter", lambda _attrs=None: iter(procs))


def _folder(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    return folder


def test_a_folder_that_only_starts_like_the_open_one_is_not_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forest = _folder(tmp_path, "forest")
    forest_v2 = _folder(tmp_path, "forest_v2")
    _running(monkeypatch, _Proc("Godot.exe", ["Godot.exe", "--path", str(forest_v2), "--editor"]))
    assert promote.editor_open(forest) is False
    assert promote.editor_open(forest_v2) is True


@pytest.mark.parametrize(
    "build",
    [
        lambda p: ["godot", "--path", str(p), "--editor"],
        lambda p: ["godot", f"--path={p}"],
        lambda p: ["godot", "--path", str(p) + os.sep],  # a trailing separator
        lambda p: ["godot", "--path", str(p) + "/"],
        lambda p: ["godot", str(p / "project.godot")],  # a positional project file
        lambda p: ["godot", "-e", str(p)],  # a positional folder after -e
        lambda p: ["godot", "--editor", str(p)],
    ],
)
def test_the_ways_a_project_is_given_to_godot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, build
) -> None:
    project = _folder(tmp_path, "My Game")
    _running(monkeypatch, _Proc("Godot_v4.7.2-stable_win64.exe", build(project)))
    assert promote.editor_open(project) is True


def test_a_relative_path_uses_the_working_directory_of_its_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _folder(tmp_path, "My Game")
    _running(monkeypatch, _Proc("godot", ["godot", "--path", "My Game"], cwd=str(tmp_path)))
    assert promote.editor_open(project) is True
    _running(monkeypatch, _Proc("godot", ["godot", "--path", "My Game"], cwd=None))
    assert promote.editor_open(project) is False  # nothing to resolve it against


@pytest.mark.skipif(os.name != "nt", reason="case-insensitive paths")
def test_paths_are_compared_without_case_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _folder(tmp_path, "Forest")
    shouted = str(project).upper().replace("\\", "/")
    _running(monkeypatch, _Proc("Godot.exe", ["Godot.exe", "--path", shouted]))
    assert promote.editor_open(project) is True


def test_only_godot_processes_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _folder(tmp_path, "My Game")
    _running(
        monkeypatch,
        _Proc("notepad.exe", ["notepad.exe", "--path", str(project)]),
        _Proc("godot_helper", None),
        _Proc("Godot.exe", ["Godot.exe", "--path", str(tmp_path / "Other")]),
    )
    assert promote.editor_open(project) is False


def test_a_process_that_denies_access_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _folder(tmp_path, "My Game")
    _running(monkeypatch, _Denied(), _Proc("godot", ["godot", "--path", str(project)]))
    assert promote.editor_open(project) is True
    _running(monkeypatch, _Denied())
    assert promote.editor_open(project) is False


def test_editor_open_is_false_when_the_system_cannot_be_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_a: object, **_k: object) -> None:
        raise psutil.Error("cannot list")

    monkeypatch.setattr(psutil, "process_iter", broken)
    assert promote.editor_open(tmp_path) is False


def test_the_check_is_fast_and_starts_no_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess
    import time

    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("a program was started")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    started = time.monotonic()
    assert promote.editor_open(_folder(tmp_path, "x")) in (True, False)
    assert time.monotonic() - started < 1.0  # 200 ms on a normal machine; slack for CI
