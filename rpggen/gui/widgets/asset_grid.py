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
    QRectF,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core import labels
from rpggen.gui import icons, theme, thumbnails
from rpggen.gui.widgets import buttons
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
# A recolour variant (T13.18) has the id of its source here; every other asset None.
VariantRole = Qt.ItemDataRole.UserRole + 10
VARIANT_GLYPH = "⧉"
# Colour variants a pack ships as files (T16.21): the first picture of a group has the number
# of its colours under ColourCountRole, every other one the id of the first under ColourOfRole.
ColourCountRole = Qt.ItemDataRole.UserRole + 11
ColourOfRole = Qt.ItemDataRole.UserRole + 12
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
        self.ratio = 1.0  # the device pixel ratio of the screen the grid is on (T13.10)
        self.grouped = False
        self.by_pack = False  # the headers are the packs, not their folders (the picker)
        self._folders: list[str] = []  # the folder key of every asset row
        self._headers: list[str] = []  # the folder keys, sorted: the header rows
        self._header_row: dict[str, int] = {}
        self._folder_rows: dict[str, list[int]] = {}
        self._colours: dict[str, list[str]] = {}  # a group's first picture -> its other colours
        self._colour_of: dict[str, str] = {}  # every other colour -> the group's first picture

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
        self._variant_names = {
            str(v.get("id")): str(v.get("name", "")) for v in (catalog.variants if catalog else [])
        }
        self._keys.clear()
        self._by_key.clear()
        self._index_folders()
        self._colours = catalog_mod.colour_groups(catalog) if catalog else {}
        self._colour_of = {m: first for first, rest in self._colours.items() for m in rest}
        self.endResetModel()

    def colour_first(self, asset_id: str) -> str | None:
        """The first picture of the colour group ``asset_id`` is another colour of."""
        return self._colour_of.get(asset_id)

    def colour_members(self, asset_id: str) -> list[str]:
        """The other colours of the group whose first picture ``asset_id`` is."""
        return list(self._colours.get(asset_id, []))

    def _index_folders(self) -> None:
        catalog = self.catalog
        self._folders = (
            [
                folder_key(a.pack_id, "" if self.by_pack else catalog_mod.folder_of(catalog, a))
                for a in self._assets
            ]
            if catalog is not None
            else []
        )
        self._folder_rows = {}
        for row, key in enumerate(self._folders):
            self._folder_rows.setdefault(key, []).append(row)
        self._headers = sorted(self._folder_rows, key=split_folder_key) if self.grouped else []
        count = len(self._assets)
        self._header_row = {key: count + i for i, key in enumerate(self._headers)}

    def set_grouped(self, on: bool, by_pack: bool = False) -> None:
        if on == self.grouped and by_pack == self.by_pack:
            return
        self.beginResetModel()
        self.grouped = on
        self.by_pack = by_pack
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

    def set_device_ratio(self, ratio: float) -> None:
        """The grid is on a screen with another scaling: the pictures are asked for again, for
        that many device pixels."""
        ratio = round(ratio, 3) if ratio > 0 else 1.0
        if ratio == self.ratio:
            return
        self.ratio = ratio
        self._keys.clear()
        self._by_key.clear()
        self.cache = thumbnails.ThumbnailCache()
        if self._assets:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._assets) - 1), [Qt.ItemDataRole.DecorationRole]
            )

    def accessible_text(self, row: int) -> str:
        """What a screen reader says for a card: "hero.png, Sprite or character, Player,
        confirmed" (the file, its usage, its role, its status in words)."""
        asset, facets = self._assets[row], self._facets[row]
        role = str(facets.get("role") or "")
        parts = [
            file_label(asset),
            labels.usage_label(str(facets.get("usage") or "")),
            "" if role in ("", "NONE") else labels.role_label(role),
            asset.status.replace("_", " ").lower(),
        ]
        if asset.id in self._colours:
            parts.append(self.tr("{0} colour variants").format(len(self._colours[asset.id]) + 1))
        return ", ".join(p for p in parts if p)

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
            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.ToolTipRole,
                Qt.ItemDataRole.AccessibleTextRole,
            ):
                return f"{pack_id} / {folder}" if folder else pack_id
            return None
        if role == FolderRole:
            return self._folders[index.row()]
        asset = self._assets[index.row()]
        facets = self._facets[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._variant_names.get(asset.id) or file_label(asset)
        if role == VariantRole:
            return facets.get("derived_from")
        if role == ColourCountRole:
            return len(self._colours[asset.id]) + 1 if asset.id in self._colours else None
        if role == ColourOfRole:
            return self._colour_of.get(asset.id)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._pixmap_for(asset, facets)
        if role == Qt.ItemDataRole.ToolTipRole:
            sure = f"  {round(asset.confidence * 100)}%" if asset.status != "CONFIRMED" else ""
            tip = f"{asset.path}\n{asset.status}  {facets.get('role', '-')}{sure}"
            if facets.get("derived_from"):
                tip += "\n" + f"{VARIANT_GLYPH} variant of {facets['derived_from']}"
            if asset.id in self._colours:
                count = len(self._colours[asset.id]) + 1
                tip += "\n" + VARIANT_GLYPH + " " + self.tr("{0} colour variants").format(count)
            elif asset.id in self._colour_of:
                first = self._colour_of[asset.id]
                tip += "\n" + VARIANT_GLYPH + " " + self.tr("a colour variant of {0}").format(first)
            return tip
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self.accessible_text(index.row())
        if role == Qt.ItemDataRole.AccessibleDescriptionRole:
            return asset.path
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
                asset.sha256,
                path,
                facets,
                self.thumb_size,
                kind=asset.kind,
                duration=duration,
                ratio=self.ratio,
            )
            key = req.key
            self._keys[asset.id] = key
            self._by_key.setdefault(key, []).append(asset.id)
            if key not in self.cache:
                self.loader.request(req)
        pixmap = self.cache.get(key)
        return pixmap if pixmap is not None else self._placeholder_pixmap()

    def _thumbnail_ready(self, key: str, data: bytes) -> None:
        self.cache.put(key, thumbnails.pixmap_from_bytes(data, self.ratio))  # UI thread
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
        self.rank: dict[str, int] | None = None  # asset id -> place: this order, not the status'
        # Colour variants (T16.21): with ``fold_colours`` the first picture of a group is the
        # card of every colour that is in the same state; ``unfolded`` are the groups shown whole.
        self.fold_colours = False
        self.unfolded: set[str] = set()
        self._counts: dict[str, tuple[int, int, int]] = {}
        self.setDynamicSortFilter(True)
        self.sort(0)

    def setSourceModel(self, model: QAbstractItemModel) -> None:  # noqa: N802
        super().setSourceModel(model)
        model.dataChanged.connect(lambda *_: self._counts.clear())
        model.dataChanged.connect(self._on_source_data)
        model.modelReset.connect(self._on_source_reset)

    def _on_source_reset(self) -> None:
        self._counts.clear()
        self.collapsed &= set(self.sourceModel().folder_keys())  # type: ignore[attr-defined]
        self.unfolded = {i for i in self.unfolded if self.sourceModel().colour_members(i)}  # type: ignore[attr-defined]

    def _on_source_data(self, top: QModelIndex, bottom: QModelIndex, roles=()) -> None:  # noqa: ANN001
        """The card of a colour group changed its state: which colours it stands for is asked
        again (Qt filters only the row that changed)."""
        if not self.fold_colours or (roles and list(roles) == [Qt.ItemDataRole.DecorationRole]):
            return
        model = self.sourceModel()
        rows = range(top.row(), bottom.row() + 1)
        if any(model.data(model.index(r, 0), ColourCountRole) is not None for r in rows):
            with self._filter_change():
                pass

    def set_fold_colours(self, on: bool) -> None:
        with self._filter_change():
            self.fold_colours = on

    def set_unfolded(self, asset_id: str, shown: bool) -> None:
        """Show every colour of a group as a card of its own, or fold them again."""
        with self._filter_change():
            (self.unfolded.add if shown else self.unfolded.discard)(asset_id)

    def is_folded(
        self, row: int, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> bool:
        """True for a colour variant its group's card stands for: the first picture of the
        group is shown, and this one has its status and its role (and its folder, when the
        grid is grouped). What differs from its card, or has no card with this filter, is a
        card of its own, so nothing that needs a look is hidden. A list of assets and an order
        of its own (the results' list, the picker) show every picture."""
        if not self.fold_colours or self.only_ids is not None or self.rank is not None:
            return False
        parent = QModelIndex() if parent is None else parent
        model = self.sourceModel()
        index = model.index(row, 0, parent)
        first = model.data(index, ColourOfRole)
        if first is None or first in self.unfolded:
            return False
        first_row = model.row_of(first)  # type: ignore[attr-defined]
        if first_row is None:
            return False
        card = model.index(first_row, 0, parent)
        same = [StatusRole, RoleRole, *([FolderRole] if getattr(model, "grouped", False) else [])]
        if any(model.data(index, r) != model.data(card, r) for r in same):
            return False
        return self._accepts_asset(first_row, parent)

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
        if self.fold_colours and self.is_folded(row, parent):
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
        if self.rank is not None:
            last = len(self.rank)
            left_rank = self.rank.get(str(model.data(left, AssetIdRole)), last)
            right_rank = self.rank.get(str(model.data(right, AssetIdRole)), last)
            if left_rank != right_rank:
                return left_rank < right_rank
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
        self.header_actions: tuple[str, ...] = HEADER_ACTIONS  # () for headers without buttons

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
        for action in reversed(self.header_actions):
            width = metrics.horizontalAdvance(labels_by_action[action]) + 16
            out[action] = QRect(right - width, rect.top() + 3, width, rect.height() - 6)
            right -= width + 4
        return {action: out[action] for action in self.header_actions}

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
        text_rect.setRight(min((b.left() for b in buttons.values()), default=rect.right()) - 8)
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
        # a cell is a small card (T15.12): rounded corners; the strip and the glyph say the status
        shape = QPainterPath()
        radius = theme.px("radius_control")
        shape.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(shape)
        painter.fillRect(rect, palette.highlight() if selected else theme.color("surface"))
        status = index.data(StatusRole) or "UNUSED"
        painter.fillRect(
            QRect(rect.left(), rect.top(), self.STRIP, rect.height()),
            QColor(STATUS_COLORS.get(status, STATUS_COLORS["UNUSED"])),
        )
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            area = QRect(rect.left() + self.STRIP + 4, rect.top() + 4, self.thumb, self.thumb)
            # the size in the window's pixels: a picture for a 200 % screen has twice the pixels
            target = self.fit(pixmap.deviceIndependentSize().toSize(), area.size())
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
        badge = self.variant_badge(index)
        if badge:  # a variant: a glyph in the picture's corner, with the number of colours
            width = max(14, painter.fontMetrics().horizontalAdvance(badge) + 6)
            corner = QRect(rect.left() + self.STRIP + 4, rect.top() + 4, width, 14)
            painter.fillRect(corner, palette.base())
            painter.setPen(palette.text().color())
            painter.drawText(corner, Qt.AlignmentFlag.AlignCenter, badge)
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
    def variant_badge(index) -> str:  # noqa: ANN001
        """ "⧉" for a recolour variant (T13.18) and for one colour of a group a pack ships,
        "⧉ 8" for the card of such a group of eight; "" for any other asset."""
        count = index.data(ColourCountRole)
        if count:
            return f"{VARIANT_GLYPH} {count}"
        return VARIANT_GLYPH if index.data(VariantRole) or index.data(ColourOfRole) else ""

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

    def showEvent(self, event) -> None:  # noqa: ANN001, N802
        super().showEvent(event)
        model = self.model()
        source = model.sourceModel() if isinstance(model, QSortFilterProxyModel) else model
        if isinstance(source, AssetListModel):
            source.set_device_ratio(self.devicePixelRatioF())

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
SEARCH_WIDTH = 150
# the status a chip stands for, as the dot beside its word (All has none)
CHIP_DOTS = {
    "chipAttention": "NEEDS_REVIEW",
    "chipAuto": "AUTO_DETECTED",
    "chipConfirmed": "CONFIRMED",
    "chipUnused": "UNUSED",
}


def status_dot(status: str | None, size: int = 10) -> QIcon:
    """A round dot in a status colour (an empty icon for no status). The chip's word stays
    beside it, so the colour is never the only cue."""
    if not status:
        return QIcon()
    ratio = icons.screen_ratio()
    pixmap = QPixmap(theme.device_size(size, ratio), theme.device_size(size, ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(STATUS_COLORS[status]))
    painter.drawEllipse(pixmap.rect().adjusted(1, 1, -1, -1))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return QIcon(pixmap)


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
        layout.setContentsMargins(0, theme.px("space_8"), 0, 0)
        layout.setSpacing(theme.px("space_8"))
        # one filter row (T15.12): the status chips, the two combos, the search field, the
        # folder toggle and what the page adds at its end; it wraps in a narrow pane
        bar = FlowLayout(spacing=6)
        self.filter_bar = bar
        self.chips: dict[str, QPushButton] = {}
        self._chip_labels: dict[str, str] = {}
        for name, label, statuses in CHIPS:
            chip = QPushButton(self.tr(label))
            chip.setObjectName(name)
            chip.setCheckable(True)
            chip.setAutoExclusive(True)
            chip.setProperty("chip", True)
            chip.setToolTip(self.tr("Show only the assets with this status"))
            chip.setIcon(status_dot(CHIP_DOTS.get(name)))
            chip.setIconSize(QSize(10, 10))
            chip.clicked.connect(lambda _=False, s=statuses: self._show_statuses(s))
            bar.addWidget(chip)
            self.chips[name] = chip
            self._chip_labels[name] = label
        changed = QPushButton(self.tr("Changed in update"))
        changed.setObjectName(CHANGED_CHIP)
        changed.setCheckable(True)
        changed.setAutoExclusive(True)
        changed.setProperty("chip", True)
        changed.setVisible(False)
        changed.clicked.connect(self._show_changed)
        bar.addWidget(changed)
        self.chips[CHANGED_CHIP] = changed
        listed = QPushButton(self.tr("From the results"))
        listed.setObjectName(LISTED_CHIP)
        listed.setCheckable(True)
        listed.setAutoExclusive(True)
        listed.setProperty("chip", True)
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
        self.search.setMinimumWidth(SEARCH_WIDTH)
        self._search_icon = self.search.addAction(
            icons.icon("search", "text_muted"), QLineEdit.ActionPosition.LeadingPosition
        )
        theme.signals.changed.connect(self._retheme)
        for combo in (self.role_combo, self.pack_combo):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        bar.addWidget(self.role_combo)
        bar.addWidget(self.pack_combo)
        bar.addWidget(self.search)
        self.group_button = QPushButton()
        self.group_button.setObjectName("groupByFolder")
        self.group_button.setCheckable(True)
        buttons.icon_only(
            self.group_button,
            "list",
            self.tr(
                "Group by folder: a header per folder, with Confirm all, Select all and Make rule…"
            ),
            buttons.SECONDARY,
        )
        self.group_button.setAccessibleName(self.tr("Group by folder"))
        self.group_button.clicked.connect(lambda on: self.set_grouped(bool(on)))
        bar.addWidget(self.group_button)
        layout.addLayout(bar)
        self.view.card_delegate.headerToggled.connect(self.toggle_folder)
        self.view.card_delegate.headerAction.connect(self._on_header_action)
        layout.addWidget(self.view, 1)
        # the footer (T15.12): what the queue holds at the left, the keys and Shortcuts at the right
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(theme.px("space_8"))
        self.queue_label = QLabel()
        self.queue_label.setObjectName("queueLabel")
        self.queue_label.setProperty("role", "caption")
        self.queue_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.keys_label = QLabel(self.tr("C Confirm · X Exclude · 1–9 Role · N Next"))
        self.keys_label.setObjectName("keysLabel")
        self.keys_label.setProperty("role", "caption")
        self.help_button = QPushButton(self.tr("Shortcuts"))
        self.help_button.setObjectName("shortcutsButton")
        self.help_button.setToolTip(self.tr("Keyboard shortcuts of this page"))
        buttons.set_kind(self.help_button, buttons.QUIET)
        self.help_button.clicked.connect(self.shortcutsRequested)
        footer.addWidget(self.queue_label, 1)
        footer.addWidget(self.keys_label)
        footer.addWidget(self.help_button)
        layout.addLayout(footer)
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

    def add_filter_widget(self, widget: QWidget) -> None:
        """Put one of the page's controls at the end of the filter row (the Profile menu)."""
        self.filter_bar.addWidget(widget)

    def set_queue_text(self, text: str) -> None:
        self.queue_label.setText(text)
        self.queue_label.setToolTip(text)

    def _retheme(self, *_args: object) -> None:
        with contextlib.suppress(RuntimeError):  # the grid was closed
            self._search_icon.setIcon(icons.icon("search", "text_muted"))

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

    def set_rank(self, asset_ids: list[str] | None) -> None:
        """Show the assets in this order (inside a group, when grouped) instead of by status."""
        self.proxy.rank = None if asset_ids is None else {a: i for i, a in enumerate(asset_ids)}
        self.proxy.invalidate()

    def _show_group_icon(self, on: bool) -> None:
        """The toggle shows what a press gives: the list of folders, or the plain grid."""
        themed = self.group_button._themed_icon  # type: ignore[attr-defined]
        themed.name = "layout-grid" if on else "list"
        themed.apply()

    def set_grouped(self, on: bool, by_pack: bool = False) -> None:
        """A header row per folder (or per pack), or the flat grid."""
        self.group_button.setChecked(on)
        self._show_group_icon(on)
        if on == self.model.grouped and by_pack == self.model.by_pack:
            return
        selected = self.selected_ids()
        self.model.set_grouped(on, by_pack)
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

    # ------------------------------------------------------------------ colour variants

    def set_fold_colours(self, on: bool) -> None:
        """One card for the colours a pack ships of one picture (the audit; the picker of the
        Mapping page shows every colour)."""
        self.proxy.set_fold_colours(on)

    def colours_shown(self, asset_id: str) -> bool:
        """Whether the colour group with this first picture is shown as a card per colour."""
        return asset_id in self.proxy.unfolded

    def show_colours(self, asset_id: str, shown: bool) -> None:
        selected = self.selected_ids()
        self.proxy.set_unfolded(asset_id, shown)
        self.select_ids([i for i in selected if i in set(self.visible_ids())] or [asset_id])

    def folded_colours(self, asset_id: str) -> list[str]:
        """The colours the card of ``asset_id`` stands for at the moment (not itself)."""
        rows = ((m, self.model.row_of(m)) for m in self.model.colour_members(asset_id))
        return [m for m, row in rows if row is not None and self.proxy.is_folded(row)]

    def with_folded_colours(self, asset_ids: list[str]) -> list[str]:
        """``asset_ids`` and, after each card of a colour group, the colours it stands for: what
        Confirm, Exclude and a role key change, so that a group stays one card."""
        out: list[str] = []
        for asset_id in asset_ids:
            out.extend(i for i in (asset_id, *self.folded_colours(asset_id)) if i not in out)
        return out

    def select_colours(self, asset_id: str) -> list[str]:
        """Select every colour of a group (the bulk panel then edits them all); returns them."""
        group = [asset_id, *self.model.colour_members(asset_id)]
        self.proxy.set_unfolded(asset_id, True)
        shown = set(self.visible_ids())
        self.select_ids([i for i in group if i in shown])
        return self.selected_ids()

    def select_ids(self, asset_ids: list[str]) -> None:
        for asset_id in asset_ids:  # a colour its group's card stands for gets a card to select
            first, row = self.model.colour_first(asset_id), self.model.row_of(asset_id)
            if first is not None and row is not None and self.proxy.is_folded(row):
                self.proxy.set_unfolded(first, True)
        selection = self.view.selectionModel()
        selection.clearSelection()
        wanted = set(asset_ids)
        for r in range(self.proxy.rowCount()):
            index = self.proxy.index(r, 0)
            if index.data(AssetIdRole) in wanted:
                selection.select(index, selection.SelectionFlag.Select)
