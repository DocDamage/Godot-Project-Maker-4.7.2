"""Page 3: audit the detected assets (grid on the left, detail panel on the right)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMenu,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.gui.edits import EditSession
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.asset_detail import AssetDetail
from rpggen.gui.widgets.asset_grid import AssetGrid, PathResolver
from rpggen.gui.widgets.bulk_panel import (
    BulkPanel,
    FolderRuleDialog,
    RulesPanel,
    common_folder,
    default_glob,
)

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
        self.quick_roles = list(QUICK_ROLES)
        self.grid = AssetGrid()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("auditTabs")
        self.tabs.addTab(self.grid, self.tr("Assets"))
        self.rules_panel: RulesPanel | None = None
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
            self.bulk = BulkPanel(self.session)
            self.side.addWidget(self.bulk)
            self.rules_panel = RulesPanel(self.session)
            self.tabs.addTab(self.rules_panel, self.tr("Rules"))
            self.session.changed.connect(self._on_catalog_changed)
            undo = self.session.undo_stack.createUndoAction(self, self.tr("Undo"))
            redo = self.session.undo_stack.createRedoAction(self, self.tr("Redo"))
            undo.setShortcut(QKeySequence.StandardKey.Undo)
            redo.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Y")])
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
        session = self._ensure_session(state)
        self.resolver = make_resolver(state)
        assert self.detail is not None
        self.detail.resolver = self.resolver
        self.grid.set_catalog(session.catalog, self.resolver)

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
