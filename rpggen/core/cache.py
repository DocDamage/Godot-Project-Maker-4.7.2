from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from rpggen import jsonio, paths

log = logging.getLogger(__name__)


def _root() -> Path:
    return paths.cache_dir() / "analysis"


def _entry_path(sha256: str) -> Path:
    return _root() / sha256[:2] / f"{sha256}.json"


def get(sha256: str, version: int) -> dict[str, Any] | None:
    """Cached analysis for an image hash, or None on a miss.

    A version mismatch is a miss. A corrupt entry is a miss and the file is deleted.
    """
    path = _entry_path(sha256)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.debug("deleting corrupt analysis cache entry %s", path)
        path.unlink(missing_ok=True)
        return None
    if not isinstance(data, dict) or data.get("analyzer_version") != version:
        return None
    return data


def put(sha256: str, version: int, data: dict[str, Any]) -> None:
    """Store an analysis entry (the analyzer version and hash are added to it)."""
    entry = dict(data)
    entry["analyzer_version"] = version
    entry["sha256"] = sha256
    jsonio.write(_entry_path(sha256), entry)


def clear() -> None:
    """Remove every cached analysis (the CLI flag --no-cache)."""
    shutil.rmtree(_root(), ignore_errors=True)
