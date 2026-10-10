"""Promotion of a finished staging folder into the target project, with backup (T5.03) and
restore (T5.07).

The three invariants (docs/regeneration.md): painted tiles never change, user-owned files are
never touched, and a failed generation leaves the target byte-identical.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rpggen import paths
from rpggen.core import ledger as ledger_mod
from rpggen.core.ledger import FileState, Ledger
from rpggen.core.staging import BACKUPS_NAME, Staging
from rpggen.errors import Issue, IssueList, RpgGenError

log = logging.getLogger(__name__)

KEEP_BACKUPS = 3
NEW_SUFFIX = ".rpggen-new"
TMP_SUFFIX = ".rpggen-tmp"
RETRIES = 3
RETRY_SLEEP_S = 0.2


@dataclass
class PromotionPlan:
    write: list[str] = field(default_factory=list)  # staging -> target (new or changed, allowed)
    conflicts: list[str] = field(default_factory=list)  # user-modified: staging goes to .rpggen-new
    delete: list[str] = field(default_factory=list)  # generated files removed, untouched in target
    skipped_deleted: list[str] = field(default_factory=list)  # user deleted: not recreated

    def issues(self) -> list[Issue]:
        found = IssueList()
        for rel in self.conflicts:
            found.add("REGEN-001", file=rel)
        for rel in self.skipped_deleted:
            found.add("REGEN-002", file=rel)
        return list(found)


@dataclass
class PromotionSummary:
    """What a regeneration is about to do to the project, for a person to look at first."""

    write: list[str]  # files that will be created or updated
    conflicts: list[str]  # changed by the user: the new version is written beside, as .rpggen-new
    delete: list[str]  # generated files the run no longer produces
    skipped_deleted: list[str]  # the user deleted these: they are not brought back
    backup: str  # the folder of the backup, relative to the project
    # T15.20: the project's choice (kept in its ledger) to repeat every check on every
    # regeneration; whoever is asked may change it, and the answer is stored with the run
    run_every_check: bool = False

    @property
    def changes(self) -> bool:
        """True when the run writes, replaces or deletes anything."""
        return bool(self.write or self.conflicts or self.delete)


class PromotionDeclined(Exception):
    """The person (or a script) looked at the summary and said no: nothing was changed."""


def summarize(plan_: PromotionPlan, target: Path) -> PromotionSummary:
    """The summary of ``plan_``; the backup folder is named as ``execute`` would name it."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return PromotionSummary(
        list(plan_.write),
        list(plan_.conflicts),
        list(plan_.delete),
        list(plan_.skipped_deleted),
        f"{BACKUPS_NAME}/{stamp}",
    )


def _same(target: Path, staging: Path, rel: str) -> bool:
    t = paths.from_posix_rel(rel, target)
    s = paths.from_posix_rel(rel, staging)
    return t.is_file() and s.is_file() and ledger_mod.file_hash(t) == ledger_mod.file_hash(s)


def plan(target: Path, staging: Path, old: Ledger, new: Ledger) -> PromotionPlan:
    """Decide for every ledger path what promotion does with it."""
    target, staging = Path(target), Path(staging)
    result = PromotionPlan()
    for rel in sorted(set(new.files) | set(old.files)):
        in_staging = rel in new.files and paths.from_posix_rel(rel, staging).is_file()
        state = ledger_mod.classify(target, rel, old)
        entry = new.files.get(rel) or old.files[rel]
        if not in_staging:
            # Dropped by this run: remove it only when it is a generated file nobody touched.
            if rel in old.files and entry.owner == "generated" and state is FileState.UNTOUCHED:
                result.delete.append(rel)
            continue
        if _same(target, staging, rel):
            continue
        target_exists = paths.from_posix_rel(rel, target).is_file()
        if entry.owner == "user_seed" and target_exists:
            continue  # user seeds are only ever created
        if not target_exists and (rel in old.deleted_by_user or state is FileState.DELETED):
            result.skipped_deleted.append(rel)
            continue
        if state is FileState.UNKNOWN:
            continue  # the user's own file
        if rel in ledger_mod.MERGE_MANAGED:
            result.write.append(rel)
        elif state is FileState.MODIFIED:
            declined = old.files[rel].declined_sha256 if rel in old.files else None
            if declined is not None and declined == new.files[rel].sha256:
                continue  # "Keep mine" (T12.58): the user declined exactly this content
            result.conflicts.append(rel)
        else:  # UNTOUCHED or ABSENT
            result.write.append(rel)
    return result


