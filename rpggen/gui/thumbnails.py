"""Thumbnails: rendered as PNG bytes in workers, turned into QPixmaps on the UI thread only."""

from __future__ import annotations

import hashlib
import io
import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPixmap

from rpggen import paths
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers

log = logging.getLogger(__name__)

THUMB_SIZE = 96
CACHE_SIZE = 2000
TILE_PREVIEW_CELLS = 4
BATCH_SIZE = 24


@dataclass(frozen=True)
class ThumbRequest:
    """What a worker needs to render one thumbnail (plain data, no Qt objects)."""

    key: str  # disk-cache key: <sha256>_<variant>
    path: str  # absolute file path
    usage: str
    grid: dict[str, Any] | None
    frame: list[int] | None
    region: list[int] | None


def variant_tag(usage: str, grid: Any, frame: Any, region: Any) -> str:
    text = json.dumps([usage, grid, frame, region], sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def request_for(sha256: str, path: Path, facets: dict[str, Any]) -> ThumbRequest:
    usage = str(facets.get("usage", ""))
    grid = facets.get("grid")
    frame = facets.get("frame")
    region = facets.get("region")
    key = f"{sha256}_{variant_tag(usage, grid, frame, region)}"
    return ThumbRequest(key, str(path), usage, grid, frame, region)


def _crop_box(req: ThumbRequest, width: int, height: int) -> tuple[int, int, int, int]:
    x0 = y0 = 0
    x1, y1 = width, height
    if req.region and len(req.region) == 4:
        x0, y0, rw, rh = req.region
        x1, y1 = min(width, x0 + rw), min(height, y0 + rh)
    if req.usage == "tiles" and req.grid:
        cw, ch = req.grid["cell"]
        mx, my = req.grid.get("margin", [0, 0])
        sx, sy = req.grid.get("separation", [0, 0])
        n = TILE_PREVIEW_CELLS
        x1 = min(x1, x0 + mx + n * cw + (n - 1) * sx)
        y1 = min(y1, y0 + my + n * ch + (n - 1) * sy)
        x0, y0 = x0 + mx, y0 + my
    elif req.usage == "sprite" and req.frame:
        fw, fh = req.frame
        x1, y1 = min(x1, x0 + fw), min(y1, y0 + fh)
    return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)


def render_thumbnail(req: ThumbRequest, size: int = THUMB_SIZE) -> bytes:
    """PNG bytes of the preview: tiles show their first 4x4 cells, sprites their first frame,
    everything else the whole image, fitted to ``size`` with nearest-neighbor sampling."""
    with Image.open(req.path) as opened:
        rgba = opened.convert("RGBA")
        cropped = rgba.crop(_crop_box(req, *rgba.size))
    w, h = cropped.size
    scale = min(size / w, size / h)
    if scale >= 1:
        scale = max(1, int(scale))  # integer upscale keeps pixels square
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    resized = cropped.resize(new_size, Image.Resampling.NEAREST)
    out = io.BytesIO()
    resized.save(out, format="PNG")
    return out.getvalue()


def thumb_cache_dir() -> Path:
    return paths.local_cache_dir() / "thumbs"


def load_or_render(req: ThumbRequest) -> bytes | None:
    """Bytes from the disk cache or freshly rendered (and stored); None when the file fails."""
    cached = thumb_cache_dir() / f"{req.key}.png"
    try:
        if cached.exists():
            return cached.read_bytes()
        data = render_thumbnail(req)
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(cached)
        return data
    except Exception:  # noqa: BLE001 - a broken image only loses its thumbnail
        log.warning("no thumbnail for %s", req.path, exc_info=True)
        return None


def load_thumbnails(
    requests: list[ThumbRequest],
    on_ready: Callable[[str, bytes], None],
    *,
    callbacks: Callbacks,
) -> int:
    """Worker function: render every request and hand the bytes to ``on_ready``."""
    done = 0
    for req in requests:
        if callbacks.is_cancelled():
            raise workers.Cancelled
        data = load_or_render(req)
        if data is not None:
            on_ready(req.key, data)
        done += 1
        callbacks.on_phase("thumbnails", done, len(requests))
    return done


def pixmap_from_bytes(data: bytes) -> QPixmap:
    """Create the QPixmap; call on the UI thread only."""
    pixmap = QPixmap()
    pixmap.loadFromData(data, "PNG")  # type: ignore[call-overload]  # the stub wants bytes
    return pixmap


class ThumbnailCache:
    """LRU of QPixmaps (UI thread only)."""

    def __init__(self, capacity: int = CACHE_SIZE) -> None:
        self.capacity = capacity
        self._items: OrderedDict[str, QPixmap] = OrderedDict()

    def get(self, key: str) -> QPixmap | None:
        pixmap = self._items.get(key)
        if pixmap is not None:
            self._items.move_to_end(key)
        return pixmap

    def put(self, key: str, pixmap: QPixmap) -> None:
        self._items[key] = pixmap
        self._items.move_to_end(key)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return key in self._items


def placeholder_pixmap(size: int = THUMB_SIZE) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(200, 200, 200))
    return pixmap


class ThumbnailLoader(QObject):
    """Batches thumbnail requests into workers and announces results with ``ready``."""

    ready = Signal(str, bytes)  # cache key, PNG bytes

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pending: dict[str, ThumbRequest] = {}
        self._in_flight: set[str] = set()
        self._workers: set[workers.Worker] = set()
        self._stopped = False

    def request(self, req: ThumbRequest) -> None:
        if self._stopped or req.key in self._pending or req.key in self._in_flight:
            return
        self._pending[req.key] = req
        if not self._workers:
            self._start_next()

    def _start_next(self) -> None:
        if not self._pending or self._stopped:
            return
        batch: list[ThumbRequest] = []
        for key in list(self._pending)[:BATCH_SIZE]:
            batch.append(self._pending.pop(key))
        self._in_flight.update(r.key for r in batch)
        worker = workers.Worker(load_thumbnails, batch, self.ready.emit)
        self._workers.add(worker)

        def finished(_result: object, w: workers.Worker = worker, keys=tuple(r.key for r in batch)):
            self._in_flight.difference_update(keys)
            self._workers.discard(w)
            self._start_next()

        worker.signals.finished.connect(finished)
        worker.signals.failed.connect(finished)
        worker.start()

    def stop(self) -> None:
        """Forget queued work and ask running workers to stop (used when the grid goes away)."""
        self._stopped = True
        self._pending.clear()
        for worker in self._workers:
            worker.cancel()
