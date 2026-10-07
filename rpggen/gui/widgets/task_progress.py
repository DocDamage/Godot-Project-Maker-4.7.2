"""Run one background function behind a modal progress dialog with Cancel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtWidgets import QProgressDialog, QWidget

from rpggen.gui import workers


@dataclass
class TaskOutcome:
    """``cancelled``: the user abandoned the task; a late result is ignored.
    ``error``: an Issue or exception when the function failed."""

    value: Any = None
    error: Any = None
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return not self.cancelled and self.error is None


def run_task(
    parent: QWidget,
    label: str,
    fn: Callable[..., Any],
    *args: Any,
    object_name: str = "taskProgress",
    determinate: bool = False,
    **kwargs: Any,
) -> TaskOutcome:
    """Run ``fn(*args, callbacks=..., **kwargs)`` in a worker; the dialog stays up (indeterminate
    unless ``determinate``; progress arrives as (label, done, total)). Cancel closes the dialog at
    once and the worker's late result is dropped, because blocking calls such as ``urlopen``
    cannot be interrupted; ``fn`` can poll ``callbacks.is_cancelled`` to stop sooner."""
    worker = workers.Worker(fn, *args, **kwargs)
    dialog = QProgressDialog(label, parent.tr("Cancel"), 0, 100 if determinate else 0, parent)
    dialog.setObjectName(object_name)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    outcome = TaskOutcome()
    loop = QEventLoop()
    token = {"open": True}  # the request token: signals after cancel are ignored

    def on_progress(text: str, done: int, total: int) -> None:
        if not token["open"]:
            return
        if text:
            dialog.setLabelText(text)
        if determinate and total > 0:
            dialog.setMaximum(total)
            dialog.setValue(min(done, total))

    def finish(value: Any = None, error: Any = None) -> None:
        if not token["open"]:
            return
        token["open"] = False
        outcome.value, outcome.error = value, error
        loop.quit()

    def on_cancel() -> None:
        if not token["open"]:
            return
        token["open"] = False
        outcome.cancelled = True
        worker.cancel()
        loop.quit()

    worker.signals.progress.connect(on_progress)
    worker.signals.finished.connect(lambda result: finish(value=result))
    worker.signals.failed.connect(lambda error: finish(error=error))
    dialog.canceled.connect(on_cancel)
    dialog.show()
    worker.start()
    loop.exec()
    dialog.close()
    dialog.deleteLater()
    return outcome


def error_text(error: object) -> str:
    return str(getattr(error, "message", None) or error)
