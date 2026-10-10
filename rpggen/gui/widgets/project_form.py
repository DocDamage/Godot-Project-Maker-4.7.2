"""The widgets of the Project page: the four fields, their status lines and the sample button.
The page wires them; ``rpggen.gui.models.project_model`` decides what they show."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import godot_fetch
from rpggen.gui import icons, theme
from rpggen.gui.models.forms import FieldStatus
from rpggen.gui.models.project_model import NAME_MAX
from rpggen.gui.widgets import buttons
from rpggen.gui.widgets.card import Card
from rpggen.gui.widgets.pack_list import PackCardDelegate, PackList

LABEL_WIDTH = 140  # the label column of the Project card
DROP_ZONE_HEIGHT = 96
CARD_SPACING = 6  # between the rows of a card: two packs fit the smallest window
LIST_FRAME = 4  # the list's own border, above and below its cards
CARDS_SHOWN = 3  # the pack list grows to this many cards, then it scrolls

ZERO_WIDTH_SPACE = chr(0x200B)  # a line-break chance that shows nothing


def breakable(text: str) -> str:
    """``text`` with a line-break chance after each path separator: a word-wrapped label only
    breaks at spaces, so a long path would otherwise set the width of the window."""
    return text.replace("\\", "\\" + ZERO_WIDTH_SPACE).replace("/", "/" + ZERO_WIDTH_SPACE)


def show_status(label: QLabel, status: FieldStatus) -> None:
    """A field's line. It is shown for what is wrong and what the user should know (an error,
    a warning, "Checking…"). A hint is the field's placeholder instead, and "… is fine" is not
    said in words: the page fits the smallest window that way (T15.11). The label keeps the
    text and the state either way."""
    label.setText(breakable(status.text))
    label.setToolTip(status.text if len(status.text) > 80 else "")
    label.setProperty("state", status.state)
    label.setVisible(bool(status.text) and status.state not in ("hint", "ok"))
    label.style().unpolish(label)
    label.style().polish(label)


def _status_label(name: str) -> QLabel:
    label = QLabel()
    label.setObjectName(name)
    label.setWordWrap(True)
    # a wrapped label's own minimum is a guess at a pleasant shape, wide for a long message: let
    # the form decide the width, and the label wraps to it
    label.setMinimumWidth(1)
    label.setVisible(False)
    return label


def _button(text: str, name: str, tooltip: str = "", icon_name: str = "") -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    if tooltip:
        button.setToolTip(tooltip)
    if icon_name:
        icons.set_icon(button, icon_name)
    return button


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFixedWidth(LABEL_WIDTH)
    return label


class DropZone(QFrame):
    """What the pack list is while it is empty: a dashed box that takes dropped folders and
    archives and holds the buttons that add one."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setFixedHeight(DROP_ZONE_HEIGHT)
        self.on_paths_dropped: Callable[[list[Path]], None] = lambda paths: None
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(theme.px("space_16"), 0, theme.px("space_16"), 0)
        self.row.setSpacing(theme.px("space_8"))
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(QSize(24, 24))
        self.text_label = QLabel(text)
        self.text_label.setObjectName("dropZoneText")
        self.text_label.setProperty("muted", True)
        self.row.addWidget(self.icon_label)
        self.row.addWidget(self.text_label)
        self.row.addStretch(1)
        self._redraw()
        theme.signals.changed.connect(self._redraw)

    def _redraw(self, *_args: object) -> None:
        with contextlib.suppress(RuntimeError):
            self.icon_label.setPixmap(icons.pixmap("file-archive", "text_muted", 24))

    def _set_dragging(self, on: bool) -> None:
        self.setProperty("dragOver", on)
        theme.repolish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt override
        if event.mimeData().hasUrls():
            self._set_dragging(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802
        self._set_dragging(False)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt override
        self._set_dragging(False)
        dropped = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if dropped:
            self.on_paths_dropped(dropped)
            event.acceptProposedAction()


class ProjectForm(QWidget):
    """Two cards (T15.11): the asset packs, and the project (output folder, Godot executable,
    project name). The page wires the widgets; the model decides what they show."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.px("space_8"))

        # ---- Asset packs
        self.packs_card = Card(margin=theme.px("space_12"))
        self.packs_card.setObjectName("packsCard")
        self.packs_card.box.setSpacing(CARD_SPACING)
        self.packs_card.add_heading(self.tr("Asset packs"))
        self.pack_list = PackList()
        self.pack_list.setToolTip(self.tr("The asset packs: drop folders or archives here"))
        self.drop_zone = DropZone(self.tr("Drop folders or archives here"))
        self.add_zip_button = _button(self.tr("Add Zip/7z…"), "addZipButton", "", "file-archive")
        self.add_folder_button = _button(self.tr("Add Folder…"), "addFolderButton", "", "folder")
        self.remove_button = _button(self.tr("Remove"), "removePackButton", "", "x")
        self.update_pack_button = _button(
            self.tr("Update pack…"),
            "updatePackButton",
            self.tr("Replace a pack of this project with a newer release of it."),
        )
        self.update_pack_button.setVisible(False)
        self.sample_button = _button(
            self.tr("Try with sample pack"),
            "trySampleButton",
            self.tr("Fill in the bundled sample pack and go straight to the options."),
        )
        buttons.set_kind(self.sample_button, buttons.QUIET)
        self.or_label = QLabel(self.tr("or"))
        self.or_label.setProperty("muted", True)
        self.packs_status = _status_label("packsStatus")
        self.pack_buttons = QHBoxLayout()  # under the list while it has packs
        self.pack_buttons.setContentsMargins(0, 0, 0, 0)
        self.pack_buttons.setSpacing(theme.px("space_8"))
        self.sample_row = self.pack_buttons  # the name the page knew the sample's row by
        self.packs_card.box.addWidget(self.drop_zone)
        self.packs_card.box.addWidget(self.pack_list)
        self.packs_card.box.addLayout(self.pack_buttons)
        self.packs_card.box.addWidget(self.packs_status)
        layout.addWidget(self.packs_card)

        # ---- Project
        self.project_card = Card(margin=theme.px("space_12"))
        self.project_card.setObjectName("projectFormCard")
        self.project_card.box.setSpacing(CARD_SPACING)
        self.project_card.add_heading(self.tr("Project"))
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.px("space_8"))
        grid.setVerticalSpacing(theme.px("space_4"))
        grid.setColumnStretch(1, 1)
        self.project_card.box.addLayout(grid)

        self.target_edit = QLineEdit()
        self.target_edit.setObjectName("targetEdit")
        self.target_edit.setToolTip(self.tr("The folder the Godot project is created in"))
        self.target_edit.setPlaceholderText(self.tr("Where the Godot project will be created"))
        self.browse_target_button = _button(
            self.tr("Browse…"), "browseTargetButton", "", "folder-open"
        )
        self.target_status = _status_label("targetStatus")
        grid.addWidget(_field_label(self.tr("Output folder")), 0, 0)
        grid.addWidget(self.target_edit, 0, 1)
        grid.addWidget(self.browse_target_button, 0, 2)
        grid.addWidget(self.target_status, 1, 1, 1, 2)

        self.godot_combo = QComboBox()
        self.godot_combo.setObjectName("godotCombo")
        self.godot_combo.setToolTip(self.tr("The Godot program rpggen uses to build the project"))
        self.godot_combo.setEditable(True)
        # a long path scrolls in the field; it must not set the width of the window
        self.godot_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.godot_combo.setMinimumContentsLength(24)
        if (godot_line := self.godot_combo.lineEdit()) is not None:
            godot_line.setPlaceholderText(self.tr("A Godot 4.7 executable"))
        self.browse_godot_button = _button(
            self.tr("Browse…"), "browseGodotButton", "", "folder-open"
        )
        self.godot_status = _status_label("godotStatus")
        self.godot_chip = QLabel()  # the version found, or that the choice cannot be used
        self.godot_chip.setObjectName("godotChip")
        self.godot_chip.setProperty("chip", True)
        self.godot_chip.setVisible(False)
        self.download_godot_button = _button(
            self.tr("Download Godot {0} (about {1} MB)").format(
                godot_fetch.DEFAULT_VERSION,
                godot_fetch.DOWNLOAD_MB[godot_fetch.current_platform()],
            ),
            "downloadGodotButton",
            self.tr(
                "Downloads the official Godot from github.com/godotengine/godot/releases into "
                "rpggen's own folder. Your other Godot versions are not touched."
            ),
            "download",
        )
        self.download_godot_button.setVisible(False)
        godot_label = QVBoxLayout()
        godot_label.setContentsMargins(0, 0, 0, 0)
        godot_label.setSpacing(2)
        godot_label.addWidget(_field_label(self.tr("Godot executable")))
        godot_label.addWidget(self.godot_chip, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addLayout(godot_label, 2, 0, 2, 1, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self.godot_combo, 2, 1)
        grid.addWidget(self.browse_godot_button, 2, 2)
        godot_under = QVBoxLayout()
        godot_under.setContentsMargins(0, 0, 0, 0)
        godot_under.setSpacing(theme.px("space_4"))
        godot_under.addWidget(self.godot_status)
        godot_under.addWidget(self.download_godot_button, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addLayout(godot_under, 3, 1, 1, 2)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setToolTip(self.tr("The name of the game (also the window title)"))
        self.name_edit.setPlaceholderText(self.tr("1 to {0} characters").format(NAME_MAX))
        self.name_edit.setMaxLength(NAME_MAX * 2)  # longer text is reported, not silently cut
        self.name_status = _status_label("nameStatus")
        grid.addWidget(_field_label(self.tr("Project name")), 4, 0)
        grid.addWidget(self.name_edit, 4, 1, 1, 2)
        grid.addWidget(self.name_status, 5, 1, 1, 2)
        layout.addWidget(self.project_card)
        layout.addStretch(1)

        self.pack_list.model().rowsInserted.connect(self._packs_changed)
        self.pack_list.model().rowsRemoved.connect(self._packs_changed)
        self.pack_list.model().modelReset.connect(self._packs_changed)
        self.sync_packs()
        for before, after in zip(self.tab_chain(), self.tab_chain()[1:], strict=False):
            QWidget.setTabOrder(before, after)

    def tab_chain(self) -> list[QWidget]:
        """The order Tab walks the page in (hidden ones are skipped by Qt)."""
        return [
            self.pack_list,
            self.add_zip_button,
            self.add_folder_button,
            self.remove_button,
            self.update_pack_button,
            self.sample_button,
            self.target_edit,
            self.browse_target_button,
            self.godot_combo,
            self.browse_godot_button,
            self.download_godot_button,
            self.name_edit,
        ]

    def _packs_changed(self, *_args: object) -> None:
        with contextlib.suppress(RuntimeError):  # the page is being closed
            self.sync_packs()

    def sync_packs(self) -> None:
        """Empty: the drop zone, with the buttons that add a pack and the sample link on its
        line. With packs: the list (as high as its cards, up to three, then it scrolls) and
        the buttons in a row under it."""
        count = self.pack_list.count()
        empty = count == 0
        for layout in (self.drop_zone.row, self.pack_buttons):
            for widget in (
                self.add_zip_button,
                self.add_folder_button,
                self.or_label,
                self.sample_button,
                self.remove_button,
                self.update_pack_button,
            ):
                layout.removeWidget(widget)
            # the stretch at the end of the row of buttons
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                if (
                    item is not None
                    and item.spacerItem() is not None
                    and layout is self.pack_buttons
                ):
                    layout.takeAt(i)
        self._update_shown = getattr(self, "_update_shown", False)
        if empty:
            for widget in (
                self.add_zip_button,
                self.add_folder_button,
                self.update_pack_button,
                self.or_label,
                self.sample_button,
            ):
                self.drop_zone.row.addWidget(widget)
        else:
            for widget in (
                self.add_zip_button,
                self.add_folder_button,
                self.remove_button,
                self.update_pack_button,
            ):
                self.pack_buttons.addWidget(widget)
            self.pack_buttons.addStretch(1)
        # a button that changes its row is shown again by Qt only on the next turn of the
        # event loop: say it now
        self.add_zip_button.setVisible(True)
        self.add_folder_button.setVisible(True)
        self.drop_zone.setVisible(empty)
        self.pack_list.setVisible(not empty)
        self.or_label.setVisible(empty)
        self.sample_button.setVisible(empty)
        self.remove_button.setVisible(not empty)
        self.update_pack_button.setVisible(self._update_shown)
        shown = max(1, min(count, CARDS_SHOWN))
        self.pack_list.setFixedHeight(shown * (PackCardDelegate.HEIGHT + 2) + LIST_FRAME)

    def show_update_button(self, on: bool) -> None:
        """*Update pack…* shows for a folder that is a project made with rpggen."""
        self._update_shown = on
        self.update_pack_button.setVisible(on)

    def packs_focus(self) -> QWidget:
        """Where the focus goes when the packs are what is missing: the list, or (it is not
        shown while it is empty) the first button that adds a pack."""
        return self.pack_list if self.pack_list.count() else self.add_zip_button

    def show_godot_chip(self, status: FieldStatus) -> None:
        """The version as a chip beside the label when the Godot is fine; that it cannot be
        used when it is not (the line under the field says why)."""
        if status.state == "ok":
            text, kind = status.text.replace("Godot ", "", 1), "success"
        elif status.state == "error":
            text, kind = self.tr("not usable"), "danger"
        else:
            text, kind = "", ""
        self.godot_chip.setText(text)
        self.godot_chip.setProperty("kind", kind)
        self.godot_chip.setVisible(bool(text))
        theme.repolish(self.godot_chip)
