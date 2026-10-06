"""Page 4: map the required and recommended roles to starter assets."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core import mapping, requirements
from rpggen.errors import Issue
from rpggen.gui import edits, thumbnails
from rpggen.gui.pages.audit_page import make_resolver
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.asset_grid import AssetGrid

USE_PLACEHOLDER = "Use placeholder"
CONTINUE_WITHOUT = "Continue without"
THUMB = 32


class AssetPickerDialog(QDialog):
    """The asset grid restricted to the assets a role can plausibly use."""

    def __init__(
        self,
        catalog: catalog_mod.Catalog,
        role: str,
        resolver,  # noqa: ANN001
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("assetPicker")
        self.setWindowTitle(self.tr("Choose an asset for {0}").format(role))
        self.resize(760, 520)
        self.picked: str | None = None
        subset = dataclasses.replace(
            catalog, assets=mapping.candidates(catalog, role), objects=catalog.objects
        )
        layout = QVBoxLayout(self)
        self.grid = AssetGrid()
        self.grid.set_catalog(subset, resolver)
        self.grid.chips["chipAll"].click()
        layout.addWidget(self.grid, 1)
        self.object_list = QListWidget()
        self.object_list.setObjectName("pickerObjects")
        objs = mapping.objects_with_role(catalog, role) if role in mapping.OBJECT_ROLES else []
        for obj in objs:
            item = QListWidgetItem(f"{obj.name}  ({obj.sheet})")
            item.setData(Qt.ItemDataRole.UserRole, obj.id)
            self.object_list.addItem(item)
        self.object_list.setVisible(bool(objs))
        self.object_list.setMaximumHeight(110)
        layout.addWidget(self.object_list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setObjectName("pickerOk")
        self.ok_button.setEnabled(False)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.grid.selectionChanged.connect(self._on_asset_selected)
        self.object_list.currentItemChanged.connect(self._on_object_selected)
        self.grid.view.doubleClicked.connect(lambda _index: self._accept())

    def _on_asset_selected(self, ids: list[str]) -> None:
        self.picked = ids[0] if len(ids) == 1 else None
        self.ok_button.setEnabled(self.picked is not None)
        if self.picked:
            self.object_list.blockSignals(True)
            self.object_list.clearSelection()
            self.object_list.setCurrentRow(-1)
            self.object_list.blockSignals(False)

    def _on_object_selected(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        self.picked = item.data(Qt.ItemDataRole.UserRole)
        self.ok_button.setEnabled(True)
        self.grid.view.clearSelection()

    def _accept(self) -> None:
        if self.picked:
            self.accept()


class RoleRowWidget(QFrame):
    def __init__(self, row: mapping.RoleRow, page: MappingPage) -> None:
        super().__init__()
        self.row = row
        self.setObjectName(f"row_{row.role}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(self)
        self.role_label = QLabel(f"<b>{row.role}</b>" + (" *" if row.required else ""))
        self.status_label = QLabel()
        self.status_label.setObjectName(f"status_{row.role}")
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB + 4, THUMB + 4)
        self.asset_label = QLabel()
        self.asset_label.setObjectName(f"asset_{row.role}")
        self.choose_button = QPushButton(self.tr("Choose…"))
        self.choose_button.setObjectName(f"choose_{row.role}")
        self.fallback = QComboBox()
        self.fallback.setObjectName(f"fallback_{row.role}")
        self.fallback.addItem(self.tr(USE_PLACEHOLDER), "placeholder")
        if not row.required:
            self.fallback.addItem(self.tr(CONTINUE_WITHOUT), "without")
        self.fallback.setCurrentIndex(-1 if row.required else 1)
        grid.addWidget(self.role_label, 0, 0)
        grid.addWidget(self.status_label, 0, 1)
        grid.addWidget(self.thumb_label, 0, 2)
        grid.addWidget(self.asset_label, 0, 3)
        grid.addWidget(self.choose_button, 0, 4)
        grid.addWidget(self.fallback, 0, 5)
        grid.setColumnStretch(3, 1)
        self.choose_button.clicked.connect(lambda: page.choose(row.role))
        self.fallback.activated.connect(lambda _i: page.on_fallback(row.role))


class MappingPage(WizardPage):
    title = "Mapping"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.starter: dict[str, str] = {}
        self.placeholders: set[str] = set()
        self.rows: dict[str, RoleRowWidget] = {}
        self.layout_ = QVBoxLayout(self)
        self.layout_.addWidget(
            QLabel(self.tr("Check that every role has an asset. * marks required roles."))
        )
        self.rows_box = QVBoxLayout()
        self.layout_.addLayout(self.rows_box)
        self.layout_.addStretch(1)

    # ------------------------------------------------------------------ building

    def enter(self, state: WizardState) -> None:
        self.state = state
        if state.catalog is None:
            return
        archetype = state.config.archetype if state.config else state.archetype
        current = dict(state.config.starter) if state.config else {}
        self.starter = mapping.resolve_starter(state.catalog, archetype, current)
        self.placeholders = set(state.placeholders)
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()
        self.rows = {}
        for row in mapping.rows(archetype):
            widget = RoleRowWidget(row, self)
            self.rows[row.role] = widget
            self.rows_box.addWidget(widget)
        self._refresh()

    def _archetype(self) -> str:
        assert self.state is not None
        return self.state.config.archetype if self.state.config else self.state.archetype

    # ------------------------------------------------------------------ showing

    def selection_for(self, role: str) -> str | None:
        assert self.state is not None and self.state.catalog is not None
        key = mapping.ROLE_KEYS.get(role)
        if key:
            return self.starter.get(key)
        return mapping.best_for(self.state.catalog, role)

    def _refresh(self) -> None:
        assert self.state is not None and self.state.catalog is not None
        catalog = self.state.catalog
        for role, widget in self.rows.items():
            ident = self.selection_for(role)
            if ident is not None:
                self._set_status(widget, "ok", "✔ " + self.tr("assigned"))
                widget.asset_label.setText(ident)
                widget.thumb_label.setPixmap(self._thumb(catalog, ident))
                widget.fallback.setEnabled(False)
            else:
                placeholder = role in self.placeholders
                text = (
                    "✔ " + self.tr("placeholder")
                    if placeholder
                    else (
                        "✖ " + self.tr("required, missing")
                        if widget.row.required
                        else "⚠ " + self.tr("missing")
                    )
                )
                state = "ok" if placeholder else ("error" if widget.row.required else "warning")
                self._set_status(widget, state, text)
                widget.asset_label.setText("")
                widget.thumb_label.clear()
                widget.fallback.setEnabled(True)
                data = (
                    "placeholder"
                    if placeholder
                    else ("without" if not widget.row.required else None)
                )
                widget.fallback.setCurrentIndex(max(-1, widget.fallback.findData(data)))
        self.changed.emit()

    @staticmethod
    def _set_status(widget: RoleRowWidget, state: str, text: str) -> None:
        widget.status_label.setText(text)
        widget.status_label.setProperty("state", state)
        widget.status_label.style().unpolish(widget.status_label)
        widget.status_label.style().polish(widget.status_label)

    def _thumb(self, catalog: catalog_mod.Catalog, ident: str) -> QPixmap:
        assert self.state is not None
        resolver = make_resolver(self.state)
        asset = catalog.asset(ident)
        facets: dict = {}
        if asset is None:
            obj = next((o for o in catalog.objects if o.id == ident), None)
            asset = catalog.asset(obj.sheet) if obj else None
            if obj is not None:
                facets = {"usage": "object", "region": obj.region}
        else:
            facets = catalog_mod.effective(asset)
        path = resolver(asset) if asset else None
        if asset is None or path is None:
            return QPixmap()
        request = thumbnails.request_for(asset.sha256, Path(path), facets)
        data = thumbnails.load_or_render(request)
        if data is None:
            return QPixmap()
        pixmap = thumbnails.pixmap_from_bytes(data)
        return pixmap.scaled(
            THUMB,
            THUMB,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    # ------------------------------------------------------------------ actions

    def run_picker(self, dialog: AssetPickerDialog) -> bool:
        return bool(dialog.exec())

    def choose(self, role: str) -> bool:
        """Open the picker for ``role``; picking an asset without the role assigns it."""
        assert self.state is not None and self.state.catalog is not None
        resolver = make_resolver(self.state)
        dialog = AssetPickerDialog(self.state.catalog, role, resolver, self)
        if not self.run_picker(dialog) or dialog.picked is None:
            return False
        self.assign(role, dialog.picked)
        return True

    def assign(self, role: str, ident: str) -> None:
        assert self.state is not None and self.state.catalog is not None
        catalog = self.state.catalog
        asset = catalog.asset(ident)
        if asset is not None and catalog_mod.effective(asset).get("role") != role:
            catalog = edits.set_override(catalog, ident, "role", role)
            self.state.catalog = catalog
        key = mapping.ROLE_KEYS.get(role)
        if key:
            self.starter[key] = ident
        self.placeholders.discard(role)
        self._refresh()

    def on_fallback(self, role: str) -> None:
        widget = self.rows[role]
        choice = widget.fallback.currentData()
        if choice == "placeholder":
            self.placeholders.add(role)
        else:
            self.placeholders.discard(role)
        self._refresh()

    # ------------------------------------------------------------------ wizard hooks

    def validate(self, state: WizardState) -> list[Issue]:
        if state.catalog is None:
            return []
        missing = mapping.missing_required(state.catalog, self._archetype(), self.placeholders)
        info = requirements.REQUIRED_BY
        return [
            form_error(
                self.tr("{0} is required for {1}: choose an asset or a placeholder.").format(
                    role, info.get(role, role.lower())
                )
            )
            for role in missing
        ]

    def leave(self, state: WizardState) -> bool | None:
        if state.catalog is None:
            return None
        state.placeholders = set(self.placeholders)
        if state.config is not None:
            state.config.starter = dict(self.starter)
        return None
