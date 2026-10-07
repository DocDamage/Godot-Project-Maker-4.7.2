"""Promotion of a finished staging folder into the target project, with backup (T5.03) and
restore (T5.07).

The three invariants (docs/regeneration.md): painted tiles never change, user-owned files are
never touched, and a failed generation leaves the target byte-identical.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
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
    return Ledger(files, sorted(set(deleted)), demo_removed=old.demo_removed)


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


def promote(stg: Staging) -> PromotionResult:
    """Promote a validated staging folder (new or regeneration) and remove it."""
    if not stg.regenerate:
        candidate = ledger_mod.scan(stg.staging)
        plan_ = PromotionPlan(write=sorted(candidate.files))
        promote_new(stg, candidate)
        return PromotionResult(plan_, None, [], candidate)
    old = load_ledger(stg.target)
    candidate = ledger_mod.scan(stg.staging, stg.target, old)
    plan_ = plan(stg.target, stg.staging, old, candidate)
    committed = final_ledger(stg.target, old, candidate, plan_)
    backup = execute(plan_, stg.target, stg.staging, stg.target, old=old, new=committed)
    for _ in range(RETRIES):
        shutil.rmtree(stg.staging, ignore_errors=True)
        if not stg.staging.exists():
            break
        time.sleep(RETRY_SLEEP_S)
    return PromotionResult(plan_, backup, plan_.issues(), committed)


# --------------------------------------------------------------------------- Godot editor


def editor_open(target: Path) -> bool:
    """Best effort: is a Godot editor running on this project?

    Godot keeps no lock file that was found to be reliable (VERIFY in the manual gate), so the
    command lines of running Godot processes are searched for the project folder. Failing to
    ask the system means "not open".
    """
    target = Path(target).resolve()
    needle = str(target).lower()
    try:
        if os.name == "nt":
            script = (
                "Get-CimInstance Win32_Process -Filter \"Name like 'Godot%'\" | "
                "ForEach-Object { $_.CommandLine }"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            ).stdout
        else:
            out = subprocess.run(
                ["ps", "-eo", "args"], capture_output=True, text=True, timeout=15, check=False
            ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    needle = needle.replace("/", "\\")
    return any(
        "godot" in line.lower() and needle in line.lower().replace("/", "\\")
        for line in out.splitlines()
    )


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
