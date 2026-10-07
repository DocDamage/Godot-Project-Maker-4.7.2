"""Help > Error codes: a searchable list of every code with its message and fix."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.errors import CODES

SEVERITY_LABEL = {"error": "Error", "warning": "Warning", "info": "Info"}


def matching(query: str) -> list[str]:
    """Codes whose id, message or fix contains every word of ``query`` (case-insensitive)."""
    words = query.lower().split()
    out = []
    for code, info in sorted(CODES.items()):
        haystack = f"{code} {info.message} {info.fix}".lower()
        if all(w in haystack for w in words):
            out.append(code)
    return out


class ErrorLookupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, initial: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("errorLookup")
        self.setWindowTitle(self.tr("Error codes"))
        self.resize(820, 520)
        layout = QVBoxLayout(self)
        self.search = QLineEdit(initial)
        self.search.setObjectName("errorSearch")
        self.search.setPlaceholderText(self.tr("Search by code or words, for example ENV-002"))
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        row = QHBoxLayout()
        self.codes = QListWidget()
        self.codes.setObjectName("errorList")
        self.codes.setMaximumWidth(260)
        row.addWidget(self.codes)
        self.detail = QLabel()
        self.detail.setObjectName("errorDetail")
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.detail, 1)
        layout.addLayout(row, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._refill)
        self.codes.currentItemChanged.connect(self._show)
        self._refill()

    def _refill(self) -> None:
        self.codes.clear()
        for code in matching(self.search.text()):
            info = CODES[code]
            item = QListWidgetItem(f"{code}  ({SEVERITY_LABEL.get(info.severity, info.severity)})")
            item.setData(Qt.ItemDataRole.UserRole, code)
            self.codes.addItem(item)
        if self.codes.count():
            self.codes.setCurrentRow(0)
        else:
            self.detail.setText(self.tr("No code matches."))

    def _show(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        info = CODES[item.data(Qt.ItemDataRole.UserRole)]
        self.detail.setText(
            f"<h3>{info.code}</h3><p><b>{SEVERITY_LABEL.get(info.severity, info.severity)}</b></p>"
            f"<p>{_escape(info.message)}</p>"
            f"<p><i>{self.tr('What to do')}:</i> {_escape(info.fix)}</p>"
        )


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
