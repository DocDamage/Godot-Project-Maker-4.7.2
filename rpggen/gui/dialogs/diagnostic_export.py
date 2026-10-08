"""The "Export diagnostic bundle" action shared by the crash dialog and the results page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from rpggen import paths
from rpggen.core import diagnostics


def app_log_dir() -> Path:
    return paths.log_dir()


def choose_save_path(parent: QWidget | None, default_name: str) -> Path | None:
    text, _ = QFileDialog.getSaveFileName(
        parent, "Export diagnostic bundle", default_name, "Zip (*.zip)"
    )
    return Path(text) if text else None


def show_message(parent: QWidget | None, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def export_bundle(
    parent: QWidget | None, folder: Path | None, godot_exe: Path | None = None
) -> Path | None:
    """Ask where to save, write the bundle of ``folder`` (a project or a failed run; None for a
    crash before any project exists) and say where it went. Returns the zip or None."""
    default = diagnostics.default_bundle_name(folder) if folder else "rpggen-diagnostics.zip"
    out = choose_save_path(parent, default)
    if out is None:
        return None
    source = folder if folder is not None and Path(folder).is_dir() else app_log_dir()
    source.mkdir(parents=True, exist_ok=True)
    try:
        # the application log contributes only the lines of the run that made the project
        diagnostics.make_bundle(source, out, godot_exe, app_log_dir=app_log_dir())
    except OSError as exc:
        QMessageBox.warning(parent, "rpggen", str(exc))
        return None
    show_message(
        parent,
        "rpggen",
        f"Saved {out}\nIt contains no art, only names, sizes and hashes. "
        "Please attach it to your bug report.",
    )
    return out
