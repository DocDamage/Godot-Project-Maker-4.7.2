from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QStyleOptionViewItem

from rpggen.core import archive, catalog, inventory
from rpggen.gui import thumbnails
from rpggen.gui.widgets import asset_grid as ag

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(scope="module")
def basic_catalog():
    opened = archive.open_pack(SYNTH / "basic16", set())
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    return cat, opened.root


def _resolver(root: Path):
    def resolve(asset):
        parts = asset.path.split("/", 3)
        return root / parts[3] if parts[:2] == ["assets", "packs"] else None

    return resolve


def _grid(qtbot, cat, root, statuses=None) -> ag.AssetGrid:
    grid = ag.AssetGrid()
    qtbot.addWidget(grid)
    grid.resize(700, 500)
    grid.show()
    grid.set_catalog(cat, _resolver(root))
    if statuses is False:
        grid.chips["chipAll"].click()
    return grid


def test_model_has_one_row_per_asset(qtbot, basic_catalog) -> None:
    cat, root = basic_catalog
    grid = _grid(qtbot, cat, root)
    assert grid.model.rowCount() == len(cat.assets)
    first = grid.model.index(0, 0)
    asset = cat.assets[0]
    assert first.data(ag.AssetIdRole) == asset.id
    assert first.data(ag.StatusRole) == asset.status
    assert first.data(ag.PackRole) == asset.pack_id
    assert first.data(Qt.ItemDataRole.DisplayRole) == asset.path.rsplit("/", 1)[-1]
    assert isinstance(first.data(Qt.ItemDataRole.DecorationRole), QPixmap)


def test_filters_change_visible_rows(qtbot, basic_catalog) -> None:
    cat, root = basic_catalog
    grid = _grid(qtbot, cat, root)
    total = len(cat.assets)
    attention = [a for a in cat.assets if a.status in ag.NEEDS_ATTENTION]
    assert grid.proxy.rowCount() == len(attention)  # default chip
    grid.chips["chipAll"].click()
    assert grid.proxy.rowCount() == total
    grid.chips["chipConfirmed"].click()
    assert grid.proxy.rowCount() == sum(a.status == "CONFIRMED" for a in cat.assets)
    grid.chips["chipAll"].click()
    grid.search.setText("HERO")  # case-insensitive path match
    assert grid.proxy.rowCount() == sum("hero" in a.path.lower() for a in cat.assets) >= 1
    grid.search.setText("")
    role = grid.model.roles()[0]
    grid.role_combo.setCurrentIndex(grid.role_combo.findData(role))
    shown = grid.proxy.rowCount()
    assert 0 < shown <= total
    grid.role_combo.setCurrentIndex(0)
    grid.pack_combo.setCurrentIndex(grid.pack_combo.findData("basic16"))
    assert grid.proxy.rowCount() == total


def test_sort_puts_attention_first(qtbot, basic_catalog) -> None:
    cat, root = basic_catalog
    grid = _grid(qtbot, cat, root, statuses=False)
    statuses = [grid.proxy.index(r, 0).data(ag.StatusRole) for r in range(grid.proxy.rowCount())]
    assert statuses == sorted(statuses, key=lambda s: ag.STATUS_PRIORITY[s])


def test_view_settings(qtbot, basic_catalog) -> None:
    cat, root = basic_catalog
    view = _grid(qtbot, cat, root).view
    assert view.viewMode().name == "IconMode" and view.uniformItemSizes()
    assert view.gridSize() == QSize(112, 152)
    assert view.layoutMode().name == "Batched"
    assert view.selectionMode().name == "ExtendedSelection"


@pytest.mark.parametrize("status", ag.STATUS_ORDER)
def test_delegate_paints_every_status(qtbot, basic_catalog, status) -> None:
    cat, root = basic_catalog
    grid = _grid(qtbot, cat, root)
    cat.assets[0].status = status
    grid.model.refresh([cat.assets[0].id])
    index = grid.model.index(0, 0)
    pixmap = QPixmap(112, 132)
    painter = QPainter(pixmap)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 112, 132)
    option.palette = grid.palette()
    ag.AssetCardDelegate().paint(painter, option, index)
    painter.end()
    strip = pixmap.toImage().pixelColor(4, 60)
    assert strip.name() == ag.STATUS_COLORS[status]


