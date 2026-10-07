"""Help > User guide: the bundled guide rendered in a QTextBrowser, opened at a section."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rpggen import paths

GUIDE_NAME = "user_guide.md"


def guide_path() -> Path:
    return paths.docs_root() / GUIDE_NAME


def guide_text() -> str:
    try:
        return guide_path().read_text(encoding="utf-8")
    except OSError:
        return "# User guide\n\nThe user guide was not found next to the program."


def headings(text: str | None = None) -> list[str]:
    """The ``## `` section titles of the guide, in order."""
    text = guide_text() if text is None else text
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def anchor_exists(anchor: str, text: str | None = None) -> bool:
    return anchor in headings(text)


class HelpViewer(QDialog):
    """The guide in a read-only browser; ``anchor`` is the title of the section to show."""

    def __init__(self, parent: QWidget | None = None, anchor: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("helpViewer")
        self.setWindowTitle(self.tr("rpggen user guide"))
        self.resize(860, 640)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setObjectName("helpBrowser")
        self.browser.setOpenLinks(False)
        self.browser.setSearchPaths([str(paths.docs_root())])
        self.browser.setMarkdown(guide_text())
        layout.addWidget(self.browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.scroll_to(anchor)

    def scroll_to(self, anchor: str) -> bool:
        """Show the section titled ``anchor``; False when the guide has no such section."""
        if not anchor or not anchor_exists(anchor):
            return False
        cursor = self.browser.document().find(anchor, 0, QTextDocument.FindFlag.FindCaseSensitively)
        if cursor.isNull():
            return False
        self.browser.setTextCursor(cursor)
        self.browser.ensureCursorVisible()
        return True
