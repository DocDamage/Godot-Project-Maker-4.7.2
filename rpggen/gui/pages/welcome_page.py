"""The welcome view shown before page 1: three big choices, recent projects and a Godot check.

It is not a numbered wizard step; the window hides the sidebar and the button bar while it shows.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import godot_target
from rpggen.core import app_settings
from rpggen.gui import workers


class WelcomePage(QWidget):
    """Emits what the user chose; the window does the navigation."""

    AVAILABLE_TIMEOUT_S = 2.0  # how long one folder may take to answer

    trySampleRequested = Signal()
    ownPackRequested = Signal()
    openProjectRequested = Signal()  # ask for a folder
    recentChosen = Signal(str)  # a recent project's folder
    downloadGodotRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomePage")
        self._godot_generation = 0
        self._available_generation = 0
        self._available_worker: workers.Worker | None = None
        self.unavailable: set[str] = set()  # recent projects whose folder cannot be reached
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
        layout.addSpacing(12)

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
        recent_buttons = QHBoxLayout()
        self.locate_button = QPushButton(self.tr("Locate…"))
        self.locate_button.setObjectName("recentLocate")
        self.locate_button.setToolTip(
            self.tr("Point a project that moved (or whose drive has another letter) at its folder")
        )
        self.remove_button = QPushButton(self.tr("Remove"))
        self.remove_button.setObjectName("recentRemove")
        self.remove_button.setToolTip(
            self.tr("Take the project off this list (nothing is deleted)")
        )
        recent_buttons.addWidget(self.locate_button)
        recent_buttons.addWidget(self.remove_button)
        recent_buttons.addStretch(1)
        layout.addLayout(recent_buttons)
        self.locate_button.clicked.connect(self.locate_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        self.recent_list.currentItemChanged.connect(lambda *_: self._sync_recent_buttons())
        layout.addStretch(1)

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

    def _card(
        self, name: str, title: str, text: str, signal: SignalInstance, tip: str
    ) -> QToolButton:
        card = QToolButton()
        card.setObjectName(name)
        card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        card.setToolTip(tip)
        card.setAccessibleName(title)
        card.setMinimumHeight(130)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.clicked.connect(signal)
        inner = QVBoxLayout(card)  # labels, so that the text wraps instead of being cut off
        inner.setContentsMargins(16, 14, 16, 14)
        heading = QLabel(f"<b style='font-size:15px'>{title}</b>")
        body = QLabel(text)
        body.setWordWrap(True)
        for label in (heading, body):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        inner.addWidget(heading)
        inner.addWidget(body)
        inner.addStretch(1)
        return card

    # ------------------------------------------------------------------ content

    def refresh(self) -> None:
        """Reload the recent projects and look for Godot again."""
        self._fill_recent()
        self.check_godot()

    def _fill_recent(self) -> None:
        """List every recent project at once (no folder is touched here); whether each one can be
        reached is found out in a worker and shown when it is known."""
        self.recent_list.clear()
        recent = app_settings.get().recent_projects
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
        self.locate_button.setVisible(bool(recent))
        self.remove_button.setVisible(bool(recent))
        self._sync_recent_buttons()
        if recent:
            self._check_available([p.target for p in recent])

    def _check_available(self, targets: list[str]) -> None:
        self._available_generation += 1
        generation = self._available_generation

        def job(*, callbacks) -> dict[str, bool]:  # noqa: ANN001
            return app_settings.available(targets, timeout_s=self.AVAILABLE_TIMEOUT_S)

        worker = workers.Worker(job)
        worker.signals.finished.connect(
            lambda result: (
                self.show_available(result) if generation == self._available_generation else None
            )
        )
        self._available_worker = worker  # keep it alive until its signal is delivered
        worker.start()

    def show_available(self, result: dict[str, bool]) -> None:
        """Grey out the projects whose folder cannot be reached (they stay in the list)."""
        try:
            self.recent_list.objectName()
        except RuntimeError:
            return  # the window was closed while the worker ran
        self.unavailable = {target for target, ok in result.items() if not ok}
        for i in range(self.recent_list.count()):
            item = self.recent_list.item(i)
            target = item.data(Qt.ItemDataRole.UserRole)
            missing = target in self.unavailable
            item.setData(Qt.ItemDataRole.UserRole + 1, missing)
            item.setForeground(
                self.palette().color(
                    self.palette().ColorGroup.Disabled, self.palette().ColorRole.Text
                )
                if missing
                else self.palette().color(self.palette().ColorRole.Text)
            )
            item.setToolTip(
                self.tr(
                    "This folder cannot be reached now (an unplugged drive or share?). "
                    "Plug it in, or use Locate…"
                )
                if missing
                else ""
            )
        self._sync_recent_buttons()

    def _sync_recent_buttons(self) -> None:
        item = self.recent_list.currentItem()
        selected = item is not None
        missing = selected and bool(item.data(Qt.ItemDataRole.UserRole + 1))
        self.remove_button.setEnabled(selected)
        self.locate_button.setEnabled(missing)

    def ask_folder(self, start: str) -> str:  # overridden by tests
        from PySide6.QtWidgets import QFileDialog

        return QFileDialog.getExistingDirectory(self, self.tr("Where is the project now?"), start)

    def locate_selected(self) -> bool:
        """Point the selected (unreachable) project at the folder where it is now."""
        item = self.recent_list.currentItem()
        if item is None:
            return False
        old = item.data(Qt.ItemDataRole.UserRole)
        new = self.ask_folder(str(Path(old).parent))
        if not new or str(Path(new)) == str(Path(old)):
            return False

        def move(settings: app_settings.AppSettings) -> None:
            for project in settings.recent_projects:
                if project.target == old:
                    project.target = str(Path(new))
                    project.last_opened = datetime.now().isoformat(timespec="seconds")

        app_settings.store().update(move)
        self._fill_recent()
        return True

    def remove_selected(self) -> bool:
        """Take the selected project off the list (the folder is not touched)."""
        item = self.recent_list.currentItem()
        if item is None:
            return False
        old = item.data(Qt.ItemDataRole.UserRole)

        def drop(settings: app_settings.AppSettings) -> None:
            settings.recent_projects = [p for p in settings.recent_projects if p.target != old]

        app_settings.store().update(drop)
        self._fill_recent()
        return True

    def recent_targets(self) -> list[str]:
        return [
            self.recent_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.recent_list.count())
        ]

    def _on_recent_activated(self, item: QListWidgetItem) -> None:
        if item.data(Qt.ItemDataRole.UserRole + 1):  # known to be unreachable: Locate… instead
            return
        self.recentChosen.emit(item.data(Qt.ItemDataRole.UserRole))

    def check_godot(self) -> None:
        """Find a usable Godot in a worker (it launches Godot to read the version)."""
        self._godot_generation += 1
        generation = self._godot_generation
        self.godot_status.setText(self.tr("Looking for Godot…"))
        worker = workers.Worker(workers.find_working_godot)

        def done(found: tuple[Path, str] | None) -> None:
            if generation == self._godot_generation:
                self.show_godot(found)

        def failed(_error: object) -> None:
            if generation == self._godot_generation:
                self.show_godot(None)

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._worker = worker  # keep it alive until its signals are delivered
        worker.start()

    def show_godot(self, found: tuple[Path, str] | None) -> None:
        try:
            self.godot_status.objectName()
        except RuntimeError:
            return  # the window was closed while the worker ran
        if found:
            exe, version = found
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