def final_ledger(target: Path, old: Ledger, candidate: Ledger, plan_: PromotionPlan) -> Ledger:
    """The ledger to commit once ``plan_`` has been executed.

    A conflicting file, or a user-modified one that the run did not replace, keeps its old hash so
    it stays "modified"; files the user deleted leave the ledger and join ``deleted_by_user``.
    """
    files = dict(candidate.files)
    written = set(plan_.write)
    for rel in list(files):
        if rel in plan_.skipped_deleted:
            del files[rel]
        elif (
            rel in old.files
            and rel not in written
            and files[rel].owner == "generated"
            and ledger_mod.classify(target, rel, old) is FileState.MODIFIED
        ):
            files[rel] = old.files[rel]
    for rel in plan_.delete:
        files.pop(rel, None)
    deleted = [d for d in old.deleted_by_user if not paths.from_posix_rel(d, target).is_file()]
    deleted += [rel for rel in plan_.skipped_deleted if rel not in deleted]
    return Ledger(
        files,
        sorted(set(deleted)),
        demo_removed=old.demo_removed,
        run_every_check=old.run_every_check,
    )


# --------------------------------------------------------------------------- file operations


def _atomic_replace(src: Path, dst: Path) -> None:
    """``os.replace`` with retries: antivirus and the Godot editor lock files on Windows."""
    for attempt in range(RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_SLEEP_S)


def _write_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + TMP_SUFFIX)
    shutil.copyfile(src, tmp)
    try:
        _atomic_replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _backup_dir(target: Path) -> Path:
    root = Path(target) / BACKUPS_NAME
    root.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = root / stamp
    n = 1
    while dest.exists():
        n += 1
        dest = root / f"{stamp}-{n}"
    dest.mkdir()
    return dest


def _backup_files(target: Path, backup: Path, rels: list[str]) -> None:
    for rel in rels:
        src = paths.from_posix_rel(rel, target)
        if src.is_file():
            dst = paths.from_posix_rel(rel, backup)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def rotate_backups(target: Path, keep: int = KEEP_BACKUPS) -> None:
    root = Path(target) / BACKUPS_NAME
    if not root.is_dir():
        return
    found = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    for old in found[: max(0, len(found) - keep)]:
        shutil.rmtree(old, ignore_errors=True)


def list_backups(target: Path) -> list[Path]:
    """Backup folders, oldest first."""
    root = Path(target) / BACKUPS_NAME
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)


def _rollback(target: Path, backup: Path, replaced: list[str], created: list[str]) -> None:
    for rel in created:
        paths.from_posix_rel(rel, target).unlink(missing_ok=True)
    for rel in replaced:
        src = paths.from_posix_rel(rel, backup)
        if src.is_file():
            _write_file(src, paths.from_posix_rel(rel, target))


def sync_godot_cache(staging: Path, target: Path) -> None:
    """Copy staging's ``.godot/`` over the target's, except ``.godot/editor/`` (editor state).

    The import cache has to match the new imports; it is not ledger-managed.
    """
    src = Path(staging) / ".godot"
    if not src.is_dir():
        return
    shutil.copytree(
        src,
        Path(target) / ".godot",
        ignore=lambda folder, names: (
            {"editor"} if Path(folder) == src and "editor" in names else set()
        ),
        dirs_exist_ok=True,
    )


def sync_run_files(staging: Path, target: Path) -> None:
    """Copy the run's logs and result files into the target (they are not ledger-managed)."""
    for rel in ("rpggen/logs", "rpggen/results"):
        src = paths.from_posix_rel(rel, Path(staging))
        if src.is_dir():
            shutil.copytree(src, paths.from_posix_rel(rel, Path(target)), dirs_exist_ok=True)


def execute(
    plan_: PromotionPlan,
    target: Path,
    staging: Path,
    backup_root: Path | None = None,
    *,
    old: Ledger,
    new: Ledger,
) -> Path | None:
    """Back up, apply the plan, write the conflict files and commit with the new ledger.

    ``backup_root`` is the target (the backup goes to ``<target>/.rpggen_backups/<stamp>/``).
    Returns the backup folder, or None when there was nothing to back up. A failed write rolls
    everything back and raises REGEN-004.
    """
    target, staging = Path(target), Path(staging)
    target_root = Path(backup_root) if backup_root is not None else target
    touched = sorted(set(plan_.write) | set(plan_.delete))
    conflict_files = [rel + NEW_SUFFIX for rel in plan_.conflicts]
    ledger_path = paths.from_posix_rel(paths.LEDGER, target)
    backup: Path | None = None
    if any(paths.from_posix_rel(r, target).is_file() for r in touched + conflict_files):
        # Only a run that overwrites or deletes something makes a backup, so no-op runs do not
        # push useful backups out of the rotation.
        backup = _backup_dir(target_root)
        _backup_files(target, backup, touched + conflict_files + [paths.LEDGER])
    replaced: list[str] = []
    created: list[str] = []
    try:
        for rel in plan_.write + conflict_files:
            dest = paths.from_posix_rel(rel, target)
            (replaced if dest.is_file() else created).append(rel)
            source = rel[: -len(NEW_SUFFIX)] if rel.endswith(NEW_SUFFIX) else rel
            _write_file(paths.from_posix_rel(source, staging), dest)
        for rel in plan_.delete:
            paths.from_posix_rel(rel, target).unlink(missing_ok=True)
        sync_godot_cache(staging, target)
        sync_run_files(staging, target)
        new.save(ledger_path)  # the commit point
    except Exception as exc:
        log.exception("promotion failed; restoring the target from the backup")
        if backup is not None:
            _rollback(
                target,
                backup,
                [r for r in replaced + plan_.delete if paths.from_posix_rel(r, backup).is_file()],
                created,
            )
        else:
            _rollback(target, target, [], created)
        raise RpgGenError("REGEN-004", reason=f"{type(exc).__name__}: {exc}") from exc
    rotate_backups(target_root)
    return backup


