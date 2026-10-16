"""Edit > Local vision model…: the optional vision step of the analysis (T17.34).

Off by default. When on, the analysis asks a vision model running on this computer what the
pictures it cannot decide show (llama-server with a multimodal model and its vision projector,
which the user already has: rpggen downloads nothing). Pictures never leave the computer.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import app_settings
from rpggen.core.vision.llama import LlamaConfig

FIELDS = (
    ("vision_server", "llama-server program"),
    ("vision_model", "Model (.gguf)"),
    ("vision_projector", "Vision projector (mmproj .gguf)"),
)


class VisionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("visionDialog")
        self.setWindowTitle(self.tr("Local vision model"))
        settings = app_settings.get()
        layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr(
                "For pictures that their names and pixels leave undecided, the analysis can ask "
                "a vision model running on this computer what they show. Pictures never leave "
                "the computer. Its answers are used only where they were measured to be right "
                "more often than rpggen's own reading."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.enabled_box = QCheckBox(self.tr("Use the local vision model"))
        self.enabled_box.setObjectName("visionEnabled")
        self.enabled_box.setChecked(settings.vision_enabled)
        layout.addWidget(self.enabled_box)
        grid = QGridLayout()
        self.edits: dict[str, QLineEdit] = {}
        for row, (key, label) in enumerate(FIELDS):
            grid.addWidget(QLabel(self.tr(label)), row, 0)
            edit = QLineEdit(str(getattr(settings, key)))
            edit.setObjectName(key)
            edit.textChanged.connect(self.update_state)
            self.edits[key] = edit
            browse = QPushButton(self.tr("Browse…"))
            browse.clicked.connect(lambda _checked=False, k=key: self.browse(k))
            row_box = QHBoxLayout()
            row_box.addWidget(edit, 1)
            row_box.addWidget(browse)
            grid.addLayout(row_box, row, 1)
        grid.addWidget(QLabel(self.tr("Port")), len(FIELDS), 0)
        self.port_box = QSpinBox()
        self.port_box.setObjectName("visionPort")
        self.port_box.setRange(1024, 65535)
        self.port_box.setValue(settings.vision_port)
        grid.addWidget(self.port_box, len(FIELDS), 1)
        layout.addLayout(grid)
        self.state_label = QLabel()
        self.state_label.setObjectName("visionState")
        self.state_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        buttons = QDialogButtonBox.StandardButton
        box = QDialogButtonBox(buttons.Save | buttons.Cancel)
        box.accepted.connect(self.save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.enabled_box.toggled.connect(self.update_state)
        self.update_state()

    def config(self) -> LlamaConfig:
        return LlamaConfig(
            server=Path(self.edits["vision_server"].text().strip()),
            model=Path(self.edits["vision_model"].text().strip()),
            projector=Path(self.edits["vision_projector"].text().strip()),
            port=self.port_box.value(),
        )

    def update_state(self) -> None:
        if not self.enabled_box.isChecked():
            self.state_label.setText(self.tr("Off: nothing is started and nothing is sent."))
            return
        missing = [k for k, edit in self.edits.items() if not Path(edit.text().strip()).is_file()]
        if missing:
            names = ", ".join(self.tr(label) for key, label in FIELDS if key in missing)
            self.state_label.setText(
                self.tr("Not found: {0}. The analysis skips the step until they are.").format(names)
            )
        else:
            self.state_label.setText(self.tr("Ready: the files are there."))

    def browse(self, key: str) -> None:  # overridden by tests
        start = self.edits[key].text().strip() or str(Path.home())
        found, _ = QFileDialog.getOpenFileName(self, self.tr("Choose a file"), start)
        if found:
            self.edits[key].setText(found)

    def save(self) -> None:
        app_settings.update(
            vision_enabled=self.enabled_box.isChecked(),
            vision_server=self.edits["vision_server"].text().strip(),
            vision_model=self.edits["vision_model"].text().strip(),
            vision_projector=self.edits["vision_projector"].text().strip(),
            vision_port=self.port_box.value(),
        )
        self.accept()
