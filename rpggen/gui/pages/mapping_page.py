"""Page 4: map the required and recommended roles to starter assets."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core import labels, mapping, requirements
from rpggen.errors import Issue
from rpggen.gui import edits, thumbnails
from rpggen.gui.pages.audit_page import make_resolver
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.asset_grid import AssetGrid
from rpggen.gui.widgets.sound_section import SoundSection

USE_PLACEHOLDER = "Use placeholder"
CONTINUE_WITHOUT = "Continue without"
THUMB = 48


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
    """One role: its friendly name, the status, a 48 px picture, the asset's file and pack, what
    the role is used for, and Choose… / Clear. A row without an asset offers the fallbacks as
    labelled radio buttons ("No asset: use a placeholder / continue without")."""

    def __init__(self, row: mapping.RoleRow, page: MappingPage) -> None:
        super().__init__()
        self.row = row
        self.setObjectName(f"row_{row.role}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(self)
        title = labels.role_label(row.role) + (" *" if row.required else "")
        self.role_label = QLabel(f"<b>{title}</b>")
        self.role_label.setToolTip(f"{row.role}: {labels.role_help(row.role)}")
        self.role_label.setMinimumWidth(150)
        self.status_label = QLabel()
        self.status_label.setObjectName(f"status_{row.role}")
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB + 4, THUMB + 4)
        self.asset_label = QLabel()
        self.asset_label.setObjectName(f"asset_{row.role}")
        self.used_label = QLabel(self.tr("Used for {0}").format(mapping.used_for(row.role)))
        self.used_label.setObjectName(f"used_{row.role}")
        self.used_label.setProperty("muted", True)
        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        text_box.addWidget(self.asset_label)
        text_box.addWidget(self.used_label)
        self.choose_button = QPushButton(self.tr("Choose…"))
        self.choose_button.setObjectName(f"choose_{row.role}")
        self.choose_button.setToolTip(self.tr("Pick the asset for this role"))
        self.clear_button = QPushButton(self.tr("Clear"))
        self.clear_button.setObjectName(f"clear_{row.role}")
        self.clear_button.setToolTip(
            self.tr("Forget your choice: rpggen picks again (or leaves the role empty)")
        )
        # what to do without an asset
        self.fallback_box = QWidget()
        self.fallback_box.setObjectName(f"fallback_{row.role}")
        fallback_layout = QHBoxLayout(self.fallback_box)
        fallback_layout.setContentsMargins(0, 0, 0, 0)
        fallback_layout.addWidget(QLabel(self.tr("No asset:")))
        self.placeholder_radio = QRadioButton(self.tr("Use a placeholder"))
        self.placeholder_radio.setObjectName(f"placeholder_{row.role}")
        self.placeholder_radio.setToolTip(
            self.tr("Draw a plain coloured shape so that the game still works")
        )
        fallback_layout.addWidget(self.placeholder_radio)
        self.without_radio = QRadioButton(self.tr("Continue without"))
        self.without_radio.setObjectName(f"without_{row.role}")
        self.without_radio.setToolTip(self.tr("Leave this part out of the game"))
        if row.required:  # a required role cannot be left out
            self.without_radio.setParent(self.fallback_box)
            self.without_radio.setVisible(False)
        else:
            fallback_layout.addWidget(self.without_radio)
        fallback_layout.addStretch(1)
        self.fallback_group = QButtonGroup(self)
        self.fallback_group.addButton(self.placeholder_radio)
        self.fallback_group.addButton(self.without_radio)
        self.fallback_group.setExclusive(False)  # a required row starts with neither chosen
        grid.addWidget(self.role_label, 0, 0)
        grid.addWidget(self.status_label, 0, 1)
        grid.addWidget(self.thumb_label, 0, 2, 2, 1)
        grid.addLayout(text_box, 0, 3)
        grid.addWidget(self.choose_button, 0, 4)
        grid.addWidget(self.clear_button, 0, 5)
        grid.addWidget(self.fallback_box, 1, 3, 1, 3)
        grid.setColumnStretch(3, 1)
        self.choose_button.clicked.connect(lambda: page.choose(row.role))
        self.clear_button.clicked.connect(lambda: page.clear(row.role))
        self.placeholder_radio.clicked.connect(lambda _c: page.on_fallback(row.role, "placeholder"))
        self.without_radio.clicked.connect(lambda _c: page.on_fallback(row.role, "without"))

    def set_fallback(self, choice: str | None) -> None:
        """Shows the chosen fallback without sending a click."""
        for radio, value in (
            (self.placeholder_radio, "placeholder"),
            (self.without_radio, "without"),
        ):
            radio.blockSignals(True)
            radio.setChecked(choice == value)
            radio.blockSignals(False)


def checkerboard(size: int) -> QPixmap:
    """The grey squares behind transparency."""
    pixmap = QPixmap(size, size)
    painter = QPainter(pixmap)
    square = 8
    for y in range(0, size, square):
        for x in range(0, size, square):
            shade = 200 if ((x // square) + (y // square)) % 2 == 0 else 232
            painter.fillRect(x, y, square, square, QColor(shade, shade, shade))
    painter.end()
    return pixmap


class MappingPage(WizardPage):
    title = "Mapping"
    help_anchor = "3. Using a pack you bought"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.starter: dict[str, str] = {}
        self.placeholders: set[str] = set()
        self.without: set[str] = set()  # optional roles the user left out on purpose
        self.rows: dict[str, RoleRowWidget] = {}
        self.layout_ = QVBoxLayout(self)
        self.layout_.addWidget(
            QLabel(self.tr("Check that every role has an asset. * marks required roles."))
        )
        self.summary_label = QLabel()
        self.summary_label.setObjectName("mappingSummary")
        self.layout_.addWidget(self.summary_label)
        self.rows_box = QVBoxLayout()
        self.layout_.addLayout(self.rows_box)
        self.sound_section = SoundSection()
        self.sound_section.changed.connect(self.changed.emit)
        self.layout_.addWidget(self.sound_section)
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
        self.without = set()
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()
        self.rows = {}
        rows = {row.role: row for row in mapping.rows(archetype)}
        placed: set[str] = set()
        for group, roles in labels.ROLE_GROUPS:
            members = [rows[r] for r in roles if r in rows]
            if not members:
                continue
            header = QLabel(f"<b>{self.tr(group)}</b>")
            header.setObjectName(f"group_{group}")
            self.rows_box.addWidget(header)
            for row in members:
                widget = RoleRowWidget(row, self)
                self.rows[row.role] = widget
                self.rows_box.addWidget(widget)
                placed.add(row.role)
        for role, row in rows.items():  # a role without a group still gets a row
            if role not in placed:
                widget = RoleRowWidget(row, self)
                self.rows[role] = widget
                self.rows_box.addWidget(widget)
        self._refresh()
        self.sound_section.set_data(
            state.catalog,
            dict(state.config.sounds) if state.config else {},
            make_resolver(state),
        )

    def _archetype(self) -> str:
        assert self.state is not None
        return self.state.config.archetype if self.state.config else self.state.archetype

    # ------------------------------------------------------------------ showing

    def selection_for(self, role: str) -> str | None:
        assert self.state is not None and self.state.catalog is not None
        key = mapping.ROLE_KEYS.get(role)
        if key:
            return self.starter.get(key) or None
        return mapping.best_for(self.state.catalog, role)

    def _display_name(self, catalog: catalog_mod.Catalog, ident: str) -> tuple[str, str]:
        """("meadow_a2.png · sample_pack", the id for the tooltip) of an asset or object."""
        asset = catalog.asset(ident)
        if asset is not None:
            return f"{asset.path.rsplit('/', 1)[-1]} · {asset.pack_id}", ident
        obj = next((o for o in catalog.objects if o.id == ident), None)
        if obj is not None:
            sheet = catalog.asset(obj.sheet)
            where = sheet.pack_id if sheet is not None else ""
            return f"{obj.name} · {where}".rstrip(" ·"), ident
        return ident, ident

    def _refresh(self) -> None:
        assert self.state is not None and self.state.catalog is not None
        catalog = self.state.catalog
        assigned: dict[str, bool] = {}
        for role, widget in self.rows.items():
            ident = self.selection_for(role)
            assigned[role] = ident is not None or role in self.placeholders
            if ident is not None:
                self._set_status(widget, "ok", "✔ " + self.tr("assigned"))
                text, tip = self._display_name(catalog, ident)
                widget.asset_label.setText(text)
                widget.asset_label.setToolTip(tip)
                widget.thumb_label.setPixmap(self._thumb(catalog, ident))
                widget.fallback_box.setVisible(False)
                key = mapping.ROLE_KEYS.get(role)
                automatic = mapping.best_for(catalog, role)
                widget.clear_button.setVisible(key is not None)
                widget.clear_button.setEnabled(key is not None and ident != automatic)
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
                widget.asset_label.setToolTip("")
                widget.thumb_label.clear()
                widget.fallback_box.setVisible(True)
                widget.clear_button.setVisible(False)
                choice = (
                    "placeholder"
                    if placeholder
                    else ("without" if not widget.row.required else None)
                )
                widget.set_fallback(choice)
        archetype = self._archetype()
        self.summary_label.setText(self._summary(archetype, assigned))
        self.changed.emit()

    def _summary(self, archetype: str, assigned: dict[str, bool]) -> str:
        required = [r for r in mapping.rows(archetype) if r.required]
        optional = [r for r in mapping.rows(archetype) if not r.required]
        done_required = sum(1 for r in required if assigned.get(r.role))
        done_optional = sum(1 for r in optional if assigned.get(r.role))
        return self.tr(
            "{0} of {1} required roles assigned, {2} of {3} optional roles assigned"
        ).format(done_required, len(required), done_optional, len(optional))

    @staticmethod
    def _set_status(widget: RoleRowWidget, state: str, text: str) -> None:
        widget.status_label.setText(text)
        widget.status_label.setProperty("state", state)
        widget.status_label.style().unpolish(widget.status_label)
        widget.status_label.style().polish(widget.status_label)

    def _thumb(self, catalog: catalog_mod.Catalog, ident: str) -> QPixmap:
        """48 px, on a checkerboard; a tile sheet shows its first 3 x 3 filled cells."""
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
        if asset is None or path is None or asset.kind != "image":
            return QPixmap()
        request = thumbnails.request_for(
            asset.sha256, Path(path), facets, size=THUMB, cells=3, skip_empty=True
        )
        data = thumbnails.load_or_render(request)
        if data is None:
            return QPixmap()
        picture = thumbnails.pixmap_from_bytes(data).scaled(
            THUMB,
            THUMB,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        canvas = checkerboard(THUMB)
        painter = QPainter(canvas)
        painter.drawPixmap((THUMB - picture.width()) // 2, (THUMB - picture.height()) // 2, picture)
        painter.end()
        return canvas

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
        self.without.discard(role)
        self._refresh()

    def clear(self, role: str) -> None:
        """Forgets the user's choice: the role goes back to the automatic one (or to none)."""
        assert self.state is not None and self.state.catalog is not None
        key = mapping.ROLE_KEYS.get(role)
        if not key:
            return
        automatic = mapping.best_for(self.state.catalog, role)
        if automatic is not None:
            self.starter[key] = automatic
        else:
            self.starter.pop(key, None)
        self._refresh()

    def on_fallback(self, role: str, choice: str | None = None) -> None:
        widget = self.rows[role]
        if choice is None:  # asked without a click: read the radio buttons
            choice = (
                "placeholder"
                if widget.placeholder_radio.isChecked()
                else ("without" if widget.without_radio.isChecked() else None)
            )
        if choice == "placeholder":
            self.placeholders.add(role)
            self.without.discard(role)
        else:
            self.placeholders.discard(role)
            if choice == "without":
                self.without.add(role)
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
                    labels.role_label(role), info.get(role, role.lower())
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
            state.config.sounds = dict(self.sound_section.sounds)
        return None
