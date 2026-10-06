"""The asset grid: a virtualized model/view of every asset with filters and status colors."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.gui import thumbnails

AssetIdRole = Qt.ItemDataRole.UserRole + 1
StatusRole = Qt.ItemDataRole.UserRole + 2
RoleRole = Qt.ItemDataRole.UserRole + 3
UsageRole = Qt.ItemDataRole.UserRole + 4
ConfidenceRole = Qt.ItemDataRole.UserRole + 5
PackRole = Qt.ItemDataRole.UserRole + 6
PathRole = Qt.ItemDataRole.UserRole + 7

STATUS_ORDER = ["CONFLICT", "NEEDS_REVIEW", "MISSING", "AUTO_DETECTED", "CONFIRMED", "UNUSED"]
STATUS_PRIORITY = {s: i for i, s in enumerate(STATUS_ORDER)}
NEEDS_ATTENTION = frozenset({"CONFLICT", "NEEDS_REVIEW", "MISSING"})

# Mirrors the ``status-colors`` block of style.qss (a test keeps both in step).
STATUS_COLORS = {
    "CONFLICT": "#d32f2f",
    "NEEDS_REVIEW": "#f57c00",
    "MISSING": "#7b1fa2",
    "AUTO_DETECTED": "#1976d2",
    "CONFIRMED": "#388e3c",
    "UNUSED": "#9e9e9e",
}

GRID_SIZE = QSize(112, 132)
THUMB = thumbnails.THUMB_SIZE

PathResolver = Callable[[catalog_mod.Asset], Path | None]


def file_label(asset: catalog_mod.Asset) -> str:
    name = asset.path.rsplit("/", 1)[-1]
    return name + ("#" + asset.id.split("#", 1)[1] if "#" in asset.id else "")


class AssetListModel(QAbstractListModel):
    """One row per asset of the catalog (objects are not rows)."""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.catalog: catalog_mod.Catalog | None = None
        self._assets: list[catalog_mod.Asset] = []
        self._facets: list[dict] = []
        self._row_of: dict[str, int] = {}
        self._keys: dict[str, str] = {}  # asset id -> thumbnail key
        self._by_key: dict[str, list[str]] = {}
        self.cache = thumbnails.ThumbnailCache()
        self.loader = thumbnails.ThumbnailLoader(self)
        self.loader.ready.connect(self._thumbnail_ready)
        self.resolver: PathResolver = lambda asset: None
        self._placeholder: QPixmap | None = None

    # ------------------------------------------------------------------ data

    def set_catalog(
        self, catalog: catalog_mod.Catalog | None, resolver: PathResolver | None = None
    ):
        self.beginResetModel()
        self.catalog = catalog
        if resolver is not None:
            self.resolver = resolver
        self._assets = list(catalog.assets) if catalog else []
        self._facets = [catalog_mod.effective(a) for a in self._assets]
        self._row_of = {a.id: i for i, a in enumerate(self._assets)}
        self._keys.clear()
        self._by_key.clear()
        self.endResetModel()

    def refresh(self, asset_ids: list[str] | None = None) -> None:
        """Re-read the facets of changed assets (all when ``asset_ids`` is None)."""
        if self.catalog is None:
            return
        by_id = {a.id: a for a in self.catalog.assets}
        if asset_ids is None or len(by_id) != len(self._assets):
            self.set_catalog(self.catalog)
            return
        for asset_id in asset_ids:
            row = self._row_of.get(asset_id)
            if row is None:
                continue
            self._assets[row] = by_id[asset_id]
            self._facets[row] = catalog_mod.effective(by_id[asset_id])
            self._keys.pop(asset_id, None)
            self.dataChanged.emit(self.index(row), self.index(row))

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._assets)

    def asset_at(self, row: int) -> catalog_mod.Asset:
        return self._assets[row]

    def row_of(self, asset_id: str) -> int | None:
        return self._row_of.get(asset_id)

    def roles(self) -> list[str]:
        return sorted({str(f.get("role")) for f in self._facets if f.get("role")})

    def packs(self) -> list[str]:
        return sorted({a.pack_id for a in self._assets})

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if not index.isValid() or not 0 <= index.row() < len(self._assets):
            return None
        asset = self._assets[index.row()]
        facets = self._facets[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return file_label(asset)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._pixmap_for(asset, facets)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{asset.path}\n{asset.status}  {facets.get('role', '-')}"
        if role == AssetIdRole:
            return asset.id
        if role == StatusRole:
            return asset.status
        if role == RoleRole:
            return facets.get("role", "")
        if role == UsageRole:
            return facets.get("usage", "")
        if role == ConfidenceRole:
            return asset.confidence
        if role == PackRole:
            return asset.pack_id
        if role == PathRole:
            return asset.path
        return None

    # ------------------------------------------------------------------ thumbnails

    def _placeholder_pixmap(self) -> QPixmap:
        if self._placeholder is None:
            self._placeholder = thumbnails.placeholder_pixmap()
        return self._placeholder

    def _pixmap_for(self, asset: catalog_mod.Asset, facets: dict) -> QPixmap:
        key = self._keys.get(asset.id)
        if key is None:
            path = self.resolver(asset)
            if path is None:
                return self._placeholder_pixmap()
            req = thumbnails.request_for(asset.sha256, path, facets)
            key = req.key
            self._keys[asset.id] = key
            self._by_key.setdefault(key, []).append(asset.id)
            if key not in self.cache:
                self.loader.request(req)
        pixmap = self.cache.get(key)
        return pixmap if pixmap is not None else self._placeholder_pixmap()

    def _thumbnail_ready(self, key: str, data: bytes) -> None:
        self.cache.put(key, thumbnails.pixmap_from_bytes(data))  # UI thread
        for asset_id in self._by_key.get(key, []):
            row = self._row_of.get(asset_id)
            if row is not None:
                self.dataChanged.emit(
                    self.index(row), self.index(row), [Qt.ItemDataRole.DecorationRole]
                )


class AssetFilterProxy(QSortFilterProxyModel):
    """Filters by status set, role set, pack and text; sorts attention-first."""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.statuses: set[str] | None = None  # None = every status
        self.roles: set[str] | None = None
        self.pack: str | None = None
        self.text = ""
        self.setDynamicSortFilter(True)
        self.sort(0)

    def set_statuses(self, statuses: set[str] | None) -> None:
        self.beginFilterChange()
        self.statuses = None if statuses is None else set(statuses)
        self.endFilterChange()

    def set_roles(self, roles: set[str] | None) -> None:
        self.beginFilterChange()
        self.roles = None if roles is None else set(roles)
        self.endFilterChange()

    def set_pack(self, pack: str | None) -> None:
        self.beginFilterChange()
        self.pack = pack or None
        self.endFilterChange()

    def set_text(self, text: str) -> None:
        self.beginFilterChange()
        self.text = text.strip().casefold()
        self.endFilterChange()

    def filterAcceptsRow(self, row: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        model = self.sourceModel()
        index = model.index(row, 0, parent)
        if self.statuses is not None and model.data(index, StatusRole) not in self.statuses:
            return False
        if self.roles is not None and model.data(index, RoleRole) not in self.roles:
            return False
        if self.pack is not None and model.data(index, PackRole) != self.pack:
            return False
        return not (self.text and self.text not in str(model.data(index, PathRole)).casefold())

    def lessThan(
        self, left: QModelIndex | QPersistentModelIndex, right: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        a = STATUS_PRIORITY.get(model.data(left, StatusRole), 99)
        b = STATUS_PRIORITY.get(model.data(right, StatusRole), 99)
        if a != b:
            return a < b
        return str(model.data(left, AssetIdRole)) < str(model.data(right, AssetIdRole))


class AssetCardDelegate(QStyledItemDelegate):
    """Paints a status strip, the nearest-neighbor thumbnail and the elided file name."""

    STRIP = 5

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: ANN001
        return GRID_SIZE

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: ANN001
        painter.save()
        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        painter.fillRect(rect, palette.highlight() if selected else palette.base())
        status = index.data(StatusRole) or "UNUSED"
        painter.fillRect(
            QRect(rect.left(), rect.top(), self.STRIP, rect.height()),
            QColor(STATUS_COLORS.get(status, STATUS_COLORS["UNUSED"])),
        )
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            area = QRect(rect.left() + self.STRIP + 4, rect.top() + 4, THUMB, THUMB)
            target = self.fit(pixmap.size(), area.size())
            target.moveCenter(area.center())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(target, pixmap)
        text_rect = QRect(rect.left() + self.STRIP + 4, rect.top() + THUMB + 8, THUMB, 20)
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        elided = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, THUMB)
        painter.setPen(palette.highlightedText().color() if selected else palette.text().color())
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided
        )
        painter.restore()

    @staticmethod
    def fit(size: QSize, box: QSize) -> QRect:
        """Rect of ``size`` scaled to fit ``box``: integer scale up when possible."""
        w, h = max(1, size.width()), max(1, size.height())
        scale = min(box.width() / w, box.height() / h)
        if scale >= 1:
            scale = float(int(scale))
        return QRect(0, 0, max(1, round(w * scale)), max(1, round(h * scale)))


class AssetGridView(QListView):
    """The icon grid. Plain C, X and 1-9 key presses are reported through ``quickKey``."""

    quickKey = Signal(str)  # noqa: N815

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setObjectName("assetGrid")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setUniformItemSizes(True)
        self.setGridSize(GRID_SIZE)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(100)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.setItemDelegate(AssetCardDelegate(self))

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        plain = event.modifiers() == Qt.KeyboardModifier.NoModifier
        text = event.text().upper()
        if plain and len(text) == 1 and text in "CX123456789":
            self.quickKey.emit(text)
            event.accept()
            return
        super().keyPressEvent(event)


CHIPS: list[tuple[str, str, set[str] | None]] = [
    ("chipAttention", "Needs attention", set(NEEDS_ATTENTION)),
    ("chipAuto", "Auto-detected", {"AUTO_DETECTED"}),
    ("chipConfirmed", "Confirmed", {"CONFIRMED"}),
    ("chipUnused", "Unused", {"UNUSED"}),
    ("chipAll", "All", None),
]


class AssetGrid(QWidget):
    """Filter bar + grid. Emits ``selectionChanged(list[str])`` with the selected asset ids."""

    selectionChanged = Signal(list)  # noqa: N815

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.model = AssetListModel(self)
        self.proxy = AssetFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.view = AssetGridView()
        self.view.setModel(self.proxy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.chips: dict[str, QPushButton] = {}
        for name, label, statuses in CHIPS:
            chip = QPushButton(self.tr(label))
            chip.setObjectName(name)
            chip.setCheckable(True)
            chip.setAutoExclusive(True)
            chip.clicked.connect(lambda _=False, s=statuses: self.proxy.set_statuses(s))
            bar.addWidget(chip)
            self.chips[name] = chip
        self.role_combo = QComboBox()
        self.role_combo.setObjectName("roleFilter")
        self.pack_combo = QComboBox()
        self.pack_combo.setObjectName("packFilter")
        self.search = QLineEdit()
        self.search.setObjectName("searchFilter")
        self.search.setPlaceholderText(self.tr("Search path…"))
        self.search.setClearButtonEnabled(True)
        bar.addWidget(self.role_combo)
        bar.addWidget(self.pack_combo)
        bar.addWidget(self.search, 1)
        layout.addLayout(bar)
        layout.addWidget(self.view, 1)

        self.chips["chipAttention"].setChecked(True)
        self.proxy.set_statuses(set(NEEDS_ATTENTION))
        self.role_combo.currentIndexChanged.connect(self._on_role)
        self.pack_combo.currentIndexChanged.connect(self._on_pack)
        self.search.textChanged.connect(self.proxy.set_text)
        self.view.selectionModel().selectionChanged.connect(
            lambda *_: self.selectionChanged.emit(self.selected_ids())
        )

    def set_catalog(self, catalog, resolver: PathResolver | None = None) -> None:
        self.model.set_catalog(catalog, resolver)
        self._fill_combos()

    def _fill_combos(self) -> None:
        for combo, items, label in (
            (self.role_combo, self.model.roles(), self.tr("All roles")),
            (self.pack_combo, self.model.packs(), self.tr("All packs")),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(label, None)
            for item in items:
                combo.addItem(item, item)
            combo.blockSignals(False)
        self.proxy.set_roles(None)
        self.proxy.set_pack(None)

    def _on_role(self) -> None:
        value = self.role_combo.currentData()
        self.proxy.set_roles(None if value is None else {value})

    def _on_pack(self) -> None:
        self.proxy.set_pack(self.pack_combo.currentData())

    def selected_ids(self) -> list[str]:
        rows = sorted(i.row() for i in self.view.selectionModel().selectedIndexes())
        return [self.proxy.index(r, 0).data(AssetIdRole) for r in rows]

    def visible_ids(self) -> list[str]:
        return [self.proxy.index(r, 0).data(AssetIdRole) for r in range(self.proxy.rowCount())]

    def select_ids(self, asset_ids: list[str]) -> None:
        selection = self.view.selectionModel()
        selection.clearSelection()
        wanted = set(asset_ids)
        for r in range(self.proxy.rowCount()):
            index = self.proxy.index(r, 0)
            if index.data(AssetIdRole) in wanted:
                selection.select(index, selection.SelectionFlag.Select)
