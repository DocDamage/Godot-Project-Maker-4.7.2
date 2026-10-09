"""The asset grid: a virtualized model/view of every asset with filters and status colors."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from pathlib import Path

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
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
from rpggen.core import labels
from rpggen.gui import thumbnails
from rpggen.gui.widgets.flow_layout import FlowLayout

AssetIdRole = Qt.ItemDataRole.UserRole + 1
StatusRole = Qt.ItemDataRole.UserRole + 2
RoleRole = Qt.ItemDataRole.UserRole + 3
UsageRole = Qt.ItemDataRole.UserRole + 4
ConfidenceRole = Qt.ItemDataRole.UserRole + 5
PackRole = Qt.ItemDataRole.UserRole + 6
PathRole = Qt.ItemDataRole.UserRole + 7
# Grouping by folder (T13.02): a header row has its folder key under HeaderRole (an asset row has
# None there), and every row has the key of its folder under FolderRole.
HeaderRole = Qt.ItemDataRole.UserRole + 8
FolderRole = Qt.ItemDataRole.UserRole + 9
HEADER_HEIGHT = 26
HEADER_ACTIONS = ("confirm", "select", "rule")  # the buttons of a header, left to right


def folder_key(pack_id: str, folder: str) -> str:
    return f"{pack_id}\n{folder}"


def split_folder_key(key: str) -> tuple[str, str]:
    pack_id, _, folder = key.partition("\n")
    return pack_id, folder


STATUS_ORDER = ["CONFLICT", "NEEDS_REVIEW", "MISSING", "AUTO_DETECTED", "CONFIRMED", "UNUSED"]
STATUS_PRIORITY = {s: i for i, s in enumerate(STATUS_ORDER)}
NEEDS_ATTENTION = frozenset({"CONFLICT", "NEEDS_REVIEW", "MISSING"})

# Mirrors the ``status-colors`` block of style.qss (a test keeps both in step).
STATUS_COLORS = {
    "CONFLICT": "#d32f2f",
    "NEEDS_REVIEW": "#ef6c00",
    "MISSING": "#a53fc8",
    "AUTO_DETECTED": "#1976d2",
    "CONFIRMED": "#388e3c",
    "UNUSED": "#8a8a8a",
}

THUMB_SIZES = (64, 96, 128, 192)
THUMB = thumbnails.THUMB_SIZE


def grid_size_for(thumb: int) -> QSize:
    """The cell of the grid for a thumbnail size (the card adds a strip, margins, a confidence
    bar, a name and a role chip)."""
    return QSize(thumb + 16, thumb + 56)


GRID_SIZE = grid_size_for(THUMB)

# A small corner glyph next to the coloured edge, so that the audit is usable without telling
# colours apart.
STATUS_GLYPHS = {
    "CONFIRMED": "✔",
    "NEEDS_REVIEW": "?",
    "AUTO_DETECTED": "·",
    "CONFLICT": "!",
    "MISSING": "∅",
    "UNUSED": "–",
}

PathResolver = Callable[[catalog_mod.Asset], Path | None]


def file_label(asset: catalog_mod.Asset) -> str:
    name = asset.path.rsplit("/", 1)[-1]
    return name + ("#" + asset.id.split("#", 1)[1] if "#" in asset.id else "")


class AssetListModel(QAbstractListModel):
    """One row per asset of the catalog (objects are not rows). With ``grouped`` on, one header
    row per folder follows the asset rows (so an asset keeps its row); the proxy sorts each
    header in front of its folder."""

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
        self.thumb_size = THUMB
        self.grouped = False
        self._folders: list[str] = []  # the folder key of every asset row
        self._headers: list[str] = []  # the folder keys, sorted: the header rows
        self._header_row: dict[str, int] = {}
        self._folder_rows: dict[str, list[int]] = {}

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
        self._index_folders()
        self.endResetModel()

    def _index_folders(self) -> None:
        catalog = self.catalog
        self._folders = (
            [folder_key(a.pack_id, catalog_mod.folder_of(catalog, a)) for a in self._assets]
            if catalog is not None
            else []
        )
        self._folder_rows = {}
        for row, key in enumerate(self._folders):
            self._folder_rows.setdefault(key, []).append(row)
        self._headers = sorted(self._folder_rows, key=split_folder_key) if self.grouped else []
        count = len(self._assets)
        self._header_row = {key: count + i for i, key in enumerate(self._headers)}

    def set_grouped(self, on: bool) -> None:
        if on == self.grouped:
            return
        self.beginResetModel()
        self.grouped = on
        self._index_folders()
        self.endResetModel()

    def folder_rows(self, key: str) -> list[int]:
        """The asset rows of a folder."""
        return self._folder_rows.get(key, [])

    def folder_keys(self) -> list[str]:
        """The folders that have a header, in the order of the headers."""
        return list(self._headers)

    def is_header(self, row: int) -> bool:
        return row >= len(self._assets)

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
            header = self._header_row.get(self._folders[row])
            if header is not None:  # its counts changed, and whether the filter shows it
                self.dataChanged.emit(self.index(header), self.index(header))

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._assets) + len(self._headers)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if index.isValid() and self.is_header(index.row()):
            return Qt.ItemFlag.ItemIsEnabled  # a header is clicked, never selected
        return super().flags(index)

    def asset_at(self, row: int) -> catalog_mod.Asset:
        return self._assets[row]

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for asset in self._assets:
            counts[asset.status] = counts.get(asset.status, 0) + 1
        return counts

    def set_thumb_size(self, size: int) -> None:
        """Another thumbnail size: the pictures are asked for again (the key has the size)."""
        if size == self.thumb_size:
            return
        self.thumb_size = size
        self._keys.clear()
        self._by_key.clear()
        if self._assets:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._assets) - 1), [Qt.ItemDataRole.DecorationRole]
            )

    def row_of(self, asset_id: str) -> int | None:
        return self._row_of.get(asset_id)

    def roles(self) -> list[str]:
        return sorted({str(f.get("role")) for f in self._facets if f.get("role")})

    def packs(self) -> list[str]:
        return sorted({a.pack_id for a in self._assets})

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return None
        if self.is_header(index.row()):
            key = self._headers[index.row() - len(self._assets)]
            pack_id, folder = split_folder_key(key)
            if role in (HeaderRole, FolderRole):
                return key
            if role == PackRole:
                return pack_id
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                return f"{pack_id} / {folder}" if folder else pack_id
            return None
        if role == FolderRole:
            return self._folders[index.row()]
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
            duration = (facets.get("audio") or {}).get("duration_s")
            req = thumbnails.request_for(
                asset.sha256, path, facets, self.thumb_size, kind=asset.kind, duration=duration
            )
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
        self.only_ids: set[str] | None = None  # "Changed in update": just these assets
        self.collapsed: set[str] = set()  # folder keys whose assets are folded away
        self._counts: dict[str, tuple[int, int, int]] = {}
        self.setDynamicSortFilter(True)
        self.sort(0)

    def setSourceModel(self, model: QAbstractItemModel) -> None:  # noqa: N802
        super().setSourceModel(model)
        model.dataChanged.connect(lambda *_: self._counts.clear())
        model.modelReset.connect(self._on_source_reset)

    def _on_source_reset(self) -> None:
        self._counts.clear()
        self.collapsed &= set(self.sourceModel().folder_keys())  # type: ignore[attr-defined]

    @contextlib.contextmanager
    def _filter_change(self) -> Iterator[None]:
        """Change what the filter accepts: ``beginFilterChange`` / ``endFilterChange`` where Qt
        has them (6.10 deprecates ``invalidateFilter``), else ``invalidateFilter`` (PySide6 6.7
        and 6.8, which the project supports)."""
        self._counts.clear()
        begin = getattr(self, "beginFilterChange", None)
        if begin is None:
            yield
            self.invalidateFilter()
            return
        begin()
        try:
            yield
        finally:
            self.endFilterChange()

    def set_statuses(self, statuses: set[str] | None) -> None:
        with self._filter_change():
            self.statuses = None if statuses is None else set(statuses)

    def set_roles(self, roles: set[str] | None) -> None:
        with self._filter_change():
            self.roles = None if roles is None else set(roles)

    def set_pack(self, pack: str | None) -> None:
        with self._filter_change():
            self.pack = pack or None

    def set_text(self, text: str) -> None:
        with self._filter_change():
            self.text = text.strip().casefold()

    def set_only_ids(self, ids: set[str] | None) -> None:
        with self._filter_change():
            self.only_ids = None if ids is None else set(ids)

    def set_collapsed(self, key: str, collapsed: bool) -> None:
        with self._filter_change():
            (self.collapsed.add if collapsed else self.collapsed.discard)(key)

    def passing_rows(self, key: str) -> list[int]:
        """The source rows of a folder's assets that pass the filter (folded away or not)."""
        model = self.sourceModel()
        return [r for r in model.folder_rows(key) if self._accepts_asset(r, QModelIndex())]  # type: ignore[attr-defined]

    def folder_counts(self, key: str) -> tuple[int, int, int]:
        """``(need attention, confirmed, all)`` of the folder's assets that pass the filter."""
        if key not in self._counts:
            model = self.sourceModel()
            statuses = [model.data(model.index(r, 0), StatusRole) for r in self.passing_rows(key)]
            self._counts[key] = (
                sum(1 for s in statuses if s in NEEDS_ATTENTION),
                sum(1 for s in statuses if s == "CONFIRMED"),
                len(statuses),
            )
        return self._counts[key]

    def filterAcceptsRow(self, row: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        model = self.sourceModel()
        key = model.data(model.index(row, 0, parent), HeaderRole)
        if key is not None:  # a header shows while one of its assets passes the filter
            return any(self._accepts_asset(r, parent) for r in model.folder_rows(key))  # type: ignore[attr-defined]
        if self.collapsed and model.data(model.index(row, 0, parent), FolderRole) in self.collapsed:
            return False
        return self._accepts_asset(row, parent)

    def _accepts_asset(self, row: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        model = self.sourceModel()
        index = model.index(row, 0, parent)
        if self.only_ids is not None and model.data(index, AssetIdRole) not in self.only_ids:
            return False
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
        if getattr(model, "grouped", False):  # folder by folder, each header first
            left_folder = split_folder_key(str(model.data(left, FolderRole)))
            right_folder = split_folder_key(str(model.data(right, FolderRole)))
            if left_folder != right_folder:
                return left_folder < right_folder
            left_header = model.data(left, HeaderRole) is not None
            if left_header or model.data(right, HeaderRole) is not None:
                return left_header
        a = STATUS_PRIORITY.get(model.data(left, StatusRole), 99)
        b = STATUS_PRIORITY.get(model.data(right, StatusRole), 99)
        if a != b:
            return a < b
        return str(model.data(left, AssetIdRole)) < str(model.data(right, AssetIdRole))


class AssetCardDelegate(QStyledItemDelegate):
    """Paints a status strip, the nearest-neighbor thumbnail and the elided file name; and, when
    the grid is grouped by folder, the header rows with their three buttons."""

    STRIP = 5

    headerAction = Signal(str, str)  # noqa: N815 - folder key, one of HEADER_ACTIONS
    headerToggled = Signal(str)  # noqa: N815 - a click on the header itself: fold or unfold

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.thumb = THUMB
        self.header_width = 0  # the view sets it to its viewport's width

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: ANN001
        if index.data(HeaderRole) is not None:
            # a little less than the row, so the header starts a line and nothing fits beside it
            return QSize(max(120, self.header_width - 4), HEADER_HEIGHT)
        return grid_size_for(self.thumb)

    # ------------------------------------------------------------------ folder headers

    def header_labels(self) -> dict[str, str]:
        return {
            "confirm": self.tr("Confirm all"),
            "select": self.tr("Select all"),
            "rule": self.tr("Make rule…"),
        }

    def header_buttons(self, rect: QRect, metrics) -> dict[str, QRect]:  # noqa: ANN001
        """Where the three buttons of a header are, right-aligned in its row."""
        labels_by_action = self.header_labels()
        out: dict[str, QRect] = {}
        right = rect.right() - 4
        for action in reversed(HEADER_ACTIONS):
            width = metrics.horizontalAdvance(labels_by_action[action]) + 16
            out[action] = QRect(right - width, rect.top() + 3, width, rect.height() - 6)
            right -= width + 4
        return {action: out[action] for action in HEADER_ACTIONS}

    def header_text(self, index) -> str:  # noqa: ANN001
        """ "▾ pack / folder — 4 need attention · 12 confirmed"."""
        key = str(index.data(HeaderRole))
        proxy = index.model()
        attention, confirmed, total = proxy.folder_counts(key)
        mark = "▸" if key in proxy.collapsed else "▾"
        counts = self.tr("{0} need attention · {1} confirmed · {2} shown").format(
            attention, confirmed, total
        )
        return f"{mark} {index.data(Qt.ItemDataRole.DisplayRole)} — {counts}"

    def _paint_header(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: ANN001
        rect = option.rect.adjusted(2, 2, -2, -2)
        palette = option.palette
        painter.fillRect(rect, palette.alternateBase())
        buttons = self.header_buttons(rect, painter.fontMetrics())
        text_rect = QRect(rect.left() + 6, rect.top(), rect.width(), rect.height())
        text_rect.setRight(min(b.left() for b in buttons.values()) - 8)
        painter.setPen(palette.text().color())
        text = painter.fontMetrics().elidedText(
            self.header_text(index), Qt.TextElideMode.ElideMiddle, text_rect.width()
        )
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text
        )
        labels_by_action = self.header_labels()
        for action, button in buttons.items():
            painter.setPen(palette.mid().color())
            painter.setBrush(palette.button())
            painter.drawRoundedRect(button, 3, 3)
            painter.setPen(palette.buttonText().color())
            painter.drawText(button, Qt.AlignmentFlag.AlignCenter, labels_by_action[action])

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: ANN001, N802
        key = index.data(HeaderRole)
        if key is None:
            return super().editorEvent(event, model, option, index)
        if event.type() != QEvent.Type.MouseButtonRelease or not isinstance(event, QMouseEvent):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        rect = option.rect.adjusted(2, 2, -2, -2)
        metrics = option.fontMetrics
        for action, button in self.header_buttons(rect, metrics).items():
            if button.contains(event.position().toPoint()):
                self.headerAction.emit(str(key), action)
                return True
        self.headerToggled.emit(str(key))
        return True

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: ANN001
        painter.save()
        if index.data(HeaderRole) is not None:
            self._paint_header(painter, option, index)
            painter.restore()
            return
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
            area = QRect(rect.left() + self.STRIP + 4, rect.top() + 4, self.thumb, self.thumb)
            target = self.fit(pixmap.size(), area.size())
            target.moveCenter(area.center())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(target, pixmap)
        if status in ("AUTO_DETECTED", "NEEDS_REVIEW"):
            self._paint_confidence(painter, rect, index.data(ConfidenceRole), status)
        glyph = STATUS_GLYPHS.get(status, "")
        if glyph:
            painter.setPen(QColor(STATUS_COLORS.get(status, STATUS_COLORS["UNUSED"])))
            painter.fillRect(QRect(rect.right() - 16, rect.top() + 2, 14, 14), palette.base())
            painter.drawText(
                QRect(rect.right() - 16, rect.top() + 2, 14, 14),
                Qt.AlignmentFlag.AlignCenter,
                glyph,
            )
        text_rect = QRect(
            rect.left() + self.STRIP + 4, rect.top() + self.thumb + 10, self.thumb, 18
        )
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        elided = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, self.thumb)
        painter.setPen(palette.highlightedText().color() if selected else palette.text().color())
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided
        )
        self._paint_chip(
            painter,
            rect,
            index,
            palette.highlightedText().color() if selected else palette.text().color(),
        )
        painter.restore()

    @staticmethod
    def chip_text(index) -> str:  # noqa: ANN001
        """The friendly role name shown on the card ("" when the asset has no role)."""
        role = str(index.data(RoleRole) or "")
        return "" if role in ("", "NONE") else labels.role_label(role)

    def chip_rect(self, rect: QRect) -> QRect:
        return QRect(rect.left() + self.STRIP + 4, rect.top() + self.thumb + 30, self.thumb, 16)

    def _paint_chip(self, painter: QPainter, rect: QRect, index, ink: QColor) -> None:  # noqa: ANN001
        text = self.chip_text(index)
        if not text:
            return
        chip = self.chip_rect(rect)
        base = QColor(
            STATUS_COLORS.get(index.data(StatusRole) or "UNUSED", STATUS_COLORS["UNUSED"])
        )
        fill = QColor(base)
        fill.setAlpha(46)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(chip, 7, 7)
        painter.setPen(ink)
        elided = painter.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideRight, chip.width() - 10
        )
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, elided)

    def _paint_confidence(self, painter: QPainter, rect: QRect, confidence, status: str) -> None:  # noqa: ANN001
        """A thin bar under the picture: its length is how sure the detection was."""
        try:
            value = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            return
        left = rect.left() + self.STRIP + 4
        top = rect.top() + self.thumb + 6
        painter.fillRect(QRect(left, top, self.thumb, 3), QColor(128, 128, 128, 70))
        painter.fillRect(
            QRect(left, top, max(1, round(self.thumb * value)), 3),
            QColor(STATUS_COLORS.get(status, STATUS_COLORS["UNUSED"])),
        )

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
        self.setToolTip("")
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(100)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.card_delegate = AssetCardDelegate(self)
        self.setItemDelegate(self.card_delegate)
        self.grouped = False

    def set_thumb_size(self, size: int) -> None:
        self.card_delegate.thumb = size
        self._apply_layout()

    def set_grouped(self, on: bool) -> None:
        """With folder headers the rows have two sizes (a header is as wide as the view), so
        the fixed grid is given up for the delegate's size hints while grouping is on."""
        self.grouped = on
        self._apply_layout()

    def _apply_layout(self) -> None:
        self.card_delegate.header_width = self.viewport().width()
        self.setUniformItemSizes(not self.grouped)
        self.setGridSize(QSize() if self.grouped else grid_size_for(self.card_delegate.thumb))
        self.doItemsLayout()

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        if self.grouped and self.card_delegate.header_width != self.viewport().width():
            self.card_delegate.header_width = self.viewport().width()
            self.scheduleDelayedItemsLayout()
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        modifiers = event.modifiers()
        plain = modifiers == Qt.KeyboardModifier.NoModifier
        text = event.text().upper()
        if plain and len(text) == 1 and text in "CX123456789N":
            self.quickKey.emit(text)
            event.accept()
            return
        if event.key() == Qt.Key.Key_N and modifiers == Qt.KeyboardModifier.ShiftModifier:
            self.quickKey.emit("SHIFT+N")
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
COMBO_MAX_WIDTH = 240
LISTED_CHIP = "chipListed"  # shown while a list of assets is shown (from the results page)
CHANGED_CHIP = "chipChanged"  # shown only after a pack update


