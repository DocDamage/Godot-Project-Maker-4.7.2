"""Page 3: audit the detected assets (grid on the left, detail panel on the right)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import ids
from rpggen.core import catalog as catalog_mod
from rpggen.core import profile_registry, profiles
from rpggen.core.inventory import Inventory
from rpggen.errors import RpgGenError
from rpggen.gui.dialogs.profile_dialogs import ExportProfileDialog, FindProfileDialog
from rpggen.gui.edits import EditSession
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import analysis_progress
from rpggen.gui.widgets.anim_preview import AnimEditorDialog
from rpggen.gui.widgets.asset_detail import AssetDetail
from rpggen.gui.widgets.asset_grid import AssetGrid, PathResolver
from rpggen.gui.widgets.bulk_panel import (
    BulkPanel,
    FolderRuleDialog,
    RulesPanel,
    common_folder,
    default_glob,
)
from rpggen.gui.widgets.grid_editor import GridEditorDialog
from rpggen.gui.widgets.object_cutter import ObjectCutterDialog
from rpggen.gui.widgets.terrain_tab import TerrainTab

QUICK_ROLES = ["GROUND", "WALL", "DECORATION", "BUILDING", "PLAYER", "NPC", "ENEMY", "ITEM", "UI"]


def make_resolver(state: WizardState) -> PathResolver:
    """Absolute file of an asset: the extracted/opened root of its pack plus the pack-relative
    path (generated assets such as placeholders have no file here)."""
    roots = {p.pack_id: Path(p.root) for p in state.opened_packs}
    generated_root = Path(state.target) / ".rpggen_staging" if state.target else None

    def resolve(asset: catalog_mod.Asset) -> Path | None:
        parts = asset.path.split("/", 3)
        if len(parts) == 4 and parts[:2] == ["assets", "packs"] and asset.pack_id in roots:
            return roots[asset.pack_id] / parts[3]
        if generated_root is not None:
            candidate = generated_root / asset.path
            return candidate if candidate.exists() else None
        return None

    return resolve


class AuditPage(WizardPage):
    title = "Audit"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session: EditSession | None = None
        self.resolver: PathResolver = lambda asset: None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.state: WizardState | None = None
        bar = QHBoxLayout()
        bar.addStretch(1)
        self.profile_button = QToolButton()
        self.profile_button.setObjectName("profileButton")
        self.profile_button.setText(self.tr("Profile"))
        self.profile_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        profile_menu = QMenu(self.profile_button)
        self.export_action = profile_menu.addAction(self.tr("Export pack profile…"))
        self.export_action.setObjectName("exportProfileAction")
        self.import_action = profile_menu.addAction(self.tr("Import profile…"))
        self.import_action.setObjectName("importProfileAction")
        self.online_action = profile_menu.addAction(self.tr("Find profile online…"))
        self.online_action.setObjectName("findProfileAction")
        self.profile_button.setMenu(profile_menu)
        bar.addWidget(self.profile_button)
        layout.addLayout(bar)
        self.export_action.triggered.connect(lambda: self.export_profile())
        self.import_action.triggered.connect(lambda: self.import_profile())
        self.online_action.triggered.connect(lambda: self.find_profile_online())
        self.quick_roles = list(QUICK_ROLES)
        self.archetype = "turn_based"
        self.grid = AssetGrid()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("auditTabs")
        self.tabs.addTab(self.grid, self.tr("Assets"))
        self.rules_panel: RulesPanel | None = None
        self.terrain_tab: TerrainTab | None = None
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("auditSplitter")
        self.splitter.addWidget(self.tabs)
        self.side = QStackedWidget()
        self.side.setObjectName("auditSide")
        self.empty_label = QLabel(self.tr("Select an asset to see its details."))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side.addWidget(self.empty_label)
        self.detail: AssetDetail | None = None
        self.splitter.addWidget(self.side)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter)
        self.bulk: BulkPanel | None = None
        self.grid.selectionChanged.connect(self._on_selection)
        view = self.grid.view
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(self._on_context_menu)
        view.quickKey.connect(self._on_quick_key)

    def _on_quick_key(self, key: str) -> None:
        if key == "C":
            self._confirm_selection()
        elif key == "X":
            self._exclude_selection()
        else:
            self._quick_role(int(key))

    def _confirm_selection(self) -> None:
        ids = self.grid.selected_ids()
        if ids and self.session is not None:
            self.session.confirm(ids)

    def _exclude_selection(self) -> None:
        ids = self.grid.selected_ids()
        if ids and self.session is not None:
            self.session.bulk_edit(ids, {"role": "NONE"})

    def _quick_role(self, number: int) -> None:
        ids = self.grid.selected_ids()
        if ids and self.session is not None and number <= len(self.quick_roles):
            self.session.bulk_edit(ids, {"role": self.quick_roles[number - 1]})

    # ------------------------------------------------------------------ session wiring

    def _ensure_session(self, state: WizardState) -> EditSession:
        assert state.catalog is not None
        if self.session is None:
            self.session = EditSession(state.catalog, self)
            self.detail = AssetDetail(self.session)
            self.side.addWidget(self.detail)
            self.detail.gridEditRequested.connect(self.edit_grid)
            self.detail.animationsRequested.connect(self.edit_animations)
            self.detail.cutObjectsRequested.connect(self.cut_objects)
            self.bulk = BulkPanel(self.session)
            self.side.addWidget(self.bulk)
            self.rules_panel = RulesPanel(self.session)
            self.tabs.addTab(self.rules_panel, self.tr("Rules"))
            self.terrain_tab = TerrainTab(self.session)
            self.terrain_tab.changed.connect(self.changed.emit)
            self.tabs.addTab(self.terrain_tab, self.tr("Terrain"))
            self.session.changed.connect(self._on_catalog_changed)
            undo = self.session.undo_stack.createUndoAction(self, self.tr("Undo"))
            redo = self.session.undo_stack.createRedoAction(self, self.tr("Redo"))
            undo.setShortcut(QKeySequence.StandardKey.Undo)
            redo.setShortcuts([QKeySequence(QKeySequence.StandardKey.Redo), QKeySequence("Ctrl+Y")])
            for action in (undo, redo):
                action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                self.addAction(action)
            self.undo_action, self.redo_action = undo, redo
        elif self.session.catalog is not state.catalog:
            self.session.reset(state.catalog)
        return self.session

    def enter(self, state: WizardState) -> None:
        if state.catalog is None:
            return
        self.state = state
        self.archetype = state.archetype
        session = self._ensure_session(state)
        self.resolver = make_resolver(state)
        assert self.detail is not None
        self.detail.resolver = self.resolver
        if self.terrain_tab is not None:
            self.terrain_tab.resolver = self.resolver
            self.terrain_tab.refresh()
        self.grid.set_catalog(session.catalog, self.resolver)
        changed = {a.id for a in session.catalog.assets if a.path in state.changed_paths}
        self.grid.set_changed(changed)

    def leave(self, state: WizardState) -> bool | None:
        if self.session is not None:
            state.catalog = self.session.catalog
        return None

    # ------------------------------------------------------------------ reacting

    def _on_catalog_changed(self, ids: list[str]) -> None:
        assert self.session is not None
        self.grid.model.catalog = self.session.catalog
        self.grid.model.refresh(ids or None)
        self.changed.emit()

    def _on_selection(self, ids: list[str]) -> None:
        if self.detail is None:
            return
        if len(ids) == 1:
            self.detail.set_asset(ids[0])
            self.side.setCurrentWidget(self.detail)
        elif len(ids) > 1 and self.bulk is not None:
            self.detail.set_asset(None)
            self.bulk.set_assets(ids)
            self.side.setCurrentWidget(self.bulk)
        else:
            self.detail.set_asset(None)
            self.side.setCurrentWidget(self.empty_label)

    # ------------------------------------------------------------------ dialogs

    def run_dialog(self, dialog) -> bool:  # noqa: ANN001 - overridden by tests
        return bool(dialog.exec())

    def edit_grid(self, asset_id: str) -> bool:
        """Open the grid editor; Apply writes a ``grid`` override."""
        assert self.session is not None
        asset = self.session.catalog.asset(asset_id)
        path = self.resolver(asset) if asset else None
        if asset is None or path is None:
            return False
        grid = catalog_mod.effective(asset).get("grid")
        dialog = GridEditorDialog(path, grid, asset.path, self)
        if not self.run_dialog(dialog):
            return False
        return self.session.set_override(asset_id, "grid", dialog.grid())

    def edit_animations(self, asset_id: str) -> bool:
        """Open the animation editor; Apply writes ``animations``/``origin``/``frame``."""
        assert self.session is not None
        asset = self.session.catalog.asset(asset_id)
        path = self.resolver(asset) if asset else None
        if asset is None or path is None:
            return False
        eff = catalog_mod.effective(asset)
        grid = eff.get("grid")
        frame = tuple(eff.get("frame") or (grid["cell"] if grid else (16, 16)))

        def sheet_for(source: str) -> Path | None:
            return self.resolver(dataclasses.replace(asset, path=source))

        dialog = AnimEditorDialog(
            path,
            eff.get("animations") or {},
            frame,
            tuple(eff["origin"]) if eff.get("origin") else None,
            grid,
            arpg=self.archetype == "arpg",
            sheet_resolver=sheet_for,
            parent=self,
        )
        if not self.run_dialog(dialog):
            return False
        values = dialog.overrides()
        if not values:
            return False
        return self.session.set_overrides([asset_id], values, "Edit animations")

    def cut_objects(self, asset_id: str) -> bool:
        """Open the object cutter for a sheet; Apply replaces the sheet's objects."""
        assert self.session is not None
        catalog = self.session.catalog
        asset = catalog.asset(asset_id)
        path = self.resolver(asset) if asset else None
        if asset is None or path is None:
            return False
        dialog = ObjectCutterDialog(
            path,
            asset_id,
            [o for o in catalog.objects if o.sheet == asset_id],
            catalog_mod.effective(asset).get("grid"),
            {o.id for o in catalog.objects},
            self,
        )
        if not self.run_dialog(dialog):
            return False
        return self.session.set_sheet_objects(asset_id, dialog.result_objects())

    # ------------------------------------------------------------------ pack profiles

    def choose_save_path(self, default_name: str) -> Path | None:  # overridden by tests
        name, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export pack profile"),
            default_name,
            self.tr("Pack profiles (*.rpgprofile.json)"),
        )
        return Path(name) if name else None

    def choose_open_path(self) -> Path | None:  # overridden by tests
        name, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import profile"),
            "",
            self.tr("Pack profiles (*.rpgprofile.json);;JSON (*.json)"),
        )
        return Path(name) if name else None

    def show_error(self, title: str, message: str) -> None:  # overridden by tests
        QMessageBox.warning(self, title, message)

    def run_analysis(self, state: WizardState) -> bool:  # overridden by tests
        return analysis_progress.run_analysis(self, state)

    def export_profile(self) -> Path | None:
        """Ask for the profile's details and a file, then write the profile of one pack."""
        state = self.state
        if self.session is None or state is None or not state.inventories:
            return None
        catalog = self.session.catalog
        pack_ids = [inv.pack_id for inv in state.inventories]
        dialog = ExportProfileDialog(pack_ids, pack_ids[0], self)
        if not self.run_dialog(dialog):
            return None
        pack_id = dialog.pack_id() or pack_ids[0]
        inventory = next(inv for inv in state.inventories if inv.pack_id == pack_id)
        meta = dialog.meta()
        path = self.choose_save_path(f"{ids.slug(meta['title'])}{profiles.PROFILE_SUFFIX}")
        if path is None:
            return None
        try:
            data = profiles.export_profile(catalog, pack_id, inventory, meta)
            profiles.write_profile(data, path)
        except (RpgGenError, OSError) as exc:
            self.show_error(self.tr("Could not export the profile"), str(exc))
            return None
        return path

    def fetch_registry(self, inventories: list[Inventory]) -> list[profile_registry.Candidate]:
        """Download the registry index and match it (overridden by tests). Network only here."""
        return profile_registry.candidates(profile_registry.fetch_index(), inventories)

    def download_registry_profile(self, profile_id: str) -> None:  # overridden by tests
        profile_registry.download_profile(profile_id)

    def find_profile_online(self) -> bool:
        """The user-initiated network call: list matching community profiles, install the one
        the user picks, then analyze again (the user's edits are kept). True when installed."""
        state = self.state
        if state is None or self.session is None or not state.inventories:
            return False
        try:
            found = self.fetch_registry(state.inventories)
        except (profile_registry.RegistryError, OSError) as exc:
            self.show_error(self.tr("Could not reach the profile registry"), str(exc))
            return False
        if not found:
            self.show_error(
                self.tr("Find profile online"),
                self.tr("No community profile matches your packs yet."),
            )
            return False
        dialog = FindProfileDialog(found, self)
        if not self.run_dialog(dialog):
            return False
        chosen = dialog.selected()
        if chosen is None:
            return False
        try:
            self.download_registry_profile(chosen.profile_id)
        except (profile_registry.RegistryError, RpgGenError, OSError) as exc:
            self.show_error(self.tr("Could not install the profile"), str(exc))
            return False
        state.catalog = self.session.catalog
        if not self.run_analysis(state):
            return False
        self.enter(state)
        self.changed.emit()
        return True

    def import_profile(self) -> bool:
        """Install a profile file and analyze the packs again; the user's edits are kept."""
        state = self.state
        if state is None or self.session is None:
            return False
        path = self.choose_open_path()
        if path is None:
            return False
        try:
            profile = profiles.install_profile(path)
        except (RpgGenError, OSError, ValueError) as exc:
            self.show_error(self.tr("Could not import the profile"), str(exc))
            return False
        state.catalog = self.session.catalog  # re-assembly builds on the current edits
        if not self.run_analysis(state):
            return False
        self.enter(state)
        self.changed.emit()
        return bool(profile)

    # ------------------------------------------------------------------ folder rules

    def _on_context_menu(self, pos: QPoint) -> None:
        if not self.grid.selected_ids():
            return
        menu = QMenu(self)
        action = menu.addAction(self.tr("Make rule for this folder…"))
        action.setObjectName("makeRuleAction")
        action.triggered.connect(self.make_rule)
        menu.exec(self.grid.view.viewport().mapToGlobal(pos))

    def make_rule(self) -> bool:
        """Open the rule dialog for the selection; True when a rule was added."""
        ids = self.grid.selected_ids()
        if not ids or self.session is None:
            return False
        found = common_folder(self.session.catalog, ids)
        if found is None:
            return False
        pack_id, folder = found
        values = self.bulk.values() if self.bulk is not None and len(ids) > 1 else {}
        dialog = FolderRuleDialog(
            [p.pack_id for p in self.session.catalog.packs],
            pack_id,
            default_glob(folder),
            values,
            self,
        )
        if not self.run_rule_dialog(dialog):
            return False
        return self.session.add_rule(dialog.rule())

    def run_rule_dialog(self, dialog: FolderRuleDialog) -> bool:
        return bool(dialog.exec())
