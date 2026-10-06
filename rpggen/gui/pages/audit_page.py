"""Page 3: audit the detected assets (grid on the left, detail panel on the right)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLabel, QSplitter, QStackedWidget, QVBoxLayout, QWidget

from rpggen.core import catalog as catalog_mod
from rpggen.gui.edits import EditSession
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.asset_detail import AssetDetail
from rpggen.gui.widgets.asset_grid import AssetGrid, PathResolver


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
        self.grid = AssetGrid()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("auditSplitter")
        self.splitter.addWidget(self.grid)
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
        self.grid.selectionChanged.connect(self._on_selection)

    # ------------------------------------------------------------------ session wiring

    def _ensure_session(self, state: WizardState) -> EditSession:
        assert state.catalog is not None
        if self.session is None:
            self.session = EditSession(state.catalog, self)
            self.detail = AssetDetail(self.session)
            self.side.addWidget(self.detail)
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
        else:
            self.detail.set_asset(None)
            self.side.setCurrentWidget(self.empty_label)
