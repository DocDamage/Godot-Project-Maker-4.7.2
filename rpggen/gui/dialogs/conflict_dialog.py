"""Resolve ``.rpggen-new`` conflicts one file at a time (T12.58).

The list on the left holds the files that have a ``.rpggen-new`` version. For the selected file
the dialog shows the version rpggen last wrote (when a backup or the git history has it), yours
and the new one side by side, with the lines that differ from the last generated version (or,
without it, from each other) highlighted. Keep mine, Take new and Merge act at once; each backs
the files up first, so *Restore previous* on the Results page undoes it.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import conflicts
from rpggen.errors import RpgGenError
from rpggen.gui import theme

SHOW_LIMIT = 400_000  # bytes shown per version; a bigger file is cut (the actions use all of it)


def _shown(data: bytes | None) -> str:
    if data is None:
        return ""
    text = data[:SHOW_LIMIT].decode("utf-8", errors="replace").replace("\r\n", "\n")
    return text + ("\n…" if len(data) > SHOW_LIMIT else "")


def changed_lines(reference: str, text: str) -> list[int]:
    """The line numbers of ``text`` that are not in ``reference`` (replaced or inserted)."""
    a, b = reference.splitlines(), text.splitlines()
    out: list[int] = []
    for tag, _a1, _a2, b1, b2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out.extend(range(b1, b2))
    return out


class _Pane(QWidget):
    def __init__(self, title: str, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(title)
        self.title.setObjectName(f"{name}Title")
        layout.addWidget(self.title)
        self.view = QPlainTextEdit()
        self.view.setObjectName(name)
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.view.setAccessibleName(title)
        layout.addWidget(self.view, 1)

    def show_text(self, text: str, marked: list[int]) -> None:
        self.view.setPlainText(text)
        colour = theme.token("diff_changed")
        selections: list[QTextEdit.ExtraSelection] = []
        document = self.view.document()
        for line in marked:
            block = document.findBlockByNumber(line)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(colour)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = QTextCursor(block)
            selections.append(selection)
        self.view.setExtraSelections(selections)
        self.marked = marked


class ConflictDialog(QDialog):
    """The resolver. ``select`` is the file to show first (from an issue's row)."""

    def __init__(self, target: Path, select: str | None = None, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setObjectName("conflictDialog")
        self.setWindowTitle(self.tr("Resolve conflicts"))
        self.resize(1000, 600)
        self.target = Path(target)
        self.resolved: list[conflicts.Resolution] = []
        layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr(
                "You changed these generated files, and the last regeneration made a new version "
                "of each (saved beside it as .rpggen-new). Choose what to keep. Every choice is "
                "backed up first: Restore previous on the Results page undoes it."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.file_list = QListWidget()
        self.file_list.setObjectName("conflictList")
        self.file_list.setAccessibleName(self.tr("Files with a new version"))
        split.addWidget(self.file_list)
        self.panes = QSplitter(Qt.Orientation.Horizontal)
        self.base_pane = _Pane(self.tr("Last generated"), "conflictBase")
        self.mine_pane = _Pane(self.tr("Yours"), "conflictMine")
        self.new_pane = _Pane(self.tr("New"), "conflictNew")
        for pane in (self.base_pane, self.mine_pane, self.new_pane):
            self.panes.addWidget(pane)
        split.addWidget(self.panes)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 780])
        layout.addWidget(split, 1)
        self.note = QLabel()
        self.note.setObjectName("conflictNote")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.status = QLabel()
        self.status.setObjectName("conflictStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.keep_button = self._button(self.tr("Keep mine"), "keepMine", row)
        self.keep_button.setToolTip(
            self.tr("Keep your file. This new version is not offered again; a later one is.")
        )
        self.take_button = self._button(self.tr("Take new"), "takeNew", row)
        self.take_button.setToolTip(
            self.tr("Replace your file with the new version. Later regenerations update it.")
        )
        self.merge_button = self._button(self.tr("Merge"), "mergeBoth", row)
        self.merge_button.setToolTip(
            self.tr("Combine both line by line; where both changed a line, markers show both.")
        )
        row.addStretch(1)
        self.close_button = self._button(self.tr("Close"), "conflictClose", row)
        layout.addLayout(row)
        self.keep_button.clicked.connect(lambda: self.apply(conflicts.Action.KEEP_MINE))
        self.take_button.clicked.connect(lambda: self.apply(conflicts.Action.TAKE_NEW))
        self.merge_button.clicked.connect(lambda: self.apply(conflicts.Action.MERGE))
        self.close_button.clicked.connect(self.accept)
        self.file_list.currentTextChanged.connect(self._show)
        self.refresh(select)

    def _button(self, text: str, name: str, row: QHBoxLayout) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        row.addWidget(button)
        return button

    @property
    def current(self) -> str | None:
        item = self.file_list.currentItem()
        return item.text() if item is not None else None

    def refresh(self, select: str | None = None) -> None:
        files = conflicts.list_conflicts(self.target)
        self.file_list.blockSignals(True)
        self.file_list.clear()
        self.file_list.addItems(files)
        self.file_list.blockSignals(False)
        if files:
            row = files.index(select) if select in files else 0
            self.file_list.setCurrentRow(row)
            self._show(files[row])
        else:
            self._show(None)

    def _show(self, rel: str | None) -> None:
        for button in (self.keep_button, self.take_button, self.merge_button):
            button.setEnabled(bool(rel))
        if not rel:
            for pane in (self.base_pane, self.mine_pane, self.new_pane):
                pane.show_text("", [])
            self.base_pane.setVisible(True)
            self.note.setText(self.tr("No conflicts are left in this project."))
            return
        try:
            found = conflicts.versions(self.target, rel)
        except RpgGenError as exc:
            self.note.setText(exc.issue.message)
            return
        notes: list[str] = []
        if not found.text:
            sizes = [
                self.tr("{0} bytes").format(len(data)) if data is not None else "—"
                for data in (found.base, found.mine, found.new)
            ]
            self.base_pane.show_text(self.tr("(binary file, {0})").format(sizes[0]), [])
            self.mine_pane.show_text(self.tr("(binary file, {0})").format(sizes[1]), [])
            self.new_pane.show_text(self.tr("(binary file, {0})").format(sizes[2]), [])
            self.base_pane.setVisible(found.base is not None)
            self.merge_button.setEnabled(False)
            notes.append(self.tr("This is not a text file: keep yours or take the new version."))
        else:
            base, mine, new = _shown(found.base), _shown(found.mine), _shown(found.new)
            reference_mine = base if found.base is not None else new
            reference_new = base if found.base is not None else mine
            self.base_pane.show_text(base, [])
            self.mine_pane.show_text(mine, changed_lines(reference_mine, mine))
            self.new_pane.show_text(new, changed_lines(reference_new, new))
            self.base_pane.setVisible(found.base is not None)
            if found.base is None:
                notes.append(
                    self.tr(
                        "The version rpggen last wrote was not found (no backup or git commit "
                        "holds it), so only yours and the new one are shown, and a merge marks "
                        "every difference."
                    )
                )
        if found.mine is None:
            notes.append(self.tr("You deleted this file; Take new brings it back."))
        if rel.lower().endswith(conflicts.GODOT_RESOURCE_EXTS):
            notes.append(
                self.tr(
                    "This is a Godot scene or resource: after a merge, open it in Godot to check "
                    "that it still loads."
                )
            )
        self.note.setText("\n".join(notes))

    def apply(self, action: conflicts.Action) -> conflicts.Resolution | None:
        rel = self.current
        if rel is None:
            return None
        try:
            done = conflicts.resolve(self.target, rel, action)
        except RpgGenError as exc:
            self.status.setText(f"{exc.issue.code}: {exc.issue.message}")
            return None
        self.resolved.append(done)
        words = {
            conflicts.Action.KEEP_MINE: self.tr("{0}: kept yours."),
            conflicts.Action.TAKE_NEW: self.tr("{0}: took the new version."),
            conflicts.Action.MERGE: self.tr("{0}: merged."),
        }
        text = words[action].format(rel)
        if done.conflicts:
            text += " " + self.tr(
                "{0} place(s) have conflict markers (<<<<<<< yours … >>>>>>> rpggen): edit them."
            ).format(done.conflicts)
        if done.check_in_godot:
            text += " " + self.tr("Open it in Godot to check it.")
        backup = done.backup.relative_to(self.target).as_posix()
        self.status.setText(text + " " + self.tr("Backup: {0}").format(backup))
        self.refresh()
        return done