def test_status_colors_mirror_the_stylesheet() -> None:
    qss = (Path(ag.__file__).parents[1] / "style.qss").read_text(encoding="utf-8")
    block = re.search(r"status-colors.*?\n(.*?)\*/", qss, re.S).group(1)
    found = dict(re.findall(r"^(\w+)=(#[0-9a-f]{6})$", block, re.M))
    assert found == ag.STATUS_COLORS


def test_delegate_scales_by_integers() -> None:
    assert ag.AssetCardDelegate.fit(QSize(16, 16), QSize(96, 96)).size() == QSize(96, 96)
    assert ag.AssetCardDelegate.fit(QSize(20, 20), QSize(96, 96)).size() == QSize(80, 80)
    assert ag.AssetCardDelegate.fit(QSize(192, 96), QSize(96, 96)).size() == QSize(96, 48)


# ------------------------------------------------------------------------ thumbnails


def _png(path: Path, size, color=(255, 0, 0, 255)) -> Path:
    Image.new("RGBA", size, color).save(path)
    return path


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def test_thumbnail_rendering_rules(tmp_path: Path) -> None:
    sheet = Image.new("RGBA", (160, 160), (0, 0, 255, 255))
    sheet.paste((255, 255, 0, 255), (0, 0, 64, 64))  # the first 4x4 cells of a 16px grid
    path = tmp_path / "sheet.png"
    sheet.save(path)
    grid = {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}

    tiles = thumbnails.ThumbRequest("k1", str(path), "tiles", grid, None, None)
    img = _open(thumbnails.render_thumbnail(tiles))
    assert img.size == (64, 64) and img.getpixel((63, 63)) == (255, 255, 0, 255)

    sprite = thumbnails.ThumbRequest("k2", str(path), "sprite", None, [32, 48], None)
    img = _open(thumbnails.render_thumbnail(sprite))
    assert img.size == (64, 96)  # the first 32x48 frame at integer scale 2


def test_thumbnail_fits_96_with_nearest_neighbor(tmp_path: Path) -> None:
    big = _png(tmp_path / "big.png", (200, 100), (10, 20, 30, 255))
    req = thumbnails.ThumbRequest("k3", str(big), "image", None, None, None)
    img = _open(thumbnails.render_thumbnail(req))
    assert img.size == (96, 48)
    small = _png(tmp_path / "small.png", (16, 8), (1, 2, 3, 255))
    img = _open(
        thumbnails.render_thumbnail(
            thumbnails.ThumbRequest("k4", str(small), "image", None, None, None)
        )
    )
    assert img.size == (96, 48)  # integer upscale x6


def test_thumbnails_are_cached_on_disk(tmp_path: Path) -> None:
    path = _png(tmp_path / "a.png", (16, 16))
    req = thumbnails.request_for("a" * 64, path, {"usage": "image"})
    assert req.key.startswith("a" * 64 + "_")
    first = thumbnails.load_or_render(req)
    assert (thumbnails.thumb_cache_dir() / f"{req.key}.png").exists()
    path.unlink()  # the second call must come from the disk cache
    assert thumbnails.load_or_render(req) == first
    other = thumbnails.request_for("a" * 64, path, {"usage": "tiles", "grid": {"cell": [8, 8]}})
    assert other.key != req.key


def test_lru_keeps_the_most_recent(qtbot) -> None:
    cache = thumbnails.ThumbnailCache(capacity=3)
    pixmaps = {k: QPixmap(2, 2) for k in "abcd"}
    for key in "abc":
        cache.put(key, pixmaps[key])
    assert cache.get("a") is not None  # touches a
    cache.put("d", pixmaps["d"])
    assert "b" not in cache and "a" in cache and len(cache) == 3


def test_loader_delivers_pixmaps_to_the_model(qtbot, basic_catalog) -> None:
    cat, root = basic_catalog
    grid = _grid(qtbot, cat, root, statuses=False)
    index = grid.model.index(0, 0)
    first = index.data(Qt.ItemDataRole.DecorationRole)  # starts the request
    assert first.size() == QSize(96, 96)  # placeholder
    qtbot.waitUntil(lambda: len(grid.model.cache) > 0, timeout=10000)
    again = grid.model.index(0, 0).data(Qt.ItemDataRole.DecorationRole)
    assert again.size() != QSize(96, 96) or again.cacheKey() != first.cacheKey()
