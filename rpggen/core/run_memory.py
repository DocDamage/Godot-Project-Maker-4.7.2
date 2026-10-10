"""How the last generation into a folder ended, and what your own files were then (T15.20).

A regeneration with nothing changed skips its checks, but not after a run that failed or was
cancelled: that one left the project as it was, and whoever runs again wants to see it checked.
Nor when a file of your own changed since the last run (a map under ``game/``, the project's
settings): the validator and the smoke test are what a run has to say about those. A failed or
cancelled run must not write into the project, and a repeat leaves it byte for byte as it is,
so the note lives in rpggen's own data folder, one small file per project folder.
"""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path

from rpggen import jsonio, paths

FOLDER = "last_runs"
OWN_FOLDER = "game"  # what a person makes and edits; rpggen writes a file there once
OWN_FILES = ("project.godot",)


def _path(target: Path) -> Path:
    key = hashlib.sha256(str(Path(target).resolve()).casefold().encode("utf-8")).hexdigest()
    return paths.data_dir() / FOLDER / f"{key[:16]}.json"


def own_files_hash(target: Path) -> str:
    """One hash over the files of the project that are a person's own: everything under
    ``game/`` and ``project.godot``, by path and content."""
    target = Path(target)
    digest = hashlib.sha256()
    own = target / OWN_FOLDER
    files = sorted(p for p in own.rglob("*") if p.is_file()) if own.is_dir() else []
    files += [target / name for name in OWN_FILES if (target / name).is_file()]
    for path in files:
        digest.update(path.relative_to(target).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _note(target: Path) -> dict[str, object]:
    path = _path(target)
    try:
        data = jsonio.read(path) if path.is_file() else {}
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def remember(target: Path, ok: bool) -> None:
    """Note how a run into ``target`` ended: a success with what your own files are now, a
    failure or a cancel as such. Never raises: it is a convenience."""
    path = _path(target)
    with contextlib.suppress(OSError):
        note: dict[str, object] = {"ok": ok, "target": str(Path(target))}
        if ok:
            note["own_files"] = own_files_hash(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        jsonio.write(path, note)


def last_run_failed(target: Path) -> bool:
    """True when the last run into ``target`` failed or was cancelled."""
    return _note(target).get("ok") is False


def own_files_changed(target: Path) -> bool:
    """True when a file under ``game/`` or ``project.godot`` is not what it was when the last
    run into ``target`` succeeded, or when nothing is known of such a run (another computer,
    a cleared data folder)."""
    known = _note(target).get("own_files")
    if not isinstance(known, str) or not known:
        return True
    try:
        return own_files_hash(target) != known
    except OSError:
        return True
