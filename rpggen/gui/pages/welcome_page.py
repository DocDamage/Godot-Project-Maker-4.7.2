"""The welcome view shown before page 1: three big choices, recent projects and a Godot check.

It is not a numbered wizard step; the window hides the sidebar and the button bar while it shows.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import features, godot_target
from rpggen.core import app_settings, pack_sniff
from rpggen.gui import workers

PICTURE = "rpggen/results/starter_map.png"  # the starter map as it was built (T11.27)
PICTURE_SIZE = QSize(112, 70)
ARCHETYPE_WORDS = {"turn_based": "turn-based", "arpg": "action"}


def pack_changes(project: app_settings.RecentProject) -> list[tuple[str, datetime]]:
    """``(pack file or folder name, when it changed)`` for the packs of a project that are not
    as they were when it was generated. It touches the disk: call it from a worker."""
    out: list[tuple[str, datetime]] = []
    for pack in project.packs:
        when = pack_sniff.changed_since(pack["path"], pack.get("stamp", ""))
        if when is not None:
            out.append((Path(pack["path"]).name, when))
    return out


class ProjectCard(QFrame):
    """One recent project (T13.08): the picture of its starter map (or, for a project without
    one, a drawing of its kind of game), its name, kind, the date of the last generation, its
    packs and its folder; a line and a Regenerate button when a pack changed since; and, for a
    folder that is gone, a line saying so and Remove from the list."""

    regenerateRequested = Signal(str)  # noqa: N815 - the project's folder
    removeRequested = Signal(str)  # noqa: N815

    def __init__(self, project: app_settings.RecentProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.target = project.target
        self.setObjectName("projectCard")
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(1)
        self.picture = QLabel()
        self.picture.setObjectName("cardPicture")
        self.picture.setFixedSize(PICTURE_SIZE)
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.has_map_picture = False
        grid.addWidget(self.picture, 0, 0, 4, 1)
        name = project.name or Path(project.target).name
        kind = self.tr(ARCHETYPE_WORDS.get(project.archetype, project.archetype))
        self.title_label = QLabel(f"<b>{name}</b>  ·  {kind}" if kind else f"<b>{name}</b>")
        self.title_label.setObjectName("cardTitle")
        when = ""
        with contextlib.suppress(ValueError):
            when = datetime.fromisoformat(project.last_opened).strftime("%Y-%m-%d %H:%M")
        packs = ", ".join(Path(p["path"]).name for p in project.packs)
        details = [self.tr("Last generated {0}").format(when)] if when else []
        if packs:
            details.append(self.tr("packs: {0}").format(packs))
        self.details_label = QLabel("  ·  ".join(details))
        self.details_label.setObjectName("cardDetails")
        self.folder_label = QLabel(project.target)
        self.folder_label.setObjectName("cardFolder")
        self.folder_label.setProperty("muted", True)
        self.note_label = QLabel()
        self.note_label.setObjectName("cardNote")
        self.note_label.setProperty("state", "warning")
        self.note_label.setVisible(False)
        for row, label in enumerate(
            (self.title_label, self.details_label, self.folder_label, self.note_label)
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            grid.addWidget(label, row, 1)
        grid.setColumnStretch(1, 1)
        self.regenerate_button = QPushButton(self.tr("Regenerate"))
        self.regenerate_button.setObjectName("cardRegenerate")
        self.regenerate_button.setToolTip(
            self.tr("Open the project and go to Generate: you see the changes before they happen")
        )
        self.regenerate_button.setVisible(False)
        self.regenerate_button.clicked.connect(lambda: self.regenerateRequested.emit(self.target))
        self.remove_button = QPushButton(self.tr("Remove from the list"))
        self.remove_button.setObjectName("cardRemove")
        self.remove_button.setToolTip(
            self.tr("Take the project off this list (nothing is deleted)")
        )
        self.remove_button.setVisible(False)
        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self.target))
        grid.addWidget(self.regenerate_button, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.remove_button, 2, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        self.missing = False
        self.changed: list[tuple[str, datetime]] = []
        self.show_drawing()
        self.setAccessibleName(f"{name}, {kind}, {project.target}")

    def show_drawing(self) -> None:
        """No picture of the map (a project from 1.0 without one, a folder that is away): a
        drawing of the kind of game, as on the Archetype page."""
        from rpggen.gui.pages.archetype_page import MockScreen

        screen = MockScreen(self.project.archetype or "turn_based")
        screen.resize(PICTURE_SIZE.width() * 2, PICTURE_SIZE.height() * 2)
        self.picture.setPixmap(
            screen.grab().scaled(
                PICTURE_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        screen.deleteLater()
        self.has_map_picture = False

    def load_picture(self) -> bool:
        """The starter map's picture from the project folder (which was found to be there)."""
        pixmap = QPixmap(str(Path(self.target) / PICTURE))
        if pixmap.isNull():
            return False
        self.picture.setPixmap(
            pixmap.scaled(
                PICTURE_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        self.has_map_picture = True
        return True

    def set_missing(self, missing: bool) -> None:
        self.missing = missing
        self._show_note()

    def set_changed(self, changed: list[tuple[str, datetime]]) -> None:
        self.changed = list(changed)
        self._show_note()

    def _show_note(self) -> None:
        text = ""
        if self.missing:
            text = self.tr("This folder cannot be reached now (an unplugged drive or share?).")
        elif self.changed:
            name, when = self.changed[0]
            text = self.tr("{0} changed on {1}").format(name, f"{when.day} {when:%b}")
            if len(self.changed) > 1:
                text += self.tr(" (and {0} more)").format(len(self.changed) - 1)
        self.note_label.setText(text)
        self.note_label.setVisible(bool(text))
        self.regenerate_button.setVisible(bool(self.changed) and not self.missing)
        self.remove_button.setVisible(self.missing)
        for label in (self.title_label, self.details_label, self.folder_label):
            label.setEnabled(not self.missing)


class WelcomePage(QWidget):
    """Emits what the user chose; the window does the navigation."""

    AVAILABLE_TIMEOUT_S = 2.0  # how long one folder may take to answer

    trySampleRequested = Signal()
    trySideSampleRequested = Signal()  # the side-view sample, as a metroidvania (T14.09)
    ownPackRequested = Signal()
    openProjectRequested = Signal()  # ask for a folder
    recentChosen = Signal(str)  # a recent project's folder
    regenerateRequested = Signal(str)  # a card's Regenerate: open it and go to Generate
    downloadGodotRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomePage")
        self._godot_generation = 0
        self._available_generation = 0
        self._available_worker: workers.Worker | None = None
        self.unavailable: set[str] = set()  # recent projects whose folder cannot be reached
        self.cards: dict[str, ProjectCard] = {}  # folder -> its card in the list
        self.cards_checked = False
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
        self._add_sample_choices()
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
        layout.addWidget(self.recent_list, 5)  # the cards get most of the spare height
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

    def _add_sample_choices(self) -> None:
        """Make *Try the sample* a split button (T14.09): a click is the top-down village, as
        before, and the arrow lists both samples. While the metroidvania is not available the
        card stays the plain button of 1.1."""
        self.sample_menu: QMenu | None = None
        self.sample_top_action: QAction | None = None
        self.sample_side_action: QAction | None = None
        if not features.METROIDVANIA_AVAILABLE:
            return
        menu = QMenu(self.sample_card)
        menu.setObjectName("sampleMenu")
        self.sample_top_action = menu.addAction(self.tr("Top-down village"))
        self.sample_top_action.setObjectName("sampleTopDown")
        self.sample_top_action.setToolTip(self.tr("A turn-based RPG from the village pack"))
        self.sample_top_action.triggered.connect(self.trySampleRequested)
        self.sample_side_action = menu.addAction(self.tr("Side-view cave"))
        self.sample_side_action.setObjectName("sampleSideView")
        self.sample_side_action.setToolTip(self.tr("A metroidvania from the cave pack"))
        self.sample_side_action.triggered.connect(self.trySideSampleRequested)
        menu.setToolTipsVisible(True)
        self.sample_menu = menu
        self.sample_card.setMenu(menu)
        self.sample_card.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.sample_card.setToolTip(
            self.tr(
                "Fills in the bundled sample pack and goes straight to the options. "
                "The arrow offers the side-view sample too"
            )
        )

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
        self.cards = {}
        self.cards_checked = False  # the worker has not said yet what is there and what changed
        recent = app_settings.get().recent_projects
        for project in recent:
            card = ProjectCard(project)
            card.regenerateRequested.connect(self.regenerateRequested)
            card.removeRequested.connect(self.remove_target)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, project.target)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, card.accessibleName())
            item.setSizeHint(card.sizeHint())
            self.recent_list.addItem(item)
            self.recent_list.setItemWidget(item, card)
            self.cards[project.target] = card
        self.recent_label.setVisible(bool(recent))
        self.recent_list.setVisible(bool(recent))
        self.locate_button.setVisible(bool(recent))
        self.remove_button.setVisible(bool(recent))
        self._sync_recent_buttons()
        if recent:
            self._check_available(list(recent))

    def _check_available(self, projects: list[app_settings.RecentProject]) -> None:
        """In a worker: which folders can be reached, and which packs changed since."""
        self._available_generation += 1
        generation = self._available_generation
        targets = [p.target for p in projects]

        def job(*, callbacks) -> tuple[dict[str, bool], dict[str, list]]:  # noqa: ANN001
            reachable = app_settings.available(targets, timeout_s=self.AVAILABLE_TIMEOUT_S)
            changes = {p.target: pack_changes(p) for p in projects if reachable.get(p.target)}
            return reachable, changes

        def done(result: tuple[dict[str, bool], dict[str, list]]) -> None:
            if generation == self._available_generation:
                self.show_available(result[0])
                self.show_changed(result[1])
                self.cards_checked = True

        worker = workers.Worker(job)
        worker.signals.finished.connect(done)
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
            card = self.cards.get(target)
            if card is not None:
                card.set_missing(missing)
                if not missing and target in result:
                    card.load_picture()  # the folder answered: reading it will not hang
                item.setSizeHint(card.sizeHint())
        self._sync_recent_buttons()

    def show_changed(self, changes: dict[str, list]) -> None:
        """A pack that is not as it was when the project was generated: the card says which one
        and offers Regenerate."""
        for i in range(self.recent_list.count()):
            item = self.recent_list.item(i)
            card = self.cards.get(item.data(Qt.ItemDataRole.UserRole))
            if card is not None:
                card.set_changed(changes.get(card.target, []))
                item.setSizeHint(card.sizeHint())

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
        return self.remove_target(item.data(Qt.ItemDataRole.UserRole))

    def remove_target(self, old: str) -> bool:
        """Take a project off the list (a card's Remove from the list; nothing is deleted)."""

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
