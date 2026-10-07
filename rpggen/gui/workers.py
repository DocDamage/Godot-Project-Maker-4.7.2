"""Background work: a QRunnable that reports through signals and never touches widgets."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from rpggen.core import archive, inventory, orchestrator
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core.orchestrator import Callbacks
from rpggen.errors import Issue, IssueList, RpgGenError
from rpggen.gui.state import WizardState

log = logging.getLogger(__name__)


class Cancelled(Exception):
    """Raised by worker functions that stop because ``is_cancelled`` returned True."""


class WorkerSignals(QObject):
    progress = Signal(str, int, int)  # phase/label, i, n
    log = Signal(str)
    finished = Signal(object)  # result
    failed = Signal(object)  # Issue or exception


class Worker(QRunnable):
    """Runs ``fn(*args, callbacks=Callbacks(...), **kwargs)`` on the global thread pool."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancel = threading.Event()
        self.setAutoDelete(False)  # the signals object must outlive run() for queued delivery

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def _emit(self, signal_name: str, *args: Any) -> None:
        try:
            getattr(self.signals, signal_name).emit(*args)
        except RuntimeError:  # the receiving side was destroyed (window closed)
            self.cancel()

    def callbacks(self) -> Callbacks:
        return Callbacks(
            on_phase=lambda name, i, n: self._emit("progress", name, i, n),
            on_log=lambda line: self._emit("log", line),
            is_cancelled=self.is_cancelled,
        )

    def run(self) -> None:
        try:
            result = self.fn(*self.args, callbacks=self.callbacks(), **self.kwargs)
        except RpgGenError as exc:
            self._emit("failed", exc.issue)
        except BaseException as exc:
            log.exception("worker failed")
            self._emit("failed", exc)
        else:
            self._emit("finished", result)

    def start(self, pool: QThreadPool | None = None) -> None:
        (pool or QThreadPool.globalInstance()).start(self)


# --------------------------------------------------------------------------- worker functions


@dataclass
class AnalysisResult:
    opened: list[archive.OpenedPack] = field(default_factory=list)
    inventories: list[inventory.Inventory] = field(default_factory=list)
    catalog: catalog_mod.Catalog | None = None
    issues: list[Issue] = field(default_factory=list)


def analyze_packs(state: WizardState, *, callbacks: Callbacks) -> AnalysisResult:
    """Open, inventory and assemble the packs of ``state`` (reads the state, never mutates it).

    The existing ``state.catalog`` (a draft or a generated project's catalog) is the ``previous``
    of ``assemble`` so the user's overrides survive.
    """
    sources = list(state.pack_sources)
    total = len(sources) + 1
    used: set[str] = set()
    # A project that is regenerated keeps its pack ids (also for a pack that was updated from
    # an archive with another name), or every asset id would change.
    wanted = {
        str(Path(p.source).resolve()).casefold(): p.pack_id
        for p in (state.config.packs if state.config else [])
    }
    wanted.update({str(Path(s).resolve()).casefold(): pid for s, pid in state.pack_updates.items()})
    opened_list: list[archive.OpenedPack] = []
    pairs: list[tuple[archive.OpenedPack, inventory.Inventory]] = []
    issues = IssueList()
    for i, source in enumerate(sources, start=1):
        if callbacks.is_cancelled():
            raise Cancelled
        callbacks.on_phase(f"Reading {source.name}", i, total)
        callbacks.on_log(f"opening {source}")
        opened = archive.open_pack(
            source, used, pack_id=wanted.get(str(Path(source).resolve()).casefold())
        )
        used.add(opened.pack_id)
        inv = inventory.build_inventory(opened)
        opened_list.append(opened)
        pairs.append((opened, inv))
    if callbacks.is_cancelled():
        raise Cancelled
    callbacks.on_phase("Analyzing images", total, total)
    cat, found, _generated = catalog_mod.assemble(pairs, state.catalog, [])
    issues.extend(found)
    return AnalysisResult(opened_list, [inv for _o, inv in pairs], cat, list(issues))


def fetch_registry(
    inventories: list[inventory.Inventory],
    *,
    callbacks: Callbacks,
    fetch: Callable[[list[inventory.Inventory]], Any] | None = None,
) -> Any:
    """Download the registry index and match it against the packs (network; worker thread)."""
    from rpggen.core import profile_registry

    callbacks.on_phase("Looking for matching profiles…", 0, 0)
    if fetch is not None:
        return fetch(inventories)
    return profile_registry.candidates(profile_registry.fetch_index(), inventories)


def download_profile(
    profile_id: str,
    *,
    callbacks: Callbacks,
    download: Callable[[str], Any] | None = None,
) -> Any:
    """Download and install one registry profile (network; worker thread)."""
    from rpggen.core import profile_registry

    callbacks.on_phase("Downloading the profile…", 0, 0)
    if download is not None:
        return download(profile_id)
    return profile_registry.download_profile(profile_id)


def download_godot(
    version: str, out: Path, *, callbacks: Callbacks, platform: str | None = None
) -> Path:
    """Download the official Godot into ``out`` (network; worker thread)."""
    import sys

    from rpggen.core import godot_fetch

    def progress(done: int, total: int) -> None:
        mb = 1 << 20
        text = (
            f"Downloading Godot {version}… {done // mb} of {total // mb} MB"
            if total
            else (f"Downloading Godot {version}… {done // mb} MB")
        )
        callbacks.on_phase(text, done, total)

    plat = platform or ("linux" if sys.platform.startswith("linux") else "windows")
    return godot_fetch.fetch(
        version, out, plat, progress=progress, is_cancelled=callbacks.is_cancelled
    )


def find_working_godot(*, callbacks: Callbacks) -> tuple[Path, str] | None:
    """The first Godot (saved path, then the usual places) that passes the version gate, with
    its version text; None when there is none (worker thread: it launches Godot)."""
    from rpggen.core import app_settings, godot

    candidates: list[Path] = []
    saved = app_settings.load().godot_exe
    if saved and Path(saved).is_file():
        candidates.append(Path(saved))
    candidates.extend(p for p in godot.auto_find_godot() if p not in candidates)
    for exe in candidates:
        if callbacks.is_cancelled():
            return None
        try:
            version = godot.detect_version(exe)
            godot.check_version(version)
        except (RpgGenError, OSError):
            continue
        return exe, ".".join(str(p) for p in version[:3]) + f".{version[3]}"
    return None


def check_for_update(
    *, callbacks: Callbacks, fetch: Callable[[str, int], bytes] | None = None
) -> Any:
    """The latest release of the project or None (network; worker thread; raises
    RegistryError when offline)."""
    from rpggen.core import update_check

    callbacks.on_phase("Checking for updates…", 0, 0)
    return update_check.latest_release(fetch)


def apply_analysis(state: WizardState, result: AnalysisResult) -> None:
    state.opened_packs = result.opened
    state.inventories = result.inventories
    state.catalog = result.catalog


# --------------------------------------------------------------------------- generation


def generate(
    cfg: config_mod.GeneratorConfig,
    catalog: catalog_mod.Catalog | None,
    target: Path,
    godot_exe: Path,
    placeholders: list[str],
    git_message: str | None = None,
    force_while_open: bool = False,
    *,
    callbacks: Callbacks,
) -> orchestrator.RunResult:
    """Run the whole pipeline for the wizard's in-memory config and catalog."""
    return orchestrator.run_in_memory(
        cfg,
        catalog,
        target,
        godot_exe,
        callbacks,
        placeholders=placeholders,
        force_while_open=force_while_open,
        git_message=git_message,
    )
