"""Optional git support for generated projects (T5.06). rpggen never pushes."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

TIMEOUT_S = 120
FALLBACK_IDENTITY = ("-c", "user.name=rpggen", "-c", "user.email=rpggen@localhost")


def git_available() -> bool:
    return shutil.which("git") is not None


def _git(target: Path, *args: str, identity: bool = False) -> subprocess.CompletedProcess[str]:
    prefix = ["git", *(FALLBACK_IDENTITY if identity else ())]
    return subprocess.run(
        [*prefix, *args],
        cwd=target,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )


def _has_identity(target: Path) -> bool:
    name = _git(target, "config", "user.name").stdout.strip()
    email = _git(target, "config", "user.email").stdout.strip()
    return bool(name and email)


def is_repository(target: Path) -> bool:
    return (Path(target) / ".git").exists()


def init_and_commit(target: Path, message: str) -> bool:
    """``git init`` (if needed), ``git add -A`` and ``git commit`` in ``target``.

    The fallback identity ``rpggen <rpggen@localhost>`` is used only when no identity is
    configured. Returns False when git is missing or a step fails (the reason is logged);
    nothing is ever pushed.
    """
    target = Path(target)
    if not git_available():
        return False
    try:
        if not is_repository(target) and _git(target, "init").returncode != 0:
            log.warning("git init failed in %s", target)
            return False
        use_fallback = not _has_identity(target)
        if _git(target, "add", "-A").returncode != 0:
            log.warning("git add failed in %s", target)
            return False
        if not _git(target, "status", "--porcelain").stdout.strip():
            return True  # nothing to commit
        commit = _git(target, "commit", "-m", message, identity=use_fallback)
        if commit.returncode != 0:
            log.warning("git commit failed in %s: %s", target, commit.stderr.strip())
            return False
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("git failed in %s: %s", target, exc)
        return False
    return True


def is_clean(target: Path) -> bool:
    """True when ``git status --porcelain`` lists nothing."""
    return not _git(Path(target), "status", "--porcelain").stdout.strip()