def promote_new(stg: Staging, ledger_: Ledger) -> None:
    """A first generation: move every top-level entry of staging into the empty target."""
    for entry in sorted(stg.staging.iterdir(), key=lambda p: p.name):
        dest = stg.target / entry.name
        if dest.exists():
            raise RpgGenError("REGEN-004", reason=f"{dest.name} already exists in the target")
        shutil.move(str(entry), str(dest))
    stg.staging.rmdir()
    ledger_.save(stg.target / paths.LEDGER)


@dataclass
class PromotionResult:
    plan: PromotionPlan
    backup: Path | None
    issues: list[Issue]
    ledger: Ledger


def baseline_ledger(target: Path) -> Ledger:
    """For a project generated before ledgers existed: what is on disk now counts as untouched."""
    return ledger_mod.scan(Path(target))


def load_ledger(target: Path) -> Ledger:
    path = paths.from_posix_rel(paths.LEDGER, Path(target))
    return Ledger.load(path) if path.is_file() else baseline_ledger(target)


@dataclass
class PreparedPromotion:
    """A regeneration's plan, worked out but not carried out (nothing in the target changed)."""

    old: Ledger
    candidate: Ledger
    plan: PromotionPlan
    committed: Ledger


def prepare(stg: Staging) -> PreparedPromotion:
    """Work out what promoting ``stg`` into its existing target would do."""
    old = load_ledger(stg.target)
    candidate = ledger_mod.scan(stg.staging, stg.target, old)
    plan_ = plan(stg.target, stg.staging, old, candidate)
    return PreparedPromotion(old, candidate, plan_, final_ledger(stg.target, old, candidate, plan_))


def promote(
    stg: Staging,
    confirm: Callable[[PromotionSummary], bool] | None = None,
    *,
    inputs_sha256: str = "",
    godot_version: str = "",
    repeat: bool = False,
) -> PromotionResult:
    """Promote a validated staging folder (new or regeneration) and remove it.

    ``confirm`` (regenerations only) is asked with the summary when the run would write, replace
    or delete something; a False answer raises ``PromotionDeclined`` with the target untouched.
    ``inputs_sha256`` and ``godot_version`` say what the run was made from (T15.20) and go
    into the ledger. ``repeat`` is a run that found nothing changed and built nothing: the
    work folder goes and the project is not touched at all, not even its ledger.
    """
    if not stg.regenerate:
        candidate = ledger_mod.scan(stg.staging)
        candidate.inputs_sha256, candidate.godot_version = inputs_sha256, godot_version
        plan_ = PromotionPlan(write=sorted(candidate.files))
        promote_new(stg, candidate)
        return PromotionResult(plan_, None, [], candidate)
    if repeat:
        _remove_staging(stg)
        return PromotionResult(PromotionPlan(), None, [], load_ledger(stg.target))
    prepared = prepare(stg)
    old, candidate, plan_, committed = (
        prepared.old,
        prepared.candidate,
        prepared.plan,
        prepared.committed,
    )
    committed.inputs_sha256, committed.godot_version = inputs_sha256, godot_version
    if confirm is not None:
        summary = summarize(plan_, stg.target)
        summary.run_every_check = old.run_every_check
        if summary.changes and not confirm(summary):
            raise PromotionDeclined
        committed.run_every_check = summary.run_every_check  # as the person left it
    backup = execute(plan_, stg.target, stg.staging, stg.target, old=old, new=committed)
    _remove_staging(stg)
    return PromotionResult(plan_, backup, plan_.issues(), committed)


