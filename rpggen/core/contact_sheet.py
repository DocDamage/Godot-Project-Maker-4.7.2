"""Contact sheet export (T12.57, ARCHITECTURE §13): the audit on paper, for review offline.

Each page holds a grid of assets: the picture (the whole file, or its region; optionally with the
tile or frame grid drawn over it), the file name, the role and status, the confidence, and the
tile or frame size. The output is a PNG per page or one PDF, A4 or Letter, drawn with Pillow (so
no new dependency, and no Qt in core). The same input always gives the same pixels.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from rpggen.core import catalog as catalog_mod

DPI = 150
PAPERS = {"A4": (210.0, 297.0), "Letter": (215.9, 279.4)}  # millimetres, portrait
COLUMNS = 4
ROWS = 5
PER_PAGE = COLUMNS * ROWS
FORMATS = ("pdf", "png")

MARGIN = 60  # px at DPI
HEADER = 44
PAD = 8
LINE = 17
TEXT_LINES = 4
BACKGROUND = (255, 255, 255)
INK = (30, 30, 30)
MUTED = (110, 110, 110)
FRAME = (200, 200, 200)
CHECKER = ((236, 236, 236), (214, 214, 214))
GRID = (230, 40, 90)
CHECK = 8  # checkerboard square, px

Resolver = Callable[[catalog_mod.Asset], Path | None]
Progress = Callable[[int, int], None]


@dataclass(frozen=True)
class SheetEntry:
    """What one cell shows (plain data: built on the UI thread, drawn in a worker)."""

    name: str  # pack-relative file name
    role: str
    status: str
    confidence: float
    size_text: str  # "16x16 tiles", "32x48 frames" or ""
    kind: str  # image, audio, font
    path: Path | None  # the file, or None when it cannot be found
    region: tuple[int, int, int, int] | None = None
    grid: tuple[int, int, int, int, int, int] | None = None  # cell w, h, margin x, y, sep x, y
    frame: tuple[int, int] | None = None


def size_text(facets: dict[str, Any]) -> str:
    grid = facets.get("grid")
    if facets.get("usage") == "tiles" and isinstance(grid, dict) and grid.get("cell"):
        w, h = grid["cell"]
        return f"{w}x{h} tiles"
    frame = facets.get("frame")
    if isinstance(frame, list | tuple) and len(frame) == 2:
        return f"{frame[0]}x{frame[1]} frames"
    return ""


def entry_for(asset: catalog_mod.Asset, resolver: Resolver) -> SheetEntry:
    facets = catalog_mod.effective(asset)
    region = facets.get("region")
    grid = facets.get("grid")
    frame = facets.get("frame")
    grid_box = None
    if facets.get("usage") == "tiles" and isinstance(grid, dict) and grid.get("cell"):
        cw, ch = grid["cell"]
        mx, my = grid.get("margin", [0, 0])
        sx, sy = grid.get("separation", [0, 0])
        grid_box = (int(cw), int(ch), int(mx), int(my), int(sx), int(sy))
    frame_box = None
    if facets.get("usage") == "sprite" and isinstance(frame, list | tuple) and len(frame) == 2:
        frame_box = (int(frame[0]), int(frame[1]))
    return SheetEntry(
        name=asset.path.split("/", 3)[-1],
        role=str(facets.get("role", "") or "-"),
        status=asset.status,
        confidence=float(asset.confidence),
        size_text=size_text(facets),
        kind=asset.kind,
        path=resolver(asset),
        region=tuple(int(v) for v in region)
        if isinstance(region, list) and len(region) == 4
        else None,  # type: ignore[arg-type]
        grid=grid_box,
        frame=frame_box,
    )


def entries_for(
    catalog: catalog_mod.Catalog, resolver: Resolver, ids: Sequence[str] | None = None
) -> list[SheetEntry]:
    """The entries of ``ids`` (the audit's filtered set, in its order) or of every asset, sorted
    by path."""
    by_id = {a.id: a for a in catalog.assets}
    if ids is None:
        chosen = sorted(catalog.assets, key=lambda a: (a.path.casefold(), a.path))
    else:
        chosen = [by_id[i] for i in ids if i in by_id]
    return [entry_for(a, resolver) for a in chosen]


def page_count(n: int, per_page: int = PER_PAGE) -> int:
    """Pages for ``n`` assets; an empty sheet is still one page (it says so)."""
    return max(1, math.ceil(n / per_page))


def page_size(paper: str, dpi: int = DPI) -> tuple[int, int]:
    w_mm, h_mm = PAPERS[paper]
    return round(w_mm / 25.4 * dpi), round(h_mm / 25.4 * dpi)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: Any, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    # three dots: Pillow's built-in font has no ellipsis (nor dashes) to draw
    while text and draw.textlength(text + "...", font=font) > width:
        text = text[:-1]
    return text + "..."


def _checker(size: tuple[int, int]) -> Image.Image:
    board = Image.new("RGB", size, CHECKER[0])
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], CHECK):
        for x in range(0, size[0], CHECK):
            if (x // CHECK + y // CHECK) % 2:
                draw.rectangle((x, y, x + CHECK - 1, y + CHECK - 1), fill=CHECKER[1])
    return board


def _picture(entry: SheetEntry, box: tuple[int, int], grid_overlay: bool) -> Image.Image:
    """The cell's picture, fitted into ``box`` (pixel art scaled by whole steps when it grows)."""
    canvas = Image.new("RGB", box, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    note = ""
    if entry.kind != "image":
        note = entry.kind.upper()
    elif entry.path is None or not entry.path.is_file():
        note = "missing"
    if note:
        font = _font(16)
        width = draw.textlength(note, font=font)
        draw.rectangle((0, 0, box[0] - 1, box[1] - 1), outline=FRAME)
        draw.text(((box[0] - width) / 2, box[1] / 2 - 9), note, fill=MUTED, font=font)
        return canvas
    assert entry.path is not None
    with Image.open(entry.path) as opened:
        rgba = opened.convert("RGBA")
    if entry.region:
        x, y, w, h = entry.region
        rgba = rgba.crop((x, y, x + w, y + h))
    scale = min(box[0] / rgba.width, box[1] / rgba.height)
    if scale >= 1:
        scale = float(int(scale))
    size = (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale)))
    resample = Image.Resampling.NEAREST if scale >= 1 else Image.Resampling.BOX
    shown = rgba.resize(size, resample)
    board = _checker(size)
    board.paste(shown, (0, 0), shown)
    offset = ((box[0] - size[0]) // 2, (box[1] - size[1]) // 2)
    canvas.paste(board, offset)
    if grid_overlay:
        _draw_grid(ImageDraw.Draw(canvas), entry, offset, size, rgba.size, scale)
    return canvas


def _draw_grid(
    draw: ImageDraw.ImageDraw,
    entry: SheetEntry,
    offset: tuple[int, int],
    size: tuple[int, int],
    source: tuple[int, int],
    scale: float,
) -> None:
    """The tile cells or sprite frames over the picture."""
    if entry.grid:
        cw, ch, mx, my, sx, sy = entry.grid
    elif entry.frame:
        cw, ch = entry.frame
        mx = my = sx = sy = 0
    else:
        return
    ox, oy = offset
    x = mx
    while x + cw <= source[0] + 0.01:
        left = ox + round(x * scale)
        draw.rectangle((left, oy, left + round(cw * scale) - 1, oy + size[1] - 1), outline=GRID)
        x += cw + sx
    y = my
    while y + ch <= source[1] + 0.01:
        top = oy + round(y * scale)
        draw.line((ox, top, ox + size[0] - 1, top), fill=GRID)
        draw.line(
            (ox, top + round(ch * scale) - 1, ox + size[0] - 1, top + round(ch * scale) - 1),
            fill=GRID,
        )
        y += ch + sy


def render_pages(
    entries: Sequence[SheetEntry],
    paper: str = "A4",
    grid_overlay: bool = False,
    title: str = "",
    is_cancelled: Callable[[], bool] | None = None,
    progress: Progress | None = None,
) -> list[Image.Image]:
    """One RGB image per page. Stops early (returning the pages so far) when cancelled."""
    width, height = page_size(paper)
    cell_w = (width - 2 * MARGIN) // COLUMNS
    cell_h = (height - 2 * MARGIN - HEADER) // ROWS
    picture = (cell_w - 2 * PAD, cell_h - 3 * PAD - TEXT_LINES * LINE)
    total = page_count(len(entries))
    title_font, text_font, small_font = _font(20), _font(14), _font(12)
    pages: list[Image.Image] = []
    for page_index in range(total):
        page = Image.new("RGB", (width, height), BACKGROUND)
        draw = ImageDraw.Draw(page)
        heading = f"{title} · contact sheet" if title else "Contact sheet"
        draw.text((MARGIN, MARGIN), heading, fill=INK, font=title_font)
        footer = f"page {page_index + 1} of {total} · {len(entries)} assets"
        draw.text(
            (width - MARGIN - draw.textlength(footer, font=small_font), MARGIN + 6),
            footer,
            fill=MUTED,
            font=small_font,
        )
        chunk = entries[page_index * PER_PAGE : (page_index + 1) * PER_PAGE]
        if not chunk:
            draw.text((MARGIN, MARGIN + HEADER), "No assets to show.", fill=MUTED, font=text_font)
        for i, entry in enumerate(chunk):
            if is_cancelled is not None and is_cancelled():
                return pages
            x = MARGIN + (i % COLUMNS) * cell_w
            y = MARGIN + HEADER + (i // COLUMNS) * cell_h
            draw.rectangle((x, y, x + cell_w - 4, y + cell_h - 4), outline=FRAME)
            page.paste(_picture(entry, picture, grid_overlay), (x + PAD, y + PAD))
            text_y = y + 2 * PAD + picture[1]
            room = cell_w - 2 * PAD
            lines = [
                (_fit_text(draw, entry.name, text_font, room), INK, text_font),
                (
                    _fit_text(draw, f"{entry.role} · {entry.status}", small_font, room),
                    INK,
                    small_font,
                ),
                (f"confidence {round(entry.confidence * 100)}%", MUTED, small_font),
                (entry.size_text, MUTED, small_font),
            ]
            for n, (text, colour, font) in enumerate(lines):
                draw.text((x + PAD, text_y + n * LINE), text, fill=colour, font=font)
            if progress is not None:
                progress(page_index * PER_PAGE + i + 1, len(entries))
        pages.append(page)
    return pages


def save(pages: Sequence[Image.Image], out: Path, fmt: str) -> list[Path]:
    """Write the pages: one PDF, or one PNG (``name.png``; ``name-01.png``... for several).
    Returns the files written."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "pdf":
        first, rest = pages[0], list(pages[1:])
        first.save(out, format="PDF", save_all=True, append_images=rest, resolution=float(DPI))
        return [out]
    if len(pages) == 1:
        pages[0].save(out, format="PNG", dpi=(DPI, DPI))
        return [out]
    written = []
    for i, page in enumerate(pages, start=1):
        path = out.with_name(f"{out.stem}-{i:02d}{out.suffix or '.png'}")
        page.save(path, format="PNG", dpi=(DPI, DPI))
        written.append(path)
    return written


def export(
    entries: Sequence[SheetEntry],
    out: Path,
    fmt: str = "pdf",
    paper: str = "A4",
    grid_overlay: bool = False,
    title: str = "",
    is_cancelled: Callable[[], bool] | None = None,
    progress: Progress | None = None,
) -> list[Path]:
    """Render and write the contact sheet; nothing is written when cancelled."""
    if fmt not in FORMATS or paper not in PAPERS:
        raise ValueError(f"unknown format or paper: {fmt}, {paper}")
    pages = render_pages(entries, paper, grid_overlay, title, is_cancelled, progress)
    if is_cancelled is not None and is_cancelled():
        return []
    return save(pages, out, fmt)
