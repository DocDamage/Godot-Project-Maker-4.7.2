"""Optional git support for generated projects (T5.06, T12.12). rpggen never pushes.

A repository rpggen creates gets everything (``git add -A``). In a repository that already
exists, rpggen stages and commits exactly the files it wrote or deleted, so that the user's own
uncommitted work never ends up under the message "rpggen: regenerate project".
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

TIMEOUT_S = 120
FALLBACK_IDENTITY = ("-c", "user.name=rpggen", "-c", "user.email=rpggen@localhost")
# The extensions of purchased art that Git LFS handles when the project asks for it.
LFS_EXTENSIONS = ("png", "jpg", "jpeg", "webp", "wav", "ogg", "mp3")


def git_available() -> bool:
    return shutil.which("git") is not None


def lfs_available() -> bool:
    """True when ``git lfs`` can be run."""
    if not git_available():
        return False
    try:
        run = subprocess.run(
            ["git", "lfs", "version"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return run.returncode == 0


def _git(
    target: Path, *args: str, identity: bool = False, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    prefix = ["git", *(FALLBACK_IDENTITY if identity else ())]
    return subprocess.run(
        [*prefix, *args],
        cwd=target,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_S,
        check=False,
    )


def _has_identity(target: Path) -> bool:
    name = _git(target, "config", "user.name").stdout.strip()
    email = _git(target, "config", "user.email").stdout.strip()
    return bool(name and email)


def is_repository(target: Path) -> bool:
    return (Path(target) / ".git").exists()


@dataclass(frozen=True)
class CommitResult:
    """What ``commit`` did. ``ok`` is False when git is missing or a step failed (``reason``
    says why); ``committed`` is True when a commit was made."""

    ok: bool
    committed: bool = False
    reason: str = ""


def _pathspec(files: Iterable[str]) -> str:
    return "".join(f"{f}\0" for f in files)


def _tail(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return " | ".join(lines[-3:])[:300]


def foreign_changes(target: Path, files: Iterable[str]) -> bool:
    """True when the repository in ``target`` has uncommitted changes outside ``files`` (the
    user's own work). False without a repository or without git."""
    target = Path(target)
    if not git_available() or not is_repository(target):
        return False
    try:
        status = _git(target, "status", "--porcelain", "-z", "--untracked-files=all")
    except (OSError, subprocess.SubprocessError):
        return False
    ours = {f.replace("\\", "/") for f in files}
    entries = status.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if "R" in code or "C" in code:  # a rename is followed by the old name
            index += 1
        if path.replace("\\", "/") not in ours:
            return True
    return False


def commit(target: Path, message: str, files: Iterable[str] | None = None) -> CommitResult:
    """``git init`` (if needed) and commit in ``target``; nothing is ever pushed.

    A repository that did not exist is created and gets everything. In one that did, and with
    ``files`` (paths relative to ``target``), exactly those files are staged and committed with
    ``git commit -- <paths>``, so other staged or unstaged changes stay out. The fallback
    identity ``rpggen <rpggen@localhost>`` is used only when none is configured.
    """
    target = Path(target)
    if not git_available():
        return CommitResult(False, reason="git is not installed")
    try:
        created = not is_repository(target)
        if created:
            init = _git(target, "init")
            if init.returncode != 0:
                log.warning("git init failed in %s", target)
                return CommitResult(False, reason=_tail(init.stderr) or "git init failed")
        use_fallback = not _has_identity(target)
        if created or files is None:
            return _commit_everything(target, message, use_fallback)
        return _commit_only(target, message, [f.replace("\\", "/") for f in files], use_fallback)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("git failed in %s: %s", target, exc)
        return CommitResult(False, reason=str(exc))


def _commit_everything(target: Path, message: str, use_fallback: bool) -> CommitResult:
    added = _git(target, "add", "-A")
    if added.returncode != 0:
        log.warning("git add failed in %s", target)
        return CommitResult(False, reason=_tail(added.stderr) or "git add failed")
    if not _git(target, "status", "--porcelain").stdout.strip():
        return CommitResult(True)  # nothing to commit
    done = _git(target, "commit", "-m", message, identity=use_fallback)
    if done.returncode != 0:
        log.warning("git commit failed in %s: %s", target, done.stderr.strip())
        return CommitResult(False, reason=_tail(done.stderr + done.stdout) or "git commit failed")
    return CommitResult(True, committed=True)


def _commit_only(target: Path, message: str, files: list[str], use_fallback: bool) -> CommitResult:
    # Only files that exist now (to be added) or that git tracks (a deletion) can be named.
    named = [f for f in files if (target / f).exists() or _is_tracked(target, f)]
    if not named:
        return CommitResult(True)
    added = _git(
        target,
        "add",
        "-A",
        "--pathspec-from-file=-",
        "--pathspec-file-nul",
        stdin=_pathspec(named),
    )
    if added.returncode != 0:
        log.warning("git add failed in %s: %s", target, added.stderr.strip())
        return CommitResult(False, reason=_tail(added.stderr) or "git add failed")
    done = _git(
        target,
        "commit",
        "-m",
        message,
        "--pathspec-from-file=-",
        "--pathspec-file-nul",
        identity=use_fallback,
        stdin=_pathspec(named),
    )
    if done.returncode != 0:
        output = done.stderr + done.stdout
        if "nothing to commit" in output or "no changes added to commit" in output:
            return CommitResult(True)  # nothing of ours changed
        log.warning("git commit failed in %s: %s", target, done.stderr.strip())
        return CommitResult(False, reason=_tail(output) or "git commit failed")
    return CommitResult(True, committed=True)


def _is_tracked(target: Path, rel: str) -> bool:
    found = _git(target, "ls-files", "--error-unmatch", "--", rel)
    return found.returncode == 0


def init_and_commit(target: Path, message: str) -> bool:
    """``commit`` for a caller that wants everything committed: True when it went through."""
    return commit(target, message).ok


def is_clean(target: Path) -> bool:
    """True when ``git status --porcelain`` lists nothing."""
    return not _git(Path(target), "status", "--porcelain").stdout.strip()
