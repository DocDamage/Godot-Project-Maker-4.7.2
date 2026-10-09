"""Edit > Learned rules… (T12.59): list, turn off, delete and export the learned rules."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import learned_rules

# (folder rule dicts) -> how many were added; given when an audit is open
AddFolderRules = Callable[[list[dict[str, Any]]], int]
COLUMNS = ("On", "Rule", "Fixes", "Against", "State")


class LearnedRulesDialog(QDialog):
    def __init__(
        self,
        path: Path | None = None,
        pack_ids: list[str] | None = None,
        add_folder_rules: AddFolderRules | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("learnedRulesDialog")
        self.setWindowTitle(self.tr("Learned rules"))
        self.resize(720, 420)
        self.path = path
        self.book = learned_rules.load(path)
        self.add_folder_rules = add_folder_rules
        layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr(
                "When you fix the role, usage or collision of files whose folder or name share a "
                "word, rpggen remembers it and suggests the same for new packs (still to be "
                "reviewed). A rule is used after {0} fixes. These rules stay on this computer."
            ).format(learned_rules.MIN_HITS)
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("learnedRulesTable")
        self.table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)
        self.empty_label = QLabel(self.tr("No rules yet: they appear as you fix assets."))
        self.empty_label.setObjectName("learnedRulesEmpty")
        layout.addWidget(self.empty_label)
        row = QHBoxLayout()
        self.delete_button = QPushButton(self.tr("Delete"))
        self.delete_button.setObjectName("deleteLearnedRule")
        self.delete_button.clicked.connect(self.delete_selected)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        self.pack_combo = QComboBox()
        self.pack_combo.setObjectName("learnedRulesPack")
        self.pack_combo.addItems(pack_ids or [])
        self.pack_combo.setToolTip(self.tr("The pack the folder rules are for"))
        row.addWidget(self.pack_combo)
        self.export_button = QPushButton(self.tr("Add to folder rules"))
        self.export_button.setObjectName("exportLearnedRules")
        self.export_button.setToolTip(
            self.tr("Make the selected rules folder rules of the open project (one undo step)")
        )
        self.export_button.clicked.connect(self.export_selected)
        row.addWidget(self.export_button)
        close = QPushButton(self.tr("Close"))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setObjectName("learnedRulesStatus")
        layout.addWidget(self.status)
        can_export = add_folder_rules is not None and bool(pack_ids)
        self.export_button.setEnabled(can_export)
        self.pack_combo.setEnabled(can_export)
        if not can_export:
            self.export_button.setToolTip(self.tr("Open a project's Audit page first"))
        self.refresh()

    def _state_text(self, rule: learned_rules.LearnedRule) -> str:
        if not rule.enabled:
            return self.tr("off")
        if rule.active:
            return self.tr("used ({0}%)").format(round(rule.confidence * 100))
        if rule.hits < learned_rules.MIN_HITS:
            return self.tr("needs more fixes")
        return self.tr("too often corrected")

    def refresh(self) -> None:
        self.table.blockSignals(True)
        rules = sorted(self.book.rules, key=lambda r: (-r.hits, r.describe()))
        self.table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            on = QTableWidgetItem()
            on.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            on.setCheckState(Qt.CheckState.Checked if rule.enabled else Qt.CheckState.Unchecked)
            on.setData(Qt.ItemDataRole.UserRole, rule.id)
            self.table.setItem(row, 0, on)
            for col, text in enumerate(
                (rule.describe(), str(rule.hits), str(rule.misses), self._state_text(rule)), start=1
            ):
                self.table.setItem(row, col, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        self.empty_label.setVisible(not rules)
        self.delete_button.setEnabled(bool(rules))

    def rule_ids(self) -> list[str]:
        return [
            str(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))  # type: ignore[union-attr]
            for r in range(self.table.rowCount())
        ]

    def selected_ids(self) -> list[str]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.rule_ids()[r] for r in rows]

    def _save(self) -> None:
        learned_rules.save(self.book, self.path)

    def set_enabled(self, rule_id: str, enabled: bool) -> None:
        rule = self.book.by_id(rule_id)
        if rule is not None and rule.enabled != enabled:
            rule.enabled = enabled
            self._save()
            self.refresh()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self.set_enabled(
                str(item.data(Qt.ItemDataRole.UserRole)), item.checkState() == Qt.CheckState.Checked
            )

    def delete_selected(self) -> int:
        doomed = set(self.selected_ids())
        if not doomed:
            return 0
        self.book.rules = [r for r in self.book.rules if r.id not in doomed]
        self._save()
        self.refresh()
        self.status.setText(self.tr("{0} rule(s) deleted.").format(len(doomed)))
        return len(doomed)

    def export_selected(self) -> int:
        if self.add_folder_rules is None or not self.pack_combo.currentText():
            return 0
        chosen = [self.book.by_id(i) for i in self.selected_ids()]
        pack_id = self.pack_combo.currentText()
        rules = [learned_rules.as_folder_rule(r, pack_id) for r in chosen if r is not None]
        added = self.add_folder_rules(rules) if rules else 0
        self.status.setText(
            self.tr("{0} folder rule(s) added to {1}.").format(added, pack_id)
            if rules
            else self.tr("Select the rules to add first.")
        )
        return added
