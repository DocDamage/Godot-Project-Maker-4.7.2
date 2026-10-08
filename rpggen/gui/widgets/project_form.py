"""The widgets of the Project page: the four fields, their status lines and the sample button.
The page wires them; ``rpggen.gui.models.project_model`` decides what they show."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import godot_fetch
from rpggen.gui.models.forms import FieldStatus
from rpggen.gui.models.project_model import NAME_MAX
from rpggen.gui.widgets.pack_list import PackList

ZERO_WIDTH_SPACE = chr(0x200B)  # a line-break chance that shows nothing


def breakable(text: str) -> str:
    """``text`` with a line-break chance after each path separator: a word-wrapped label only
    breaks at spaces, so a long path would otherwise set the width of the window."""
    return text.replace("\\", "\\" + ZERO_WIDTH_SPACE).replace("/", "/" + ZERO_WIDTH_SPACE)


def show_status(label: QLabel, status: FieldStatus) -> None:
    label.setText(breakable(status.text))
    label.setToolTip(status.text if len(status.text) > 80 else "")
    label.setProperty("state", status.state)
    label.style().unpolish(label)
    label.style().polish(label)


def _status_label(name: str) -> QLabel:
    label = QLabel()
    label.setObjectName(name)
    label.setWordWrap(True)
    # a wrapped label's own minimum is a guess at a pleasant shape, wide for a long message: let
    # the form decide the width, and the label wraps to it
    label.setMinimumWidth(1)
    return label


def _button(text: str, name: str, tooltip: str = "") -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def _row(*widgets: QWidget, stretch_first: bool = True) -> QHBoxLayout:
    """The first widget stretches; or, with ``stretch_first`` off, the space after the last."""
    row = QHBoxLayout()
    for i, widget in enumerate(widgets):
        row.addWidget(widget, 1 if i == 0 and stretch_first else 0)
    if not stretch_first:
        row.addStretch(1)
    return row


def _field(form: QFormLayout, label: str, *rows: QWidget | QHBoxLayout) -> None:
    box = QVBoxLayout()
    for row in rows:
        if isinstance(row, QHBoxLayout):
            box.addLayout(row)
        else:
            box.addWidget(row)
    form.addRow(label, box)


class ProjectForm(QWidget):
    """Asset packs, output folder, Godot executable, project name, and "Try with sample pack"."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        layout.addLayout(form)

        self.pack_list = PackList()
        self.pack_list.setToolTip(self.tr("The asset packs: drop folders or archives here"))
        self.add_zip_button = _button(self.tr("Add Zip/7z…"), "addZipButton")
        self.add_folder_button = _button(self.tr("Add Folder…"), "addFolderButton")
        self.remove_button = _button(self.tr("Remove"), "removePackButton")
        self.update_pack_button = _button(
            self.tr("Update pack…"),
            "updatePackButton",
            self.tr("Replace a pack of this project with a newer release of it."),
        )
        self.update_pack_button.setVisible(False)
        self.packs_status = _status_label("packsStatus")
        buttons = (
            self.add_zip_button,
            self.add_folder_button,
            self.remove_button,
            self.update_pack_button,
        )
        _field(
            form,
            self.tr("Asset packs"),
            self.pack_list,
            _row(*buttons, stretch_first=False),
            self.packs_status,
        )

        self.target_edit = QLineEdit()
        self.target_edit.setObjectName("targetEdit")
        self.target_edit.setToolTip(self.tr("The folder the Godot project is created in"))
        self.browse_target_button = _button(self.tr("Browse…"), "browseTargetButton")
        self.target_status = _status_label("targetStatus")
        _field(
            form,
            self.tr("Output folder"),
            _row(self.target_edit, self.browse_target_button),
            self.target_status,
        )

        self.godot_combo = QComboBox()
        self.godot_combo.setObjectName("godotCombo")
        self.godot_combo.setToolTip(self.tr("The Godot program rpggen uses to build the project"))
        self.godot_combo.setEditable(True)
        # a long path scrolls in the field; it must not set the width of the window
        self.godot_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.godot_combo.setMinimumContentsLength(24)
        self.browse_godot_button = _button(self.tr("Browse…"), "browseGodotButton")
        self.godot_status = _status_label("godotStatus")
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
        )
        self.download_godot_button.setVisible(False)
        _field(
            form,
            self.tr("Godot executable"),
            _row(self.godot_combo, self.browse_godot_button),
            self.godot_status,
            _row(self.download_godot_button, stretch_first=False),
        )

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setToolTip(self.tr("The name of the game (also the window title)"))
        self.name_edit.setMaxLength(NAME_MAX * 2)  # longer text is reported, not silently cut
        self.name_status = _status_label("nameStatus")
        _field(form, self.tr("Project name"), self.name_edit, self.name_status)

        layout.addStretch(1)
        self.sample_button = _button(
            self.tr("Try with sample pack"),
            "trySampleButton",
            self.tr("Fill in the bundled sample pack and go straight to the options."),
        )
        self.sample_row = _row(self.sample_button, stretch_first=False)
        layout.addLayout(self.sample_row)
