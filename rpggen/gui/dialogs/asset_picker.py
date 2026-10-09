"""The Mapping page's "More…": a gallery of the assets a role can use (T13.05)."""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import app_settings, labels, mapping
from rpggen.core import catalog as catalog_mod
from rpggen.gui.widgets.asset_grid import AssetGrid, PathResolver, split_folder_key


class AssetPickerDialog(QDialog):
    """Thumbnails of the assets ``mapping.candidates`` allows for a role, at the audit grid's
    size, grouped by pack and in rank order inside a pack (the best candidate first), with the
    filter bar's search. A card shows how sure the detection was as the bar under its picture
    and in its tooltip. Double-click, or select and OK, chooses."""

    def __init__(
        self,
        catalog: catalog_mod.Catalog,
        role: str,
        resolver: PathResolver,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("assetPicker")
        self.setWindowTitle(self.tr("Choose an asset for {0}").format(labels.role_label(role)))
        self.resize(760, 520)
        self.picked: str | None = None
        self.candidates = mapping.candidates(catalog, role)
        subset = dataclasses.replace(catalog, assets=self.candidates, objects=catalog.objects)
        layout = QVBoxLayout(self)
        self.grid = AssetGrid()
        self.grid.group_button.setVisible(False)  # the gallery is always grouped, by pack
        self.grid.help_button.setVisible(False)  # the audit's keys do nothing here
        self.grid.view.card_delegate.header_actions = ()
        self.grid.set_thumb_size(app_settings.get().thumb_size)
        self.grid.set_rank([a.id for a in self.candidates])
        self.grid.set_catalog(subset, resolver)
        self.grid.set_grouped(True, by_pack=True)
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
        self.grid.search.setFocus()

    def groups(self) -> list[tuple[str, list[str]]]:
        """What the gallery shows: ``(pack id, its asset ids top to bottom)`` per header."""
        out: list[tuple[str, list[str]]] = []
        for key in self.grid.header_keys():
            pack_id = split_folder_key(key)[0]
            shown = set(self.grid.folder_ids(key))
            out.append((pack_id, [i for i in self.grid.visible_ids() if i in shown]))
        return out

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
