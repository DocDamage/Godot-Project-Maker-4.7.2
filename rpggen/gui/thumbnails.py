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

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPixmap

from rpggen import paths
from rpggen.core import audio_info
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers

log = logging.getLogger(__name__)

THUMB_SIZE = 96
CACHE_SIZE = 2000
TILE_PREVIEW_CELLS = 4
BATCH_SIZE = 24
CARD_VERSION = 2  # bump when the audio or font card drawing changes (2: decoded waveforms)


@dataclass(frozen=True)
class ThumbRequest:
    """What a worker needs to render one thumbnail (plain data, no Qt objects)."""

    key: str  # disk-cache key: <sha256>_<variant>
    path: str  # absolute file path
    usage: str
    grid: dict[str, Any] | None
    frame: list[int] | None
    region: list[int] | None
    size: int = 96  # THUMB_SIZE; the box the picture is fitted into
    cells: int = TILE_PREVIEW_CELLS  # tile sheets: how many cells across and down are shown
    skip_empty: bool = False  # tile sheets: start at the first cell that has something in it
    kind: str = "image"  # "audio" and "font" cards are drawn, not read as pictures
    duration: float | None = None  # audio cards: the length shown on the card


def variant_tag(
    usage: str,
    grid: Any,
    frame: Any,
    region: Any,
    size: int = THUMB_SIZE,
    cells: int = TILE_PREVIEW_CELLS,
    skip_empty: bool = False,
    kind: str = "image",
    duration: float | None = None,
    ratio: float = 1.0,
) -> str:
    payload: list[Any] = [usage, grid, frame, region]
    if size != THUMB_SIZE or cells != TILE_PREVIEW_CELLS or skip_empty:
        payload.append([size, cells, skip_empty])  # the defaults keep the keys already on disk
    if kind != "image":
        payload.append(["card", CARD_VERSION, kind, duration])
    if ratio != 1.0:  # a screen scaled to 150 % or 200 % has pictures of its own
        payload.append(["ratio", round(ratio, 3)])
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def request_for(
    sha256: str,
    path: Path,
    facets: dict[str, Any],
    size: int = THUMB_SIZE,
    cells: int = TILE_PREVIEW_CELLS,
    skip_empty: bool = False,
    kind: str = "image",
    duration: float | None = None,
    ratio: float = 1.0,
) -> ThumbRequest:
    """``size`` is the box in the window's own pixels; on a screen with the device pixel ratio
    ``ratio`` the picture is rendered for ``size * ratio`` device pixels (T13.10), so pixel art
    is scaled by a whole number of device pixels. Give the same ratio to ``pixmap_from_bytes``."""
    usage = str(facets.get("usage", ""))
    grid = facets.get("grid")
    frame = facets.get("frame")
    region = facets.get("region")
    tag = variant_tag(usage, grid, frame, region, size, cells, skip_empty, kind, duration, ratio)
    device = max(1, round(size * ratio))
    return ThumbRequest(
        f"{sha256}_{tag}", str(path), usage, grid, frame, region, device, cells, skip_empty,
        kind, duration,
    )  # fmt: skip


