"""Analyze the packs of a wizard state in a worker behind a modal progress dialog."""

from __future__ import annotations

from PySide6.QtCore import SIGNAL, SLOT, QEventLoop, QObject, Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QPushButton, QWidget

from rpggen.gui import workers
from rpggen.gui.state import WizardState


def run_analysis(parent: QWidget, state: WizardState) -> bool:
    """Analyze in a worker behind a modal progress dialog; False when cancelled or failed."""
    worker = workers.Worker(workers.analyze_packs, state)
    dialog = QProgressDialog(parent.tr("Reading asset packs…"), parent.tr("Cancel"), 0, 0, parent)
    dialog.setObjectName("analysisProgress")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    # QProgressDialog hides itself on Cancel; it should stay and say "Stopping…" until the worker
    # has really stopped (within one file, one chunk or one image).
    QObject.disconnect(dialog, SIGNAL("canceled()"), dialog, SLOT("cancel()"))
    outcome: dict[str, object] = {}
    loop = QEventLoop()

    def on_progress(label: str, i: int, n: int) -> None:
        if outcome.get("stopping"):
            return  # the label stays on "Stopping…" until the worker has stopped
        dialog.setLabelText(label)
        dialog.setMaximum(n)  # 0 is a busy bar: the size of the stage is not known yet
        dialog.setValue(i)

    def on_cancel() -> None:
        outcome["stopping"] = True
        dialog.setLabelText(parent.tr("Stopping…"))
        cancel_button = dialog.findChild(QPushButton)
        if cancel_button is not None:
            cancel_button.setEnabled(False)
        worker.cancel()

    def on_done(result: object) -> None:
        outcome["result"] = result
        loop.quit()

    def on_failed(error: object) -> None:
        outcome["error"] = error
        loop.quit()

    worker.signals.progress.connect(on_progress)
    worker.signals.finished.connect(on_done)
    worker.signals.failed.connect(on_failed)
    dialog.canceled.connect(on_cancel)
    dialog.show()
    worker.start()
    loop.exec()
    dialog.close()
    if "result" not in outcome:
        error = outcome.get("error")
        if error is not None and not isinstance(error, workers.Cancelled):
            message = getattr(error, "message", None) or str(error)
            QMessageBox.warning(parent, parent.tr("Could not read the packs"), message)
        return False
    workers.apply_analysis(state, outcome["result"])  # type: ignore[arg-type]
    return True