class AssetGrid(QWidget):
    """Filter bar + grid. Emits ``selectionChanged(list[str])`` with the selected asset ids."""

    selectionChanged = Signal(list)  # noqa: N815
    confirmAutoRequested = Signal()  # noqa: N815
    shortcutsRequested = Signal()  # noqa: N815
    thumbSizeChanged = Signal(int)  # noqa: N815
    groupedChanged = Signal(bool)  # noqa: N815
    folderConfirmRequested = Signal(str)  # noqa: N815 - folder key: a header's Confirm all
    folderRuleRequested = Signal(str)  # noqa: N815 - folder key: a header's Make rule…

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.model = AssetListModel(self)
        self.proxy = AssetFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.view = AssetGridView()
        self.view.setModel(self.proxy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = FlowLayout()  # row 1: the status chips with their counts (wraps when narrow)
        self.chips: dict[str, QPushButton] = {}
        self._chip_labels: dict[str, str] = {}
        for name, label, statuses in CHIPS:
            chip = QPushButton(self.tr(label))
            chip.setObjectName(name)
            chip.setCheckable(True)
            chip.setAutoExclusive(True)
            chip.setToolTip(self.tr("Show only the assets with this status"))
            chip.clicked.connect(lambda _=False, s=statuses: self._show_statuses(s))
            bar.addWidget(chip)
            self.chips[name] = chip
            self._chip_labels[name] = label
        changed = QPushButton(self.tr("Changed in update"))
        changed.setObjectName(CHANGED_CHIP)
        changed.setCheckable(True)
        changed.setAutoExclusive(True)
        changed.setVisible(False)
        changed.clicked.connect(self._show_changed)
        bar.addWidget(changed)
        self.chips[CHANGED_CHIP] = changed
        listed = QPushButton(self.tr("From the results"))
        listed.setObjectName(LISTED_CHIP)
        listed.setCheckable(True)
        listed.setAutoExclusive(True)
        listed.setVisible(False)
        listed.setToolTip(self.tr("The assets the generation report named"))
        listed.clicked.connect(lambda: self.proxy.set_only_ids(self.listed_ids))
        bar.addWidget(listed)
        self.chips[LISTED_CHIP] = listed
        self.listed_ids: set[str] = set()
        self.changed_ids: set[str] = set()
        self.confirm_auto_button = QPushButton(self.tr("Confirm all auto-detected"))
        self.confirm_auto_button.setObjectName("confirmAutoButton")
        self.confirm_auto_button.setToolTip(
            self.tr("Mark every auto-detected asset as confirmed (one undo step)")
        )
        self.confirm_auto_button.setVisible(False)
        self.confirm_auto_button.clicked.connect(self.confirmAutoRequested)
        bar.addWidget(self.confirm_auto_button)
        self.help_button = QPushButton(self.tr("Shortcuts"))
        self.help_button.setObjectName("shortcutsButton")
        self.help_button.setToolTip(self.tr("Keyboard shortcuts of this page"))
        self.help_button.clicked.connect(self.shortcutsRequested)
        bar.addWidget(self.help_button)
        layout.addLayout(bar)
        bar2 = QHBoxLayout()  # row 2: filters, search and the thumbnail size
        self.role_combo = QComboBox()
        self.role_combo.setObjectName("roleFilter")
        self.role_combo.setToolTip(self.tr("Show only assets with this role"))
        self.pack_combo = QComboBox()
        self.pack_combo.setObjectName("packFilter")
        self.pack_combo.setToolTip(self.tr("Show only the assets of one pack"))
        self.search = QLineEdit()
        self.search.setObjectName("searchFilter")
        self.search.setPlaceholderText(self.tr("Search by name or folder"))
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(120)
        for combo in (self.role_combo, self.pack_combo):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        bar2.addWidget(self.role_combo)
        bar2.addWidget(self.pack_combo)
        bar2.addWidget(self.search, 1)
        self.group_button = QPushButton(self.tr("Group by folder"))
        self.group_button.setObjectName("groupByFolder")
        self.group_button.setCheckable(True)
        self.group_button.setToolTip(
            self.tr("A header per folder, with Confirm all, Select all and Make rule…")
        )
        self.group_button.clicked.connect(lambda on: self.set_grouped(bool(on)))
        bar2.addWidget(self.group_button)
        layout.addLayout(bar2)
        self.view.card_delegate.headerToggled.connect(self.toggle_folder)
        self.view.card_delegate.headerAction.connect(self._on_header_action)
        layout.addWidget(self.view, 1)
        self.model.modelReset.connect(self._update_counts)
        self.model.dataChanged.connect(self._on_model_data_changed)

        self.chips["chipAttention"].setChecked(True)
        self.proxy.set_statuses(set(NEEDS_ATTENTION))
        self.chips["chipAuto"].toggled.connect(self.confirm_auto_button.setVisible)
        self.role_combo.currentIndexChanged.connect(self._on_role)
        self.pack_combo.currentIndexChanged.connect(self._on_pack)
        self.search.textChanged.connect(self.proxy.set_text)
        self.view.selectionModel().selectionChanged.connect(
            lambda *_: self.selectionChanged.emit(self.selected_ids())
        )

    # ------------------------------------------------------------------ counts and size

    def _on_model_data_changed(self, _top, _bottom, roles=()) -> None:  # noqa: ANN001
        if roles and list(roles) == [Qt.ItemDataRole.DecorationRole]:
            return  # a thumbnail arrived: the statuses are the same
        self._update_counts()

    def _update_counts(self) -> None:
        """ "Needs attention 12": every chip shows how many assets it holds."""
        counts = self.model.status_counts()
        total = sum(counts.values())
        attention = sum(n for s, n in counts.items() if s in NEEDS_ATTENTION)
        numbers = {
            "chipAttention": attention,
            "chipAuto": counts.get("AUTO_DETECTED", 0),
            "chipConfirmed": counts.get("CONFIRMED", 0),
            "chipUnused": counts.get("UNUSED", 0),
            "chipAll": total,
        }
        for name, n in numbers.items():
            self.chips[name].setText(f"{self.tr(self._chip_labels[name])} {n}")

    def set_thumb_size(self, size: int) -> None:
        """The size comes from View > Thumbnail size (and Ctrl+= / Ctrl+-)."""
        if size not in THUMB_SIZES:
            return
        self.model.set_thumb_size(size)
        self.view.set_thumb_size(size)
        self.thumbSizeChanged.emit(size)

    # ------------------------------------------------------------------ folders (T13.02)

    def set_grouped(self, on: bool) -> None:
        """A header row per folder, or the flat grid."""
        self.group_button.setChecked(on)
        if on == self.model.grouped:
            return
        selected = self.selected_ids()
        self.model.set_grouped(on)
        self.view.set_grouped(on)
        self.proxy.invalidate()
        self.select_ids(selected)
        self.groupedChanged.emit(on)

    def header_keys(self) -> list[str]:
        """The folder keys of the headers the grid shows, top to bottom."""
        rows = range(self.proxy.rowCount())
        keys = [self.proxy.index(r, 0).data(HeaderRole) for r in rows]
        return [k for k in keys if k is not None]

    def folder_ids(self, key: str) -> list[str]:
        """The assets of a folder that pass the filter, in the model's order."""
        return [self.model.asset_at(r).id for r in self.proxy.passing_rows(key)]

    def toggle_folder(self, key: str) -> None:
        self.proxy.set_collapsed(key, key not in self.proxy.collapsed)

    def _on_header_action(self, key: str, action: str) -> None:
        if action == "confirm":
            self.folderConfirmRequested.emit(key)
        elif action == "rule":
            self.folderRuleRequested.emit(key)
        elif action == "select":
            self.proxy.set_collapsed(key, False)
            self.select_ids(self.folder_ids(key))

    # ------------------------------------------------------------------ the review queue

    def attention_ids(self) -> list[str]:
        """The assets that need attention in the order the grid shows them (whatever the chip)."""
        out = []
        for r in range(self.proxy.rowCount()):
            index = self.proxy.index(r, 0)
            if index.data(StatusRole) in NEEDS_ATTENTION:
                out.append(index.data(AssetIdRole))
        return out

    def select_next_attention(self, forward: bool = True) -> str | None:
        """Selects the next (or previous) asset that needs attention, wrapping around; returns
        its id, or None when nothing needs attention here."""
        queue = self.attention_ids()
        if not queue:
            return None
        current = self.selected_ids()
        order = self.visible_ids()
        position = order.index(current[0]) if current and current[0] in order else -1
        ranked = {asset_id: order.index(asset_id) for asset_id in queue}
        if forward:
            later = [i for i in queue if ranked[i] > position]
            target = later[0] if later else queue[0]
        else:
            earlier = [i for i in queue if ranked[i] < position]
            target = earlier[-1] if earlier else queue[-1]
        self.select_ids([target])
        self.scroll_to(target)
        return target

    def scroll_to(self, asset_id: str) -> None:
        for r in range(self.proxy.rowCount()):
            index = self.proxy.index(r, 0)
            if index.data(AssetIdRole) == asset_id:
                self.view.scrollTo(index)
                return

    def advance_after(self, before_order: list[str], edited_id: str) -> str | None:
        """After one asset was confirmed or excluded: select the next one that needs attention
        after it in the order the grid had before the edit."""
        queue = set(self.attention_ids())
        if not queue:
            return None
        start = before_order.index(edited_id) if edited_id in before_order else -1
        for asset_id in [*before_order[start + 1 :], *before_order[: max(start, 0)]]:
            if asset_id in queue:
                self.select_ids([asset_id])
                self.scroll_to(asset_id)
                return asset_id
        return None

    def _show_statuses(self, statuses: set[str] | None) -> None:
        self.proxy.set_only_ids(None)
        self.proxy.set_statuses(statuses)

    def _show_changed(self) -> None:
        self.proxy.set_statuses(None)
        self.proxy.set_only_ids(self.changed_ids)

    def show_ids(self, asset_ids: set[str]) -> None:
        """Show only these assets, whatever their status ("Show these assets" on Results); any
        other chip puts the usual filters back."""
        self.listed_ids = set(asset_ids)
        chip = self.chips[LISTED_CHIP]
        chip.setVisible(True)
        chip.setChecked(True)
        self.proxy.set_statuses(None)
        self.proxy.set_only_ids(self.listed_ids)

    def set_changed(self, asset_ids: set[str]) -> None:
        """Offer the "Changed in update" filter (added, resized, missing assets) and open on it."""
        self.changed_ids = set(asset_ids)
        chip = self.chips[CHANGED_CHIP]
        chip.setVisible(bool(self.changed_ids))
        if self.changed_ids:
            chip.setChecked(True)
            self._show_changed()
        elif chip.isChecked():
            self.chips["chipAttention"].setChecked(True)
            self._show_statuses(set(NEEDS_ATTENTION))

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
                combo.addItem(labels.role_label(item) if combo is self.role_combo else item, item)
                if combo is self.role_combo:
                    combo.setItemData(
                        combo.count() - 1, labels.role_help(item), Qt.ItemDataRole.ToolTipRole
                    )
            combo.blockSignals(False)
            # wide enough for the longest item, but not wider than a filter should be
            combo.setMinimumWidth(0)
            combo.setMinimumWidth(min(combo.sizeHint().width(), COMBO_MAX_WIDTH))
            combo.setToolTip(combo.currentText() if combo.count() else "")
        self.proxy.set_roles(None)
        self.proxy.set_pack(None)

    def _on_role(self) -> None:
        self.role_combo.setToolTip(self.role_combo.currentText())
        value = self.role_combo.currentData()
        self.proxy.set_roles(None if value is None else {value})

    def _on_pack(self) -> None:
        self.pack_combo.setToolTip(self.pack_combo.currentText())
        self.proxy.set_pack(self.pack_combo.currentData())

    def selected_ids(self) -> list[str]:
        rows = sorted(i.row() for i in self.view.selectionModel().selectedIndexes())
        return [self.proxy.index(r, 0).data(AssetIdRole) for r in rows]

    def visible_ids(self) -> list[str]:
        """The assets the grid shows, in its order (folder headers are not assets)."""
        ids = (self.proxy.index(r, 0).data(AssetIdRole) for r in range(self.proxy.rowCount()))
        return [i for i in ids if i is not None]

    def select_ids(self, asset_ids: list[str]) -> None:
        selection = self.view.selectionModel()
        selection.clearSelection()
        wanted = set(asset_ids)
        for r in range(self.proxy.rowCount()):
            index = self.proxy.index(r, 0)
            if index.data(AssetIdRole) in wanted:
                selection.select(index, selection.SelectionFlag.Select)
