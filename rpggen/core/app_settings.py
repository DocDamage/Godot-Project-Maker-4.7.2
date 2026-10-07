"""Application settings that survive a restart (T11.09).

Plain JSON at ``paths.local_cache_dir()/settings.json``. It is not ``QSettings`` so that core code
works without Qt and the file can go into a diagnostic bundle. Loading never raises: a missing or
corrupt file gives the defaults, unknown keys are ignored (forward compatible) and values of the
wrong type fall back to their defaults one by one.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from rpggen import paths

FILE_NAME = "settings.json"
RECENT_MAX = 10
THUMB_SIZES = (64, 96, 128, 192)
THEMES = ("dark", "light")


@dataclass
class RecentProject:
    target: str
    name: str = ""
    archetype: str = ""
    last_opened: str = ""  # ISO 8601, seconds


@dataclass
class AppSettings:
    godot_exe: str = ""
    last_pack_dir: str = ""
    last_target_dir: str = ""
    recent_projects: list[RecentProject] = field(default_factory=list)  # newest first, max 10
    window: dict[str, int] = field(default_factory=dict)  # x, y, w, h, maximized
    splitters: dict[str, list[int]] = field(default_factory=dict)  # e.g. "audit"
    theme: str = "dark"
    thumb_size: int = 96
    option_presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    quick_roles: list[str] = field(default_factory=list)  # the 1-9 keys of the audit page
    phase_timings: dict[str, float] = field(default_factory=dict)  # seconds of the last run

    def to_json(self) -> dict[str, Any]:
        return {
            "godot_exe": self.godot_exe,
            "last_pack_dir": self.last_pack_dir,
            "last_target_dir": self.last_target_dir,
            "recent_projects": [vars(r).copy() for r in self.recent_projects],
            "window": dict(self.window),
            "splitters": {k: list(v) for k, v in self.splitters.items()},
            "theme": self.theme,
            "thumb_size": self.thumb_size,
            "option_presets": self.option_presets,
            "quick_roles": list(self.quick_roles),
            "phase_timings": dict(self.phase_timings),
        }


def settings_path() -> Path:
    return paths.local_cache_dir() / FILE_NAME


def _str(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _recent(raw: Any) -> list[RecentProject]:
    out: list[RecentProject] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("target"), str):
            continue
        # entries whose folder is gone are dropped on load
        if not Path(item["target"]).is_dir():
            continue
        out.append(
            RecentProject(
                item["target"],
                _str(item.get("name"), ""),
                _str(item.get("archetype"), ""),
                _str(item.get("last_opened"), ""),
            )
        )
    return out[:RECENT_MAX]


def from_json(data: Any) -> AppSettings:
    """Build settings from decoded JSON; anything malformed keeps its default."""
    s = AppSettings()
    if not isinstance(data, dict):
        return s
    s.godot_exe = _str(data.get("godot_exe"), s.godot_exe)
    s.last_pack_dir = _str(data.get("last_pack_dir"), s.last_pack_dir)
    s.last_target_dir = _str(data.get("last_target_dir"), s.last_target_dir)
    s.recent_projects = _recent(data.get("recent_projects"))
    window = data.get("window")
    if isinstance(window, dict):
        s.window = {
            k: int(v) for k, v in window.items() if isinstance(v, int) and not isinstance(v, bool)
        }
    splitters = data.get("splitters")
    if isinstance(splitters, dict):
        s.splitters = {
            k: [int(x) for x in v]
            for k, v in splitters.items()
            if isinstance(k, str) and isinstance(v, list) and all(isinstance(x, int) for x in v)
        }
    theme = data.get("theme")
    s.theme = theme if theme in THEMES else s.theme
    size = data.get("thumb_size")
    s.thumb_size = size if size in THUMB_SIZES else s.thumb_size
    presets = data.get("option_presets")
    if isinstance(presets, dict):
        s.option_presets = {k: v for k, v in presets.items() if isinstance(v, dict)}
    roles = data.get("quick_roles")
    if isinstance(roles, list):
        s.quick_roles = [r for r in roles if isinstance(r, str)][:9]
    timings = data.get("phase_timings")
    if isinstance(timings, dict):
        s.phase_timings = {
            k: float(v)
            for k, v in timings.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
    return s


def load() -> AppSettings:
    """The saved settings, or the defaults; never raises."""
    try:
        text = settings_path().read_text(encoding="utf-8")
        return from_json(json.loads(text))
    except (OSError, ValueError):
        return AppSettings()


def save(settings: AppSettings) -> None:
    """Write atomically (temp file, then replace). Failures are swallowed: settings are a
    convenience and must never stop the app."""
    path = settings_path()
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(settings.to_json(), indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def update(**changes: Any) -> AppSettings:
    """Load, set the given fields, save and return the result."""
    s = load()
    known = {f.name for f in fields(AppSettings)}
    for key, value in changes.items():
        if key not in known:
            raise AttributeError(key)
        setattr(s, key, value)
    save(s)
    return s


def add_recent(s: AppSettings, target: Path | str, name: str, archetype: str) -> None:
    """Put a project at the top of the recent list (one entry per folder, max 10)."""
    key = str(Path(target)).casefold()
    s.recent_projects = [r for r in s.recent_projects if str(Path(r.target)).casefold() != key]
    s.recent_projects.insert(
        0,
        RecentProject(str(target), name, archetype, datetime.now().isoformat(timespec="seconds")),
    )
    del s.recent_projects[RECENT_MAX:]


def clamp_geometry(
    window: dict[str, int], screens: list[tuple[int, int, int, int]], minimum: tuple[int, int]
) -> tuple[int, int, int, int] | None:
    """(x, y, w, h) of the saved window moved and shrunk to fit an existing screen, or None when
    nothing was saved. ``screens`` are (x, y, w, h) available rectangles."""
    if not screens or not all(k in window for k in ("x", "y", "w", "h")):
        return None
    x, y, w, h = window["x"], window["y"], window["w"], window["h"]
    w, h = max(minimum[0], w), max(minimum[1], h)
    # the screen that holds most of the window's top-left area, else the first one
    chosen = screens[0]
    for sx, sy, sw, sh in screens:
        if sx <= x < sx + sw and sy <= y < sy + sh:
            chosen = (sx, sy, sw, sh)
            break
    sx, sy, sw, sh = chosen
    w, h = min(w, sw), min(h, sh)
    x = min(max(x, sx), sx + sw - w)
    y = min(max(y, sy), sy + sh - h)
    return x, y, w, h