def first_filled_cell(image: Image.Image, grid: dict[str, Any]) -> tuple[int, int]:
    """(column, row) of the first cell, row by row, that has a visible pixel; (0, 0) when none."""
    cw, ch = grid["cell"]
    mx, my = grid.get("margin", [0, 0])
    sx, sy = grid.get("separation", [0, 0])
    alpha = image.getchannel("A")
    cols = max(1, (image.width - mx + sx) // (cw + sx))
    rows = max(1, (image.height - my + sy) // (ch + sy))
    for row in range(rows):
        for col in range(cols):
            x, y = mx + col * (cw + sx), my + row * (ch + sy)
            if alpha.crop((x, y, x + cw, y + ch)).getbbox() is not None:
                return col, row
    return 0, 0


def _crop_box(
    req: ThumbRequest, width: int, height: int, start_cell: tuple[int, int] = (0, 0)
) -> tuple[int, int, int, int]:
    x0 = y0 = 0
    x1, y1 = width, height
    if req.region and len(req.region) == 4:
        x0, y0, rw, rh = req.region
        x1, y1 = min(width, x0 + rw), min(height, y0 + rh)
    if req.usage == "tiles" and req.grid:
        cw, ch = req.grid["cell"]
        mx, my = req.grid.get("margin", [0, 0])
        sx, sy = req.grid.get("separation", [0, 0])
        n = req.cells
        x0 += start_cell[0] * (cw + sx)
        y0 += start_cell[1] * (ch + sy)
        x1 = min(x1, x0 + mx + n * cw + (n - 1) * sx)
        y1 = min(y1, y0 + my + n * ch + (n - 1) * sy)
        x0, y0 = x0 + mx, y0 + my
    elif req.usage == "sprite" and req.frame:
        fw, fh = req.frame
        x1, y1 = min(x1, x0 + fw), min(y1, y0 + fh)
    return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)


def _png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _small_font(size: int) -> Any:
    return ImageFont.load_default(size=max(8, size))


def render_audio_card(path: Path, duration: float | None, size: int = THUMB_SIZE) -> bytes:
    """A speaker glyph, the waveform (the decoded samples of a WAV, OGG, FLAC or MP3; a flat
    bar for a file that cannot be decoded) and the duration, on a fixed dark card."""
    k = size / 96

    def px(v: float) -> int:
        return round(v * k)

    image = Image.new("RGBA", (size, size), (38, 46, 64, 255))
    draw = ImageDraw.Draw(image)
    ink = (214, 224, 244, 255)
    wave_ink = (104, 168, 240, 255)
    cx, cy = size // 2 - px(12), px(26)  # the speaker's box meets its cone at (cx, cy)
    draw.rectangle([cx - px(10), cy - px(6), cx, cy + px(6)], fill=ink)
    draw.polygon(
        [
            (cx, cy - px(6)),
            (cx + px(14), cy - px(16)),
            (cx + px(14), cy + px(16)),
            (cx, cy + px(6)),
        ],
        fill=ink,
    )
    for r in (px(14), px(24)):
        draw.arc(
            [cx + px(14) - r, cy - r, cx + px(14) + r, cy + r],
            -45,
            45,
            fill=ink,
            width=max(1, px(2)),
        )
    mid, height, margin = px(62), px(22), px(8)
    peaks = audio_info.peaks(path, columns=max(16, size - 2 * margin))
    if peaks:
        step = (size - 2 * margin) / len(peaks)
        for i, (low, high) in enumerate(peaks):
            x = round(margin + i * step)
            top = mid - max(0, round(high * height))
            bottom = mid + max(0, round(-low * height))
            draw.line(
                [(x, min(top, mid)), (x, max(bottom, mid))],
                fill=wave_ink,
                width=max(1, round(step)),
            )
    else:
        draw.line([(margin, mid), (size - margin, mid)], fill=wave_ink, width=1)
    text = audio_info.format_duration(duration)
    font = _small_font(px(13))
    draw.text((size / 2, px(84)), text, fill=ink, font=font, anchor="mm")
    return _png(image)


def render_font_card(path: Path, size: int = THUMB_SIZE) -> bytes:
    """ "Aa Bb 123" drawn from the font file; "Aa" in the default font when it cannot be read."""
    image = Image.new("RGBA", (size, size), (244, 244, 240, 255))
    draw = ImageDraw.Draw(image)
    ink = (30, 30, 34, 255)
    try:
        font = ImageFont.truetype(str(path), max(10, size // 5))
        draw.text((size // 2, size // 3), "Aa Bb", fill=ink, font=font, anchor="mm")
        draw.text((size // 2, size * 2 // 3), "123", fill=ink, font=font, anchor="mm")
    except (OSError, ValueError):
        draw.text((size // 2, size // 2), "Aa", fill=ink, font=_small_font(size // 2), anchor="mm")
    return _png(image)


def render_thumbnail(req: ThumbRequest, size: int = THUMB_SIZE) -> bytes:
    """PNG bytes of the preview: tiles show their first 4x4 cells, sprites their first frame,
    everything else the whole image, fitted to ``size`` with nearest-neighbor sampling. Audio and
    font files get a drawn card."""
    if req.kind == "audio":
        return render_audio_card(Path(req.path), req.duration, size)
    if req.kind == "font":
        return render_font_card(Path(req.path), size)
    with Image.open(req.path) as opened:
        rgba = opened.convert("RGBA")
        start = (0, 0)
        if req.skip_empty and req.usage == "tiles" and req.grid:
            start = first_filled_cell(rgba, req.grid)
        cropped = rgba.crop(_crop_box(req, *rgba.size, start))
    w, h = cropped.size
    scale = min(size / w, size / h)
    if scale >= 1:
        scale = max(1, int(scale))  # integer upscale keeps pixels square
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return _png(cropped.resize(new_size, Image.Resampling.NEAREST))


def _cell_box(grid: dict[str, Any], col: int, row: int) -> tuple[int, int, int, int]:
    cw, ch = grid["cell"]
    mx, my = grid.get("margin", [0, 0])
    sx, sy = grid.get("separation", [0, 0])
    x, y = mx + col * (cw + sx), my + row * (ch + sy)
    return x, y, x + cw, y + ch


def first_frame_image(path: Path, facets: dict[str, Any]) -> Image.Image | None:
    """The first frame of a character or an enemy: the first cell of ``idle_down``, else of
    ``walk_down`` or of any animation, else the first cell (or frame) of the sheet. None when the
    file cannot be read."""
    grid = facets.get("grid")
    animations = facets.get("animations") or {}
    cell = (0, 0)
    for name in ("idle_down", "walk_down", *animations):
        frames = (animations.get(name) or {}).get("frames")
        if frames:
            cell = (int(frames[0][0]), int(frames[0][1]))
            break
    try:
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
    except (OSError, ValueError):
        return None
    if grid:
        box = _cell_box(grid, *cell)
    elif facets.get("frame"):
        fw, fh = facets["frame"]
        box = (0, 0, fw, fh)
    else:
        return rgba
    cropped = rgba.crop(box)
    return cropped if cropped.getbbox() is not None else None


def ground_tile_image(path: Path, facets: dict[str, Any]) -> Image.Image | None:
    """The first cell of a tile sheet that has something in it; None when it cannot be read."""
    grid = facets.get("grid")
    if not grid:
        return None
    try:
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
    except (OSError, ValueError):
        return None
    col, row = first_filled_cell(rgba, grid)
    return rgba.crop(_cell_box(grid, col, row))


def thumb_cache_dir() -> Path:
    return paths.cache_dir() / "thumbs"


def load_or_render(req: ThumbRequest) -> bytes | None:
    """Bytes from the disk cache or freshly rendered (and stored); None when the file fails."""
    cached = thumb_cache_dir() / f"{req.key}.png"
    try:
        if cached.exists():
            return cached.read_bytes()
        data = render_thumbnail(req, req.size)
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


def pixmap_from_bytes(data: bytes, ratio: float = 1.0) -> QPixmap:
    """Create the QPixmap; call on the UI thread only. ``ratio`` is the device pixel ratio the
    picture was rendered for: the pixmap is tagged with it, so it is drawn pixel for pixel."""
    pixmap = QPixmap()
    pixmap.loadFromData(data, "PNG")  # type: ignore[call-overload]  # the stub wants bytes
    if ratio != 1.0:
        pixmap.setDevicePixelRatio(ratio)
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
