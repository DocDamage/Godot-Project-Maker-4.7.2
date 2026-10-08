"""Downloading the supported Godot: the confirmation and the download behind a progress dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from rpggen.core import godot_fetch
from rpggen.gui import workers
from rpggen.gui.widgets.task_progress import error_text, run_task


def _tr(text: str) -> str:
    return QCoreApplication.translate("GodotDownload", text)


def confirm(parent: QWidget, destination: Path) -> bool:
    answer = QMessageBox.question(
        parent,
        _tr("Download Godot"),
        _tr(
            "rpggen will download Godot {version} (about {mb} MB) from {source} and keep it in:"
            "\n\n{dest}\n\nThis is the only network access of this step. Continue?"
        ).format(
            version=godot_fetch.DEFAULT_VERSION,
            mb=godot_fetch.DOWNLOAD_MB[godot_fetch.current_platform()],
            source=godot_fetch.SOURCE_LABEL,
            dest=destination,
        ),
    )
    return answer == QMessageBox.StandardButton.Yes


def download(parent: QWidget, destination: Path) -> Path | None:
    """The downloaded executable; None when cancelled or failed (a failure is shown)."""
    outcome = run_task(
        parent,
        _tr("Downloading Godot…"),
        workers.download_godot,
        godot_fetch.DEFAULT_VERSION,
        destination,
        object_name="godotDownloadProgress",
        determinate=True,
    )
    if outcome.cancelled or isinstance(outcome.error, godot_fetch.FetchCancelled):
        return None
    if outcome.error is not None:
        QMessageBox.warning(parent, _tr("Could not download Godot"), error_text(outcome.error))
        return None
    return Path(outcome.value)
