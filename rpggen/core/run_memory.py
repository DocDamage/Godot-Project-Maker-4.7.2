"""How the last generation into a folder ended (T15.20).

A regeneration with nothing changed skips its checks, but not after a run that failed or was
cancelled: that one left the project as it was, and whoever runs again wants to see it checked.
A failed or cancelled run must not write into the project, so the note lives in rpggen's own
data folder, one small file per project folder.
"""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path

from rpggen import jsonio, paths

FOLDER = "last_runs"


def _path(target: Path) -> Path:
    key = hashlib.sha256(str(Path(target).resolve()).casefold().encode("utf-8")).hexdigest()
    return paths.data_dir() / FOLDER / f"{key[:16]}.json"


def remember(target: Path, ok: bool) -> None:
    """Note how a run into ``target`` ended. A success clears the note (no file is the usual
    state); a failure or a cancel leaves one. Never raises: it is a convenience."""
    path = _path(target)
    with contextlib.suppress(OSError):
        if ok:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            jsonio.write(path, {"ok": False, "target": str(Path(target))})


def last_run_failed(target: Path) -> bool:
    """True when the last run into ``target`` failed or was cancelled."""
    return _path(target).is_file()
