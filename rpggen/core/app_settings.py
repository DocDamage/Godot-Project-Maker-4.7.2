"""Application settings that survive a restart (T11.09, T12.11).

Plain JSON at ``paths.config_dir()/settings.json``. It is not ``QSettings`` so that core code
works without Qt and the file can go into a diagnostic bundle. Loading never raises: a missing or
corrupt file gives the defaults, unknown keys are ignored (forward compatible) and values of the
wrong type fall back to their defaults one by one.

One ``SettingsStore`` per process (and file) holds the settings: ``get()`` answers from memory,
``update`` changes them, merges with what another window wrote meanwhile and writes atomically,
``schedule`` does the same after a short pause for values that change continuously (window size,
splitters). Nothing here touches a project folder: whether a recent project still exists is
asked separately (``available``), because a folder on an unplugged drive or a dead share must
neither disappear from the list nor stall the window.
"""

from __future__ import annotations

import atexit
import contextlib
import copy
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from rpggen import jsonio, paths

log = logging.getLogger(__name__)

FILE_NAME = "settings.json"
RECENT_MAX = 10
THUMB_SIZES = (64, 96, 128, 192)
THEMES = ("system", "dark", "light")  # "system" follows the operating system
WRITE_DELAY_S = 0.3  # a scheduled write waits this long for the next change


@dataclass
class RecentProject:
    target: str
    name: str = ""
    archetype: str = ""
    last_opened: str = ""  # ISO 8601, seconds
    # the packs the project was generated from: [{"path": ..., "stamp": pack_sniff.stamp}], so
    # the welcome view can say that one changed since (T13.08; a 1.0 entry has none)
    packs: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AppSettings:
    godot_exe: str = ""
    last_pack_dir: str = ""
    last_target_dir: str = ""
    recent_projects: list[RecentProject] = field(default_factory=list)  # newest first, max 10
    window: dict[str, int] = field(default_factory=dict)  # x, y, w, h, maximized
    splitters: dict[str, list[int]] = field(default_factory=dict)  # e.g. "audit"
    theme: str = "system"  # a first run follows the system; a saved choice is kept
    thumb_size: int = 96
    option_presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    quick_roles: list[str] = field(default_factory=list)  # the 1-9 keys of the audit page
    phase_timings: dict[str, float] = field(default_factory=dict)  # seconds of the last run
    timing_assets: int = 0  # how many assets that run had (the estimate scales by the ratio)
    cache_limit_gb: float = 10.0  # extracted archives: least recently used go beyond this
    keep_full_failed_runs: bool = False  # a failed run keeps its pack art and import cache
    confirm_regeneration: bool = True  # show the changes before a regeneration writes them
    language: str = ""  # the wizard's language ("fr"); "" follows the system (T12.56)
    group_by_folder: bool = False  # the audit grid shows a header per folder (T13.02)
    # how long each phase took on this computer: phase -> the last ten [assets, seconds] (T13.07)
    phase_history: dict[str, list[list[float]]] = field(default_factory=dict)

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
            "timing_assets": self.timing_assets,
            "cache_limit_gb": self.cache_limit_gb,
            "keep_full_failed_runs": self.keep_full_failed_runs,
            "confirm_regeneration": self.confirm_regeneration,
            "language": self.language,
            "group_by_folder": self.group_by_folder,
            "phase_history": {k: [list(p) for p in v] for k, v in self.phase_history.items()},
        }


HISTORY_LENGTH = 10
# phases whose time does not grow with the pack: their estimate is the median time itself
FIXED_PHASES = frozenset({"preflight", "promote", "report"})


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _history(raw: Any) -> dict[str, list[list[float]]]:
    """``phase_history`` as read from the file: well-formed pairs only, the last ten a phase."""
    out: dict[str, list[list[float]]] = {}
    if not isinstance(raw, dict):
        return out
    for phase, pairs in raw.items():
        if not isinstance(phase, str) or not isinstance(pairs, list):
            continue
        good = [
            [float(p[0]), float(p[1])]
            for p in pairs
            if isinstance(p, list) and len(p) == 2 and _number(p[0]) and _number(p[1])
        ]
        if good:
            out[phase] = good[-HISTORY_LENGTH:]
    return out


def add_phase_times(settings: AppSettings, timings: dict[str, float], assets: int) -> None:
    """Append one run's ``phase -> seconds`` (the phases that finished) to the history, each
    with the number of assets the run had; a phase keeps its last ten."""
    for phase, seconds in timings.items():
        if not _number(seconds):
            continue
        pairs = settings.phase_history.setdefault(phase, [])
        pairs.append([float(max(0, assets)), float(seconds)])
        del pairs[:-HISTORY_LENGTH]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def estimate(history: dict[str, list[list[float]]], phase: str, assets: int) -> float | None:
    """How long ``phase`` will take for ``assets`` assets, from the history: the median seconds
    per asset times the count, or the median seconds for a phase that does not scale with the
    assets (and when no run of the history counted its assets). None without history."""
    pairs = history.get(phase) or []
    if not pairs:
        return None
    counted = [p for p in pairs if p[0] > 0]
    if phase in FIXED_PHASES or not counted or assets <= 0:
        return _median([p[1] for p in pairs])
    return _median([p[1] / p[0] for p in counted]) * assets