def _remove_staging(stg: Staging) -> None:
    for _ in range(RETRIES):
        shutil.rmtree(stg.staging, ignore_errors=True)
        if not stg.staging.exists():
            break
        time.sleep(RETRY_SLEEP_S)


# --------------------------------------------------------------------------- Godot editor


def _project_arguments(cmdline: list[str]) -> list[str]:
    """The project folders (and ``project.godot`` files) a Godot command line names:
    ``--path P``, ``--path=P``, a positional ``.../project.godot`` and the folder that follows
    ``-e`` / ``--editor``."""
    args = cmdline[1:]
    found: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        following = args[i + 1] if i + 1 < len(args) else None
        if arg == "--path" and following is not None:
            found.append(following)
            i += 2
            continue
        if arg.startswith("--path="):
            found.append(arg[len("--path=") :])
        elif arg in ("-e", "--editor") and following is not None and not following.startswith("-"):
            found.append(following)
            i += 2
            continue
        elif not arg.startswith("-") and arg.replace("\\", "/").lower().endswith("project.godot"):
            found.append(arg)
        i += 1
    return found


def _normalized(path: str, cwd: str | None) -> str | None:
    """A comparable form of a path: resolved, and case-folded where the file system is. A
    relative path needs the working directory of its process (None: it cannot be used)."""
    candidate = Path(path)
    if not candidate.is_absolute():
        if not cwd:
            return None
        candidate = Path(cwd) / candidate
    return os.path.normcase(str(candidate.resolve(strict=False)))


def editor_open(target: Path) -> bool:
    """Best effort: is a Godot editor running on this project?

    Godot keeps no lock file that was found to be reliable (VERIFY in the manual gate), so the
    command lines of the running Godot processes are parsed for the project they were given: the
    project is open when one of those paths is the folder itself or its ``project.godot`` (never
    a folder that merely starts with the same text). Failing to ask the system means "not open".
    """
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - psutil is a dependency
        log.debug("psutil is missing: cannot look for an open editor")
        return False
    folder = _normalized(str(Path(target).resolve()), None)
    if folder is None:
        return False
    wanted = {folder, os.path.normcase(os.path.join(folder, "project.godot"))}
    try:
        for proc in psutil.process_iter(["name", "cmdline", "cwd"]):
            try:
                info = proc.info
                name = (info.get("name") or "").lower()
                cmdline = info.get("cmdline") or []
                cwd = info.get("cwd")
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            if not name.startswith("godot") or not cmdline:
                continue
            for argument in _project_arguments(list(cmdline)):
                if _normalized(argument, cwd) in wanted:
                    return True
    except (psutil.Error, OSError) as exc:
        log.debug("could not list the running programs: %s", exc)
        return False
    return False


# --------------------------------------------------------------------------- restore


def restore(target: Path, backup_dir: Path | None = None) -> Path | None:
    """Put a backup's files back and make its ledger current again (T5.07).

    The default is the newest backup. First a fresh backup of what is about to be replaced is
    made, so a restore can itself be undone. Files the later generation created (in the current
    ledger, not in the restored one) are removed when the user did not touch them. Only the files
    that generation changed are in the backup, so restoring an older backup than the newest one
    leaves the newer changes in place.
    """
    target = Path(target)
    backups = list_backups(target)
    if backup_dir is None:
        if not backups:
            raise RpgGenError("REGEN-004", reason="there is no backup to restore")
        backup_dir = backups[-1]
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        raise RpgGenError("REGEN-004", reason=f"backup {backup_dir.name} does not exist")
    current = load_ledger(target)
    files = sorted(paths.to_posix_rel(p, backup_dir) for p in backup_dir.rglob("*") if p.is_file())
    restored_ledger_path = backup_dir / paths.LEDGER
    old = Ledger.load(restored_ledger_path) if restored_ledger_path.is_file() else Ledger()
    stale = [
        rel
        for rel in sorted(set(current.files) - set(old.files))
        if current.files[rel].owner == "generated"
        and ledger_mod.classify(target, rel, current) is FileState.UNTOUCHED
    ]
    safety = _backup_dir(target)
    _backup_files(target, safety, files + stale)
    created: list[str] = []
    try:
        for rel in [f for f in files if f != paths.LEDGER] + [paths.LEDGER]:
            dest = paths.from_posix_rel(rel, target)
            if not dest.is_file():
                created.append(rel)
            _write_file(paths.from_posix_rel(rel, backup_dir), dest)
        for rel in stale:
            paths.from_posix_rel(rel, target).unlink(missing_ok=True)
    except Exception as exc:
        _rollback(target, safety, files + stale, created)
        raise RpgGenError("REGEN-004", reason=f"{type(exc).__name__}: {exc}") from exc
    rotate_backups(target, KEEP_BACKUPS + 1)
    return safety
