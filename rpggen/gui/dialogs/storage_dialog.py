"""Edit > Storage…: what rpggen keeps on the disk, how big it is and what can be cleared."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import paths
from rpggen.core import app_settings, cache_policy
from rpggen.gui import workers

CACHE_LABELS = {
    "extracted": "Extracted packs",
    "analysis": "Analysis results",
    "inventories": "File lists of packs",
    "thumbs": "Thumbnails",
    "gif_strips": "Animation strips made from GIFs",
    "frame_strips": "Animation strips made from numbered frames",
    "terrain_atlases": "Terrain sheets",
}
DATA_LABELS = {
    "drafts": "Drafts of unfinished audits",
    "profiles": "Installed pack profiles",
    "godot": "Downloaded Godot",
    "logs": "Logs",
}


def format_size(count: int) -> str:
    """12 KB, 340 MB or 1.2 GB."""
    if count >= 1 << 30:
        return f"{count / (1 << 30):.1f} GB"
    if count >= 1 << 20:
        return f"{count / (1 << 20):.0f} MB"
    if count >= 1 << 10:
        return f"{count / (1 << 10):.0f} KB"
    return f"{count} B"


class StorageDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("storageDialog")
        self.setWindowTitle(self.tr("Storage"))
        self.resize(560, 460)
        self.size_labels: dict[str, QLabel] = {}
        self.clear_buttons: dict[str, QPushButton] = {}
        self._worker: workers.Worker | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(self._group("cache", CACHE_LABELS, paths.cache_dir()))
        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel(self.tr("Keep at most")))
        self.limit_box = QDoubleSpinBox()
        self.limit_box.setObjectName("cacheLimit")
        self.limit_box.setRange(1, 1000)
        self.limit_box.setDecimals(0)
        self.limit_box.setSuffix(" GB")
        self.limit_box.setValue(app_settings.get().cache_limit_gb)
        self.limit_box.setToolTip(
            self.tr("Extracted packs beyond this size are removed, least recently used first")
        )
        limit_row.addWidget(self.limit_box)
        limit_row.addWidget(QLabel(self.tr("of extracted packs")))
        limit_row.addStretch(1)
        layout.addLayout(limit_row)
        self.keep_failed_box = QCheckBox(self.tr("Keep the whole folder of a failed run"))
        self.keep_failed_box.setObjectName("keepFailedRuns")
        self.keep_failed_box.setToolTip(
            self.tr(
                "Without it a failed run keeps its logs and results but not a copy of your "
                "pack art and Godot's import cache (they can be several GB)"
            )
        )
        self.keep_failed_box.setChecked(app_settings.get().keep_full_failed_runs)
        self.keep_failed_box.toggled.connect(
            lambda on: app_settings.update(keep_full_failed_runs=bool(on))
        )
        layout.addWidget(self.keep_failed_box)
        layout.addWidget(self._group("data", DATA_LABELS, paths.data_dir()))
        self.total_label = QLabel()
        self.total_label.setObjectName("storageTotal")
        layout.addWidget(self.total_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.config_button = QPushButton(self.tr("Open settings folder"))
        self.config_button.setObjectName("openConfigFolder")
        self.config_button.clicked.connect(lambda: self.open_path(paths.config_dir()))
        buttons.addButton(self.config_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.limit_box.editingFinished.connect(self._save_limit)
        self.refresh()

    # ------------------------------------------------------------------ building

    def _group(self, kind: str, labels: dict[str, str], folder: Path) -> QGroupBox:
        title = (
            self.tr("Cache: can be made again")
            if kind == "cache"
            else self.tr("Your data: the program cannot make this again")
        )
        box = QGroupBox(title)
        box.setObjectName(f"{kind}Group")
        grid = QGridLayout(box)
        for row, (name, label) in enumerate(labels.items()):
            grid.addWidget(QLabel(self.tr(label)), row, 0)
            size = QLabel("…")
            size.setObjectName(f"size_{name}")
            size.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.size_labels[name] = size
            grid.addWidget(size, row, 1)
            button = QPushButton(self.tr("Clear"))
            button.setObjectName(f"clear_{name}")
            button.setToolTip(self.tr("Delete this"))
            button.clicked.connect(lambda _=False, n=name: self.clear(n))
            self.clear_buttons[name] = button
            grid.addWidget(button, row, 2)
        grid.setColumnStretch(0, 1)
        where = QPushButton(self.tr("Open folder"))
        where.setObjectName(f"open_{kind}")
        where.setToolTip(str(folder))
        where.clicked.connect(lambda: self.open_path(folder))
        grid.addWidget(where, len(labels), 2)
        return box

    # ------------------------------------------------------------------ hooks for tests

    def open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def confirm_clear_data(self, name: str) -> bool:
        answer = QMessageBox.question(
            self,
            self.tr("Delete your data?"),
            self.tr("This deletes {0}. It cannot be undone. Continue?").format(
                cache_policy.DATA_LOSSES[name]
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------ sizes

    def refresh(self) -> None:
        """Measure every folder in a worker (a pack cache can hold many thousands of files)."""
        worker = workers.Worker(lambda *, callbacks: cache_policy.category_sizes())
        worker.signals.finished.connect(self.show_sizes)
        self._worker = worker
        worker.start()

    def show_sizes(self, sizes: dict[str, int]) -> None:
        for name, label in self.size_labels.items():
            label.setText(format_size(sizes.get(name, 0)))
            self.clear_buttons[name].setEnabled(sizes.get(name, 0) > 0)
        cache = sum(sizes.get(n, 0) for n in cache_policy.CACHE_ITEMS)
        data = sum(sizes.get(n, 0) for n in cache_policy.DATA_ITEMS)
        self.total_label.setText(
            self.tr("Cache {0} · your data {1}").format(format_size(cache), format_size(data))
        )

    # ------------------------------------------------------------------ actions

    def clear(self, name: str) -> bool:
        """Clear one category; your data is cleared only after a confirmation."""
        if name in cache_policy.DATA_ITEMS and not self.confirm_clear_data(name):
            return False
        cache_policy.clear(name)
        self.refresh()
        return True

    def _save_limit(self) -> None:
        app_settings.update(cache_limit_gb=float(self.limit_box.value()))
