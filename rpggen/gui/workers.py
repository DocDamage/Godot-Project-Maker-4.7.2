"""Background work: a QRunnable that reports through signals and never touches widgets."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from rpggen.core import archive, inventory
from rpggen.core import catalog as catalog_mod
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

    def callbacks(self) -> Callbacks:
        return Callbacks(
            on_phase=lambda name, i, n: self.signals.progress.emit(name, i, n),
            on_log=lambda line: self.signals.log.emit(line),
            is_cancelled=self.is_cancelled,
        )

    def run(self) -> None:
        try:
            result = self.fn(*self.args, callbacks=self.callbacks(), **self.kwargs)
        except RpgGenError as exc:
            self.signals.failed.emit(exc.issue)
        except BaseException as exc:
            log.exception("worker failed")
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)

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
    opened_list: list[archive.OpenedPack] = []
    pairs: list[tuple[archive.OpenedPack, inventory.Inventory]] = []
    issues = IssueList()
    for i, source in enumerate(sources, start=1):
        if callbacks.is_cancelled():
            raise Cancelled
        callbacks.on_phase(f"Reading {source.name}", i, total)
        callbacks.on_log(f"opening {source}")
        opened = archive.open_pack(source, used)
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


def apply_analysis(state: WizardState, result: AnalysisResult) -> None:
    state.opened_packs = result.opened
    state.inventories = result.inventories
    state.catalog = result.catalog
