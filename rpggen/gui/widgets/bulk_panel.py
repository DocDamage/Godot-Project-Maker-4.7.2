"""Bulk editing of several selected assets, folder rules and the rules list."""

from __future__ import annotations

import json
import posixpath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets.asset_detail import COLLISION_PROFILES, ROLES, USAGES, add_labeled

UNCHANGED = "— unchanged —"


def _optional_combo(name: str, items: list[str], kind: str = "") -> QComboBox:
    combo = QComboBox()
    combo.setObjectName(name)
    combo.addItem(UNCHANGED, None)
    for item in items:
        if kind:
            add_labeled(combo, item, kind)
        else:
            combo.addItem(item, item)
    return combo


def split_tags(text: str) -> list[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


class BulkPanel(QWidget):
    """Replaces the detail panel while more than one asset is selected."""

    def __init__(self, session: EditSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bulkPanel")
        self.session = session
        self.asset_ids: list[str] = []
        layout = QVBoxLayout(self)
        self.count_label = QLabel()
        self.count_label.setObjectName("bulkCount")
        layout.addWidget(self.count_label)
        form = QFormLayout()
        layout.addLayout(form)
        self.role_combo = _optional_combo("bulkRole", ROLES, "role")
        self.usage_combo = _optional_combo("bulkUsage", USAGES, "usage")
        self.collision_combo = _optional_combo("bulkCollision", COLLISION_PROFILES)
        self.tileset_combo = _optional_combo("bulkTileset", [])
        self.add_tags_edit = QLineEdit()
        self.add_tags_edit.setObjectName("bulkAddTags")
        self.remove_tags_edit = QLineEdit()
        self.remove_tags_edit.setObjectName("bulkRemoveTags")
        form.addRow(self.tr("Role"), self.role_combo)
        form.addRow(self.tr("Usage"), self.usage_combo)
        form.addRow(self.tr("Collision"), self.collision_combo)
        form.addRow(self.tr("Tileset"), self.tileset_combo)
        form.addRow(self.tr("Add tags"), self.add_tags_edit)
        form.addRow(self.tr("Remove tags"), self.remove_tags_edit)
        buttons = QHBoxLayout()
        self.apply_button = QPushButton(self.tr("Apply"))
        self.apply_button.setObjectName("bulkApply")
        self.confirm_button = QPushButton(self.tr("Confirm all"))
        self.confirm_button.setObjectName("bulkConfirm")
        self.exclude_button = QPushButton(self.tr("Exclude all"))
        self.exclude_button.setObjectName("bulkExclude")
        for b in (self.apply_button, self.confirm_button, self.exclude_button):
            buttons.addWidget(b)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.apply_button.clicked.connect(self.apply)
        self.confirm_button.clicked.connect(lambda: self.session.confirm(self.asset_ids))
        self.exclude_button.clicked.connect(
            lambda: self.session.bulk_edit(self.asset_ids, {"role": "NONE"})
        )

    def set_assets(self, asset_ids: list[str]) -> None:
        self.asset_ids = list(asset_ids)
        self.count_label.setText(self.tr("{0} assets selected").format(len(asset_ids)))
        self.tileset_combo.clear()
        self.tileset_combo.addItem(UNCHANGED, None)
        for tdef in self.session.catalog.tilesets:
            self.tileset_combo.addItem(tdef.name, tdef.name)
        for combo in (self.role_combo, self.usage_combo, self.collision_combo):
            combo.setCurrentIndex(0)
        self.add_tags_edit.clear()
        self.remove_tags_edit.clear()

    def values(self) -> dict:
        """The facet values chosen in the combos (unchanged ones are left out)."""
        out: dict = {}
        if (role := self.role_combo.currentData()) is not None:
            out["role"] = role
        if (usage := self.usage_combo.currentData()) is not None:
            out["usage"] = usage
        if (profile := self.collision_combo.currentData()) is not None:
            out["collision"] = {"profile": profile}
        if (tileset := self.tileset_combo.currentData()) is not None:
            out["tileset"] = tileset
        return out

    def apply(self) -> None:
        add = split_tags(self.add_tags_edit.text())
        remove = split_tags(self.remove_tags_edit.text())
        values = self.values()
        if values or add or remove:
            self.session.bulk_edit(self.asset_ids, values, add, remove)


# --------------------------------------------------------------------------- folder rules


def common_folder(catalog: catalog_mod.Catalog, asset_ids: list[str]) -> tuple[str, str] | None:
    """``(pack_id, pack-relative folder)`` shared by the assets, or None across several packs."""
    packs = {p.pack_id: p for p in catalog.packs}
    wanted = set(asset_ids)
    folders: list[str] = []
    pack_id = None
    for asset in catalog.assets:
        if asset.id not in wanted:
            continue
        if pack_id not in (None, asset.pack_id):
            return None
        pack_id = asset.pack_id
        root = packs[asset.pack_id].root if asset.pack_id in packs else ""
        rel = (
            asset.path[len(root) + 1 :]
            if root and asset.path.startswith(root + "/")
            else asset.path
        )
        folders.append(posixpath.dirname(rel))
    if pack_id is None:
        return None
    return pack_id, posixpath.commonpath(folders) if folders else ""


def default_glob(folder: str) -> str:
    return f"{folder}/**" if folder else "**"


class FolderRuleDialog(QDialog):
    """Create a folder rule: pack, glob and the facet values it sets."""

    def __init__(
        self,
        pack_ids: list[str],
        pack_id: str,
        glob: str,
        values: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("folderRuleDialog")
        self.setWindowTitle(self.tr("Make rule for this folder"))
        self._extra = {k: v for k, v in values.items() if k not in ("role", "usage")}
        form = QFormLayout(self)
        self.pack_combo = QComboBox()
        self.pack_combo.setObjectName("rulePack")
        self.pack_combo.addItems(pack_ids)
        self.pack_combo.setCurrentText(pack_id)
        self.glob_edit = QLineEdit(glob)
        self.glob_edit.setObjectName("ruleGlob")
        self.role_combo = _optional_combo("ruleRole", ROLES, "role")
        self.usage_combo = _optional_combo("ruleUsage", USAGES)
        for combo, key in ((self.role_combo, "role"), (self.usage_combo, "usage")):
            if key in values:
                combo.setCurrentIndex(max(0, combo.findData(values[key])))
        self.extra_label = QLabel(json.dumps(self._extra, sort_keys=True) if self._extra else "")
        form.addRow(self.tr("Pack"), self.pack_combo)
        form.addRow(self.tr("Glob"), self.glob_edit)
        form.addRow(self.tr("Role"), self.role_combo)
        form.addRow(self.tr("Usage"), self.usage_combo)
        if self._extra:
            form.addRow(self.tr("Also sets"), self.extra_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def rule(self) -> catalog_mod.FolderRule:
        values = dict(self._extra)
        if (role := self.role_combo.currentData()) is not None:
            values["role"] = role
        if (usage := self.usage_combo.currentData()) is not None:
            values["usage"] = usage
        return catalog_mod.FolderRule(
            self.pack_combo.currentText(), self.glob_edit.text().strip() or "**", values
        )


class RulesPanel(QWidget):
    """The "Rules" tab: ordered folder rules that can be deleted and dragged into a new order."""

    def __init__(self, session: EditSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rulesPanel")
        self.session = session
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName("rulesList")
        self.list.setToolTip(self.tr("Folder rules: what happens to every file in a folder"))
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        layout.addWidget(self.list, 1)
        self.delete_button = QPushButton(self.tr("Delete rule"))
        self.delete_button.setObjectName("deleteRuleButton")
        layout.addWidget(self.delete_button)
        self.delete_button.clicked.connect(self._delete_selected)
        self.list.model().rowsMoved.connect(self._on_moved)
        session.changed.connect(lambda _ids: self.reload())
        self.reload()

    def reload(self) -> None:
        self.list.blockSignals(True)
        self.list.model().blockSignals(True)
        self.list.clear()
        for i, rule in enumerate(self.session.catalog.folder_rules):
            item = QListWidgetItem(
                f"{i + 1}. {rule.pack_id}: {rule.glob} → {json.dumps(rule.set, sort_keys=True)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
        self.list.model().blockSignals(False)
        self.list.blockSignals(False)

    def current_order(self) -> list[int]:
        return [self.list.item(r).data(Qt.ItemDataRole.UserRole) for r in range(self.list.count())]

    def _on_moved(self, *_args) -> None:  # noqa: ANN002
        order = self.current_order()
        if not self.session.reorder_rules(order):
            self.reload()

    def _delete_selected(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.session.delete_rule(row)
