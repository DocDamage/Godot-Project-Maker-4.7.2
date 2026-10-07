"""Help > About: name, versions, license, link and the third-party notices."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import rpggen
from rpggen import godot_target, paths
from rpggen.core import runtime_version


def notices_text() -> str:
    try:
        return paths.notices_path().read_text(encoding="utf-8")
    except OSError:
        return "THIRD_PARTY_NOTICES.md was not found."


class NoticesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noticesDialog")
        self.setWindowTitle(self.tr("Third-party notices"))
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit(notices_text())
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutDialog")
        self.setWindowTitle(self.tr("About rpggen"))
        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>rpggen {rpggen.__version__}</h2>")
        title.setObjectName("aboutTitle")
        layout.addWidget(title)
        runtime = runtime_version.read_version(paths.templates_root()) or "?"
        self.details = QLabel(
            self.tr(
                "Builds playable Godot projects from asset packs.<br><br>"
                "Runtime addon version: {runtime}<br>"
                "Targets Godot: {godot}<br>"
                "License: MIT (see the third-party notices for the bundled components)<br>"
                '<a href="{url}">{url}</a>'
            ).format(
                runtime=runtime,
                godot=f"{godot_target.VERSION} ({godot_target.MAJOR_MINOR}.x accepted)",
                url=rpggen.REPO_URL,
            )
        )
        self.details.setObjectName("aboutDetails")
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setOpenExternalLinks(False)
        self.details.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        layout.addWidget(self.details)
        self.notices_button = QPushButton(self.tr("Third-party notices"))
        self.notices_button.setObjectName("noticesButton")
        self.notices_button.setToolTip(self.tr("The licenses of the components rpggen bundles"))
        self.notices_button.clicked.connect(self.show_notices)
        layout.addWidget(self.notices_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_notices(self) -> None:
        NoticesDialog(self).exec()


def notices_file() -> Path:
    return paths.notices_path()
