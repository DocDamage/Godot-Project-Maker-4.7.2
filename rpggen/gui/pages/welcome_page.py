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
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import features, godot_target
from rpggen.core import app_settings, pack_sniff
from rpggen.gui import icons, theme, workers
from rpggen.gui.widgets import buttons
from rpggen.gui.widgets.card import INFO, SUCCESS, WARNING, Banner, Card, CardButton

PICTURE = "rpggen/results/starter_map.png"  # the starter map as it was built (T11.27)
PICTURE_SIZE = QSize(112, 70)
CARD_HEIGHT = 160  # the three choices
TWO_COLUMNS_FROM = 900  # the recent projects: two columns from this width of the view
ARCHETYPE_WORDS = {"turn_based": "turn-based", "arpg": "action", "metroidvania": "metroidvania"}


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
        self.setProperty("card", True)
        self.setProperty("interactive", True)
        grid = QGridLayout(self)
        grid.setContentsMargins(12, 8, 12, 8)
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
        buttons.set_kind(self.remove_button, buttons.QUIET)
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
    chooseGodotRequested = Signal()  # point at a Godot the user has: the Project page's Browse
    userGuideRequested = Signal()

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
        layout.setContentsMargins(
            theme.px("space_32"), theme.px("space_24"), theme.px("space_32"), theme.px("space_16")
        )
        layout.setSpacing(theme.px("space_8"))
        title = QLabel(self.tr("Welcome to rpggen"))
        title.setObjectName("welcomeTitle")
        title.setProperty("role", "display")
        layout.addWidget(title)
        subtitle = QLabel(self.tr("Turn an asset pack into a playable Godot project."))
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setProperty("muted", True)
        layout.addWidget(subtitle)
        layout.addSpacing(theme.px("space_8"))

        cards = QHBoxLayout()
        cards.setSpacing(theme.px("space_16"))
        self.sample_card = self._card(
            "sampleCard",
            "play",
            self.tr("Try the sample"),
            self.tr("See a finished project in about a minute. Nothing to configure."),
            self.trySampleRequested,
            self.tr("Fills in the bundled sample pack, generates it and shows the result"),
        )
        self._add_sample_choices()
        self.own_card = self._card(
            "ownPackCard",
            "folder-open",
            self.tr("Start with my asset pack"),
            self.tr("Add the packs you own, check what rpggen detected, then generate."),
            self.ownPackRequested,
            self.tr("Opens the first wizard page"),
        )
        self.open_card = self._card(
            "openProjectCard",
            "refresh-cw",
            self.tr("Open an existing project"),
            self.tr("Change the options of a project made with rpggen and regenerate it safely."),
            self.openProjectRequested,
            self.tr("Choose a project folder"),
        )
        for card in (self.sample_card, self.own_card, self.open_card):
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        layout.addSpacing(theme.px("space_8"))

        # the recent projects, or (while there are none) how the wizard works
        recent_head = QHBoxLayout()
        self.recent_label = QLabel(self.tr("Recent projects"))
        self.recent_label.setObjectName("recentLabel")
        self.recent_label.setProperty("role", "section")
        recent_head.addWidget(self.recent_label)
        recent_head.addStretch(1)
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
        for button in (self.locate_button, self.remove_button):
            buttons.set_kind(button, buttons.QUIET)
            recent_head.addWidget(button)
        layout.addLayout(recent_head)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentList")
        self.recent_list.setToolTip(self.tr("Double-click or press Enter to open a project"))
        self.recent_list.setFlow(QListView.Flow.LeftToRight)
        self.recent_list.setWrapping(True)
        self.recent_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setSpacing(0)
        self.recent_list.itemActivated.connect(self._on_recent_activated)
        layout.addWidget(self.recent_list, 5)  # the cards get most of the spare height
        self.locate_button.clicked.connect(self.locate_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        self.recent_list.currentItemChanged.connect(lambda *_: self._sync_recent_buttons())

        self.how_box = QWidget()
        self.how_box.setObjectName("howItWorks")
        how = QVBoxLayout(self.how_box)
        how.setContentsMargins(0, 0, 0, 0)
        how.setSpacing(theme.px("space_8"))
        how_label = QLabel(self.tr("How it works"))
        how_label.setProperty("role", "section")
        how.addWidget(how_label)
        steps = QHBoxLayout()
        steps.setSpacing(theme.px("space_16"))
        self.how_cards: list[Card] = []
        for number, (icon_name, text) in enumerate(
            (
                ("file-archive", self.tr("Add a pack you own")),
                ("search", self.tr("Check what rpggen found")),
                ("gamepad-2", self.tr("Generate and open in Godot")),
            ),
            start=1,
        ):
            step = Card()
            step.setObjectName(f"howStep{number}")
            row = QHBoxLayout()
            row.setSpacing(theme.px("space_12"))
            picture = QLabel()
            picture.setFixedSize(QSize(24, 24))
            picture.setProperty("stepIcon", icon_name)
            number_label = QLabel(str(number))
            number_label.setProperty("role", "title")
            line = QLabel(text)
            line.setWordWrap(True)
            row.addWidget(picture)
            row.addWidget(number_label)
            row.addWidget(line, 1)
            step.box.addLayout(row)
            step.setAccessibleName(self.tr("Step {0}: {1}").format(number, text))
            self.how_cards.append(step)
            steps.addWidget(step, 1)
        how.addLayout(steps)
        self.guide_button = QPushButton(self.tr("Read the user guide"))
        self.guide_button.setObjectName("welcomeGuide")
        self.guide_button.setToolTip(self.tr("Opens the user guide (F1)"))
        buttons.set_kind(self.guide_button, buttons.QUIET)
        icons.set_icon(self.guide_button, "book-open")
        self.guide_button.clicked.connect(self.userGuideRequested)
        how.addWidget(self.guide_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.how_box)
        layout.addStretch(1)

        self.godot_status = Banner(INFO, self.tr("Looking for Godot…"))
        self.godot_status.setObjectName("welcomeGodotStatus")
        self.download_button = QPushButton(
            self.tr("Download Godot {0}").format(godot_target.VERSION)
        )
        self.download_button.setObjectName("welcomeDownloadGodot")
        self.download_button.setToolTip(
            self.tr("Downloads the official Godot from github.com/godotengine/godot/releases")
        )
        buttons.set_kind(self.download_button, buttons.PRIMARY)
        self.download_button.setVisible(False)
        self.download_button.clicked.connect(self.downloadGodotRequested)
        self.choose_godot_button = QPushButton(self.tr("Choose…"))
        self.choose_godot_button.setObjectName("welcomeChooseGodot")
        self.choose_godot_button.setToolTip(
            self.tr("Point rpggen at a Godot you already have (on the Project page)")
        )
        self.choose_godot_button.setVisible(False)
        self.choose_godot_button.clicked.connect(self.chooseGodotRequested)
        self.godot_status.add_action(self.download_button)
        self.godot_status.add_action(self.choose_godot_button)
        layout.addWidget(self.godot_status)
        self._redraw_icons()
        theme.signals.changed.connect(self._redraw_icons)
        self.refresh()

    def _redraw_icons(self, *_args: object) -> None:
        try:
            for step in self.how_cards:
                for label in step.findChildren(QLabel):
                    name = label.property("stepIcon")
                    if name:
                        label.setPixmap(icons.pixmap(str(name), "accent", 24))
        except RuntimeError:  # the view was closed while a theme change was on its way
            pass

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        super().resizeEvent(event)
        self._fit_recent()

    def recent_columns(self) -> int:
        """Two columns of project cards in a wide window, one below 900 px."""
        return 2 if self.width() >= TWO_COLUMNS_FROM else 1

    def _fit_recent(self) -> None:
        columns = self.recent_columns()
        viewport = self.recent_list.viewport()
        room = (viewport.width() if viewport is not None else self.recent_list.width()) - 2
        width = max(200, room // columns)
        for i in range(self.recent_list.count()):
            item = self.recent_list.item(i)
            card = self.cards.get(item.data(Qt.ItemDataRole.UserRole))
            if card is not None:
                item.setSizeHint(QSize(width, card.sizeHint().height()))

    def _add_sample_choices(self) -> None:
        """*Choose a sample* under the sample card's description (T14.09, T15.08): a click on
        the card is the top-down village, as before, and the button lists both samples. While
        the metroidvania is not available the card has no such button."""
        self.sample_menu: QMenu | None = None
        self.sample_top_action: QAction | None = None
        self.sample_side_action: QAction | None = None
        self.sample_choose_button: QPushButton | None = None
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
        self.sample_card.set_choices(menu)
        chooser = self.sample_card.add_footer(self.tr("Choose a sample"))
        chooser.setObjectName("sampleChoose")
        chooser.setToolTip(self.tr("The top-down village or the side-view cave"))
        chooser.setMenu(menu)
        self.sample_choose_button = chooser
        self.sample_card.setToolTip(
            self.tr(
                "Fills in the bundled sample pack, generates it and shows the result. "
                "Choose a sample offers the side-view sample too"
            )
        )

    def _card(
        self, name: str, icon_name: str, title: str, text: str, signal: SignalInstance, tip: str
    ) -> CardButton:
        card = CardButton(title, text, icon_name)
        card.setObjectName(name)
        card.setToolTip(tip)
        card.setMinimumHeight(CARD_HEIGHT)
        card.clicked.connect(signal)
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
        self.how_box.setVisible(not recent)  # a first start says what to do instead
        self._fit_recent()
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
        self._fit_recent()
        self._sync_recent_buttons()

    def show_changed(self, changes: dict[str, list]) -> None:
        """A pack that is not as it was when the project was generated: the card says which one
        and offers Regenerate."""
        for i in range(self.recent_list.count()):
            item = self.recent_list.item(i)
            card = self.cards.get(item.data(Qt.ItemDataRole.UserRole))
            if card is not None:
                card.set_changed(changes.get(card.target, []))
        self._fit_recent()

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
        self.godot_status.set_kind(INFO)
        self.godot_status.set_text(self.tr("Looking for Godot…"))
        self.download_button.setVisible(False)
        self.choose_godot_button.setVisible(False)
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
            self.godot_status.set_kind(SUCCESS)
            self.godot_status.set_text(self.tr("Godot {0} found at {1}").format(version, exe))
        else:
            self.godot_status.set_kind(WARNING)
            self.godot_status.set_text(
                self.tr("Godot {0} not found").format(godot_target.MAJOR_MINOR),
                self.tr("rpggen needs it to build and check the project."),
            )
        self.download_button.setVisible(not found)
        self.choose_godot_button.setVisible(not found)
