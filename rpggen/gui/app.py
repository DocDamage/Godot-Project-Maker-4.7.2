"""GUI entry point: QApplication, stylesheet, crash dialog and the main window."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import logging_setup
from rpggen.core import app_settings
from rpggen.errors import CODES
from rpggen.gui import theme, translations, workers
from rpggen.gui.dialogs import diagnostic_export
from rpggen.gui.wizard import MainWindow

log = logging.getLogger(__name__)


def load_stylesheet(name: str = "dark") -> str:
    return theme.stylesheet(name)


class CrashDialog(QDialog):
    """GUI-001: shows an unhandled exception with a collapsible traceback."""

    def __init__(
        self, text: str, parent: QWidget | None = None, target: Path | None = None
    ) -> None:
        super().__init__(parent)
        self.target = target
        self.setObjectName("crashDialog")
        self.setWindowTitle(self.tr("Unexpected error"))
        self.resize(640, 200)
        info = CODES["GUI-001"]
        reason = text.strip().splitlines()[-1] if text.strip() else "unknown"
        layout = QVBoxLayout(self)
        message = QLabel(f"GUI-001: {info.message.format(reason=reason)}\n{info.fix}")
        message.setObjectName("crashMessage")
        message.setWordWrap(True)
        layout.addWidget(message)
        self.details_toggle = QToolButton()
        self.details_toggle.setObjectName("crashDetailsToggle")
        self.details_toggle.setText(self.tr("Show details"))
        self.details_toggle.setCheckable(True)
        layout.addWidget(self.details_toggle)
        self.details = QPlainTextEdit(text)
        self.details.setObjectName("crashDetails")
        self.details.setReadOnly(True)
        self.details.setVisible(False)
        layout.addWidget(self.details)
        self.details_toggle.toggled.connect(self.details.setVisible)
        buttons = QDialogButtonBox()
        self.export_button = QPushButton(self.tr("Export diagnostic bundle"))
        self.export_button.setObjectName("crashExportButton")
        self.export_button.setToolTip(
            self.tr("Save a zip with logs and settings (no art) to attach to a bug report")
        )
        self.export_button.clicked.connect(self.export_bundle)
        buttons.addButton(self.export_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def export_bundle(self) -> Path | None:
        return diagnostic_export.export_bundle(self, self.target)


def install_excepthook() -> None:
    def hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.error("unhandled exception\n%s", text)
        if QApplication.instance() is None or issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        CrashDialog(text).exec()

    sys.excepthook = hook


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    assert isinstance(app, QApplication)
    app.setStyle("Fusion")
    theme.apply_theme(theme.saved_theme(), remember=False)
    theme.install_focus_ring(app)
    translations.install(app_settings.get().language)  # before any widget sets its texts
    return app


def run_gui(argv: list[str] | None = None, target: Path | None = None) -> int:
    """Open the wizard; with ``target`` (an existing project, e.g. from the editor's "Open
    generator") the project page starts with that output folder."""
    from rpggen.core import cache_policy

    cache_policy.migrate()  # an older version kept everything in one folder
    app = create_app(argv)
    logging_setup.configure(diagnostic_export.app_log_dir(), False)
    install_excepthook()
    window = MainWindow(show_welcome=target is None)
    if target is not None:
        window.open_target(target)
    window.show()
    pruning = workers.Worker(workers.prune_job)  # bounded caches: the oldest archives go first
    pruning.start()
    return app.exec()
