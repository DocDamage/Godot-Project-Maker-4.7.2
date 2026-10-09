"""Background work: a QRunnable that reports through signals and never touches widgets."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from rpggen.core import archive, inventory, learned_rules, orchestrator
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
    skipped = Signal(str, str)  # phase, issue code: a check that did not run
    step = Signal(str, int, int, str)  # phase, i, n, label: progress inside a Godot phase
    finished = Signal(object)  # result
    failed = Signal(object)  # Issue or exception
    confirmation = Signal(object)  # a PromotionSummary: the page asks, then calls ``answer``


class Worker(QRunnable):
    """Runs ``fn(*args, callbacks=Callbacks(...), **kwargs)`` on the global thread pool."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancel = threading.Event()
        self.confirm_promotions = False  # ask the page before a regeneration writes
        self._answered = threading.Event()
        self._answer = False
        self.setAutoDelete(False)  # the signals object must outlive run() for queued delivery

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def answer(self, yes: bool) -> None:
        """The page's reply to a ``confirmation`` signal."""
        self._answer = yes
        self._answered.set()

    def _confirm_promotion(self, summary: Any) -> bool:
        """Runs on the worker thread: ask the page and wait for the reply (a cancel is a no)."""
        if not self.confirm_promotions:
            return True
        self._answered.clear()
        self._emit("confirmation", summary)
        while not self._answered.wait(0.1):
            if self.is_cancelled():
                return False
        return self._answer and not self.is_cancelled()

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
            on_skip=lambda phase, code: self._emit("skipped", phase, code),
            on_step=lambda phase, i, n, label: self._emit("step", phase, i, n, label),
            confirm_promotion=self._confirm_promotion,
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


PROGRESS_INTERVAL_S = 0.1  # at most ten progress signals a second


def format_bytes(count: int) -> str:
    """1.2 GB, 340 MB or 12 KB (binary units, one decimal from a gigabyte on)."""
    if count >= 1 << 30:
        return f"{count / (1 << 30):.1f} GB"
    if count >= 1 << 20:
        return f"{count / (1 << 20):.0f} MB"
    return f"{max(count, 0) / (1 << 10):.0f} KB"


class ProgressSink:
    """Turns the progress of the layers (extract, read, analyze) into ``on_phase`` calls.

    A stage reports ``(label, done, total)``; the label shown is "label — done of total" with
    bytes or counts. The calls are throttled to ten a second, but the last one of a stage (done
    equals total) always goes through, so a bar reaches its maximum only at the end of a stage.
    Values of a byte stage are sent in KB, which stay within the range of a progress bar.
    """

    def __init__(self, callbacks: Callbacks, interval: float = PROGRESS_INTERVAL_S) -> None:
        self.callbacks = callbacks
        self.interval = interval
        self._last = 0.0
        self._stage = ""

    def _send(self, text: str, done: int, total: int, last: bool) -> None:
        now = time.monotonic()
        if not last and now - self._last < self.interval:
            return
        self._last = now
        self.callbacks.on_phase(text, done, total)

    def bytes(self, label: str, done: int, total: int) -> None:
        if total <= 0:
            self._send(label, 0, 0, last=label != self._stage)
        else:
            text = f"{label} — {format_bytes(done)} of {format_bytes(total)}"
            self._send(text, done >> 10, total >> 10, last=done >= total or label != self._stage)
        self._stage = label

    def count(self, label: str, done: int, total: int) -> None:
        if total <= 0:
            self._send(label, 0, 0, last=label != self._stage)
        else:
            text = f"{label} — {done:,} of {total:,}"
            self._send(text, done, total, last=done >= total or label != self._stage)
        self._stage = label


def analyze_packs(state: WizardState, *, callbacks: Callbacks) -> AnalysisResult:
    """Open, inventory and assemble the packs of ``state`` (reads the state, never mutates it).

    The existing ``state.catalog`` (a draft or a generated project's catalog) is the ``previous``
    of ``assemble`` so the user's overrides survive. Every stage reports its progress and polls
    ``callbacks.is_cancelled``: a cancel answers within one file, one chunk or one image.
    """
    sources = list(state.pack_sources)
    sink = ProgressSink(callbacks)
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
    try:
        for source in sources:
            if callbacks.is_cancelled():
                raise Cancelled
            callbacks.on_phase(f"Reading {source.name}", 0, 0)  # until the first real figure
            callbacks.on_log(f"opening {source}")
            opened = archive.open_pack(
                source,
                used,
                pack_id=wanted.get(str(Path(source).resolve()).casefold()),
                progress=sink.bytes,
                is_cancelled=callbacks.is_cancelled,
            )
            used.add(opened.pack_id)
            inv = inventory.build_inventory(
                opened, progress=sink.count, is_cancelled=callbacks.is_cancelled
            )
            opened_list.append(opened)
            pairs.append((opened, inv))
        if callbacks.is_cancelled():
            raise Cancelled
        callbacks.on_phase("Analyzing images", 0, 0)
        cat, found, _generated = catalog_mod.assemble(
            pairs,
            state.catalog,
            [],
            is_cancelled=callbacks.is_cancelled,
            progress=sink.count,
            learned=learned_rules.load().rules,  # the user's earlier fixes (T12.59)
        )
    except archive.Cancelled as exc:  # also catalog.AssemblyCancelled
        raise Cancelled from exc
    issues.extend(found)
    _prune_caches([o.root for o in opened_list])  # the packs just opened are in use
    return AnalysisResult(opened_list, [inv for _o, inv in pairs], cat, list(issues))


def _prune_caches(in_use: list[Path]) -> None:
    """Keep the caches within their limits (never the archives in use); never raises."""
    from rpggen.core import app_settings, cache_policy

    try:
        cache_policy.prune(app_settings.get().cache_limit_gb, keep=in_use)
    except Exception:  # noqa: BLE001 - housekeeping must never fail an analysis
        log.debug("pruning the caches failed", exc_info=True)


def prune_job(*, callbacks: Callbacks) -> dict[str, int]:
    """Start-up housekeeping, run in a worker."""
    from rpggen.core import app_settings, cache_policy

    return cache_policy.prune(app_settings.get().cache_limit_gb)


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
    from rpggen.core import godot_fetch

    def progress(done: int, total: int) -> None:
        mb = 1 << 20
        text = (
            f"Downloading Godot {version}… {done // mb} of {total // mb} MB"
            if total
            else (f"Downloading Godot {version}… {done // mb} MB")
        )
        callbacks.on_phase(text, done, total)

    plat = platform or godot_fetch.current_platform()
    return godot_fetch.fetch(
        version, out, plat, progress=progress, is_cancelled=callbacks.is_cancelled
    )


def find_working_godot(*, callbacks: Callbacks) -> tuple[Path, str] | None:
    """The first Godot (saved path, then the usual places) that passes the version gate, with
    its version text; None when there is none (worker thread: it launches Godot)."""
    from rpggen.core import app_settings, godot

    candidates: list[Path] = []
    saved = app_settings.get().godot_exe
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
    accept_runtime_upgrade: bool = False,
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
        accept_runtime_upgrade=accept_runtime_upgrade,
    )
