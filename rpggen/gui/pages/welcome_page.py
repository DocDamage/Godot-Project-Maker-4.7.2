"""The welcome view shown before page 1: three big choices, recent projects and a Godot check.

It is not a numbered wizard step; the window hides the sidebar and the button bar while it shows.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import godot_target
from rpggen.core import app_settings
from rpggen.gui import workers


class WelcomePage(QWidget):
    """Emits what the user chose; the window does the navigation."""

    trySampleRequested = Signal()
    ownPackRequested = Signal()
    openProjectRequested = Signal()  # ask for a folder
    recentChosen = Signal(str)  # a recent project's folder
    downloadGodotRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomePage")
        self._godot_generation = 0
        self._worker: workers.Worker | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 16)
        title = QLabel(self.tr("Welcome to rpggen"))
        title.setObjectName("welcomeTitle")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)
        subtitle = QLabel(self.tr("Turn an asset pack into a playable Godot project."))
        subtitle.setObjectName("welcomeSubtitle")
        layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.sample_card = self._card(
            "sampleCard",
            self.tr("Try the sample"),
            self.tr("See a finished project in about a minute. Nothing to configure."),
            self.trySampleRequested,
            self.tr("Fills in the bundled sample pack and goes straight to the options"),
        )
        self.own_card = self._card(
            "ownPackCard",
            self.tr("Start with my asset pack"),
            self.tr("Add the packs you own, check what rpggen detected, then generate."),
            self.ownPackRequested,
            self.tr("Opens the first wizard page"),
        )
        self.open_card = self._card(
            "openProjectCard",
            self.tr("Open an existing project"),
            self.tr("Change the options of a project made with rpggen and regenerate it safely."),
            self.openProjectRequested,
            self.tr("Choose a project folder"),
        )
        for card in (self.sample_card, self.own_card, self.open_card):
            cards.addWidget(card, 1)
        layout.addLayout(cards)

        self.recent_label = QLabel(self.tr("Recent projects"))
        self.recent_label.setObjectName("recentLabel")
        layout.addWidget(self.recent_label)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentList")
        self.recent_list.setToolTip(self.tr("Double-click or press Enter to open a project"))
        self.recent_list.itemActivated.connect(self._on_recent_activated)
        layout.addWidget(self.recent_list, 1)

        status = QHBoxLayout()
        self.godot_status = QLabel(self.tr("Looking for Godot…"))
        self.godot_status.setObjectName("welcomeGodotStatus")
        status.addWidget(self.godot_status, 1)
        self.download_button = QPushButton(
            self.tr("Download Godot {0}").format(godot_target.VERSION)
        )
        self.download_button.setObjectName("welcomeDownloadGodot")
        self.download_button.setToolTip(
            self.tr("Downloads the official Godot from github.com/godotengine/godot/releases")
        )
        self.download_button.setVisible(False)
        self.download_button.clicked.connect(self.downloadGodotRequested)
        status.addWidget(self.download_button)
        layout.addLayout(status)
        self.refresh()

    def _card(self, name: str, title: str, text: str, signal: Signal, tip: str) -> QToolButton:
        card = QToolButton()
        card.setObjectName(name)
        card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        card.setText(f"{title}\n\n{text}")
        card.setToolTip(tip)
        card.setMinimumHeight(120)
        card.setStyleSheet("QToolButton { text-align: left; padding: 14px; font-size: 13px; }")
        card.clicked.connect(signal)
        return card

    # ------------------------------------------------------------------ content

    def refresh(self) -> None:
        """Reload the recent projects and look for Godot again."""
        self._fill_recent()
        self.check_godot()

    def _fill_recent(self) -> None:
        self.recent_list.clear()
        recent = app_settings.load().recent_projects  # folders that vanished are dropped
        for project in recent:
            when = ""
            with contextlib.suppress(ValueError):
                when = datetime.fromisoformat(project.last_opened).strftime("%Y-%m-%d %H:%M")
            kind = {"turn_based": "turn-based", "arpg": "action"}.get(
                project.archetype, project.archetype
            )
            name = project.name or Path(project.target).name
            item = QListWidgetItem(f"{name}  ·  {kind}  ·  {project.target}  ·  {when}")
            item.setData(Qt.ItemDataRole.UserRole, project.target)
            self.recent_list.addItem(item)
        self.recent_label.setVisible(bool(recent))
        self.recent_list.setVisible(bool(recent))

    def recent_targets(self) -> list[str]:
        return [
            self.recent_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.recent_list.count())
        ]

    def _on_recent_activated(self, item: QListWidgetItem) -> None:
        self.recentChosen.emit(item.data(Qt.ItemDataRole.UserRole))

    def check_godot(self) -> None:
        """Find a usable Godot in a worker (it launches Godot to read the version)."""
        self._godot_generation += 1
        generation = self._godot_generation
        self.godot_status.setText(self.tr("Looking for Godot…"))
        worker = workers.Worker(workers.find_working_godot)

        def done(found: object) -> None:
            if generation == self._godot_generation:
                self.show_godot(found)

        def failed(_error: object) -> None:
            if generation == self._godot_generation:
                self.show_godot(None)

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._worker = worker  # keep it alive until its signals are delivered
        worker.start()

    def show_godot(self, found: object) -> None:
        if found:
            exe, version = found  # type: ignore[misc]
            self.godot_status.setText(self.tr("Godot {0} found at {1}").format(version, exe))
            self.godot_status.setProperty("state", "ok")
            self.download_button.setVisible(False)
        else:
            self.godot_status.setText(
                self.tr("Godot {0} not found").format(godot_target.MAJOR_MINOR)
            )
            self.godot_status.setProperty("state", "error")
            self.download_button.setVisible(True)
        self.godot_status.style().unpolish(self.godot_status)
        self.godot_status.style().polish(self.godot_status)
