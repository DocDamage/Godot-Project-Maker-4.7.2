from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _normalize(obj: Any) -> Any:
    if isinstance(obj, bool) or obj is None or isinstance(obj, int | str):
        return obj
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_normalize(v) for v in obj]
    if isinstance(obj, set | frozenset):
        raise TypeError("sets are not JSON serializable; sort them into a list first")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(obj: Any) -> str:
    """Deterministic JSON: sorted keys, 2-space indent, UTF-8 friendly, trailing newline.

    Floats are rounded to 6 decimal places; tuples become lists; sets raise TypeError.
    """
    return (
        json.dumps(
            _normalize(obj),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            separators=(",", ": "),
        )
        + "\n"
    )


def write(path: Path, obj: Any) -> None:
    """Atomically write ``obj`` to ``path`` (tmp file, fsync, os.replace)."""
    path = Path(path)
    text = dumps(obj)
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read(path: Path) -> Any:
    """Read UTF-8 JSON. Raises RpgGenError(CAT-001) on parse failure."""
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Switched to RpgGenError(CAT-001) in T1.03 once errors.py exists.
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