def estimate_rest(
    history: dict[str, list[list[float]]], phases: list[str], assets: int
) -> float | None:
    """The estimate of several phases together; None when one of them has no history."""
    parts = [estimate(history, phase, assets) for phase in phases]
    return None if any(p is None for p in parts) else float(sum(p for p in parts if p is not None))


def settings_path() -> Path:
    return paths.config_dir() / FILE_NAME


def _str(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _packs(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    return [
        {"path": p["path"], "stamp": _str(p.get("stamp"), "")}
        for p in raw
        if isinstance(p, dict) and isinstance(p.get("path"), str)
    ]


def _recent(raw: Any) -> list[RecentProject]:
    out: list[RecentProject] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("target"), str):
            continue
        # A folder that is not there now (an unplugged drive, a share) stays in the list.
        out.append(
            RecentProject(
                item["target"],
                _str(item.get("name"), ""),
                _str(item.get("archetype"), ""),
                _str(item.get("last_opened"), ""),
                _packs(item.get("packs")),
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
    language = data.get("language")
    if isinstance(language, str) and language.replace("_", "").isalpha() and len(language) <= 8:
        s.language = language
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
    counted = data.get("timing_assets")
    if isinstance(counted, int) and not isinstance(counted, bool) and counted >= 0:
        s.timing_assets = counted
    confirm = data.get("confirm_regeneration")
    if isinstance(confirm, bool):
        s.confirm_regeneration = confirm
    s.phase_history = _history(data.get("phase_history"))
    grouped = data.get("group_by_folder")
    if isinstance(grouped, bool):
        s.group_by_folder = grouped
    keep = data.get("keep_full_failed_runs")
    if isinstance(keep, bool):
        s.keep_full_failed_runs = keep
    limit = data.get("cache_limit_gb")
    if isinstance(limit, (int, float)) and not isinstance(limit, bool) and 1 <= limit <= 1000:
        s.cache_limit_gb = float(limit)
    return s


def _read(path: Path) -> AppSettings:
    """The settings in ``path``, or the defaults; never raises."""
    try:
        return from_json(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return AppSettings()


_FIELDS = tuple(f.name for f in fields(AppSettings))


def _merge(disk: AppSettings, before: AppSettings, ours: AppSettings) -> AppSettings:
    """What is on disk now with this process's changes (``before`` to ``ours``) applied.

    A scalar or list that this process changed wins; one it did not touch keeps the disk value, so
    two windows that change different keys both keep their changes. A dict is merged by key. Recent
    projects merge by folder, newest first.
    """
    merged = copy.deepcopy(disk)
    for name in _FIELDS:
        old, new, current = getattr(before, name), getattr(ours, name), getattr(merged, name)
        if old == new:
            continue
        if name == "recent_projects":
            setattr(merged, name, _merge_recent(current, old, new))
        elif isinstance(new, dict) and isinstance(current, dict):
            result = dict(current)
            for key in set(old) - set(new):
                result.pop(key, None)
            for key, value in new.items():
                if old.get(key) != value:
                    result[key] = copy.deepcopy(value)
            setattr(merged, name, result)
        else:
            setattr(merged, name, copy.deepcopy(new))
    return merged


def _merge_recent(
    disk: list[RecentProject], old: list[RecentProject], new: list[RecentProject]
) -> list[RecentProject]:
    def key(project: RecentProject) -> str:
        return str(Path(project.target)).casefold()

    removed = {key(p) for p in old} - {key(p) for p in new}
    old_by_key = {key(p): p for p in old}
    changed = [p for p in new if old_by_key.get(key(p)) != p]
    best: dict[str, RecentProject] = {}
    for project in [*(p for p in disk if key(p) not in removed), *changed]:
        known = best.get(key(project))
        if known is None or project.last_opened >= known.last_opened:
            best[key(project)] = project
    ordered = sorted(best.values(), key=lambda p: p.last_opened, reverse=True)
    return ordered[:RECENT_MAX]


class SettingsStore:
    """The settings of one file, shared by everything in the process."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._settings: AppSettings | None = None
        self._pending: threading.Timer | None = None
        self._unwritten: AppSettings | None = None  # the settings before the scheduled changes

    def get(self) -> AppSettings:
        """The current settings, from memory (the file is read once, on the first call). Treat
        the result as read-only: change settings with ``update`` or ``schedule``."""
        with self._lock:
            if self._settings is None:
                self._settings = _read(self.path)
            return self._settings

    def reload(self) -> AppSettings:
        """Forget the memory and read the file again."""
        with self._lock:
            self._settings = _read(self.path)
            return self._settings

    def _apply(
        self, fn: Callable[[AppSettings], None] | None, changes: dict[str, Any]
    ) -> tuple[AppSettings, AppSettings]:
        known = set(_FIELDS)
        for key in changes:
            if key not in known:
                raise AttributeError(key)
        current = self.get()
        before = copy.deepcopy(current)
        if fn is not None:
            fn(current)
        for key, value in changes.items():
            setattr(current, key, value)
        return before, current

    def update(
        self, fn: Callable[[AppSettings], None] | None = None, /, **changes: Any
    ) -> AppSettings:
        """Apply a change, merge it with what is on disk now and write the result at once.
        Failures to write are logged and swallowed: settings are a convenience."""
        with self._lock:
            before, ours = self._apply(fn, changes)
            if self._unwritten is not None:  # earlier scheduled changes go out with this one
                before = self._unwritten
            self._write(before, ours)
            return self.get()

    def schedule(
        self, fn: Callable[[AppSettings], None] | None = None, /, **changes: Any
    ) -> AppSettings:
        """Apply a change in memory now and write it after ``WRITE_DELAY_S`` without another
        one (flushed when the program exits)."""
        with self._lock:
            before, ours = self._apply(fn, changes)
            if self._unwritten is None:
                self._unwritten = before
            if self._pending is not None:
                self._pending.cancel()
            self._pending = threading.Timer(WRITE_DELAY_S, self.flush)
            self._pending.daemon = True
            self._pending.start()
            return ours

    def flush(self) -> None:
        """Write what ``schedule`` still holds back."""
        with self._lock:
            if self._pending is not None:
                self._pending.cancel()
                self._pending = None
            if self._unwritten is None:
                return
            before = self._unwritten
            self._unwritten = None
            self._write(before, self.get())

    def _write(self, before: AppSettings, ours: AppSettings) -> None:
        self._unwritten = None
        merged = _merge(_read(self.path), before, ours)
        try:
            jsonio.write(self.path, merged.to_json())
        except (OSError, TypeError, ValueError):
            log.warning("could not write the settings to %s", self.path, exc_info=True)
        self._settings = merged


_stores: dict[Path, SettingsStore] = {}
_stores_lock = threading.Lock()


def store() -> SettingsStore:
    """The store of the current settings file (one per path, so that a test that points
    ``RPGGEN_CACHE_DIR`` somewhere else gets its own)."""
    path = settings_path()
    with _stores_lock:
        found = _stores.get(path)
        if found is None:
            found = _stores[path] = SettingsStore(path)
        return found


def get() -> AppSettings:
    """The current settings from memory (see ``SettingsStore.get``)."""
    return store().get()


def flush_all() -> None:
    """Write every store's scheduled changes (registered to run when the program exits)."""
    with _stores_lock:
        stores = list(_stores.values())
    for item in stores:
        item.flush()


atexit.register(flush_all)


def load() -> AppSettings:
    """The saved settings read from the file now, or the defaults; never raises. The GUI uses
    ``get()``."""
    return _read(settings_path())


def save(settings: AppSettings) -> None:
    """Make ``settings`` the saved ones (what differs from the store is written, merged with
    what another window wrote)."""

    def assign(current: AppSettings) -> None:
        for name in _FIELDS:
            setattr(current, name, copy.deepcopy(getattr(settings, name)))

    store().update(assign)


def update(**changes: Any) -> AppSettings:
    """Set the given fields and write them (see ``SettingsStore.update``)."""
    return store().update(**changes)


def schedule(**changes: Any) -> AppSettings:
    """Set the given fields now and write them after a short pause."""
    return store().schedule(**changes)


def available(
    targets: list[str],
    timeout_s: float = 2.0,
    is_dir: Callable[[str], bool] = os.path.isdir,
) -> dict[str, bool]:
    """Which of these folders can be reached now. Each is asked in a thread of its own with
    ``timeout_s``: a folder on a dead network share counts as unavailable instead of stalling.
    The threads are daemons, so a stuck one never keeps the program from exiting."""
    results: dict[str, bool] = {}
    threads: list[tuple[str, threading.Thread]] = []

    def ask(target: str) -> None:
        with contextlib.suppress(OSError):
            results[target] = bool(is_dir(target))

    for target in targets:
        thread = threading.Thread(target=ask, args=(target,), daemon=True)
        thread.start()
        threads.append((target, thread))
    deadline = time.monotonic() + timeout_s
    for _target, thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    return {target: results.get(target, False) for target in targets}


def add_recent(
    s: AppSettings,
    target: Path | str,
    name: str,
    archetype: str,
    packs: list[dict[str, str]] | None = None,
) -> None:
    """Put a project at the top of the recent list (one entry per folder, max 10). ``packs``
    are the packs it was generated from, each with its stamp; without them an entry that is
    already there keeps the ones it has."""
    key = str(Path(target)).casefold()
    before = next((r for r in s.recent_projects if str(Path(r.target)).casefold() == key), None)
    if packs is None:
        packs = list(before.packs) if before is not None else []
    s.recent_projects = [r for r in s.recent_projects if str(Path(r.target)).casefold() != key]
    s.recent_projects.insert(
        0,
        RecentProject(
            str(target), name, archetype, datetime.now().isoformat(timespec="seconds"), packs
        ),
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
