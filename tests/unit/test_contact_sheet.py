"""T12.57: the contact sheet (pages, PDF, deterministic PNG)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import contact_sheet
from rpggen.core.contact_sheet import SheetEntry


def _sheet_png(tmp_path: Path) -> Path:
    path = tmp_path / "tiles.png"
    image = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    for x in range(16):
        for y in range(16):
            image.putpixel((x, y), (40, 160, 60, 255))
            image.putpixel((16 + x, y), (60, 60, 200, 255 if (x + y) % 2 else 0))
    image.save(path)
    return path


def _entries(path: Path | None, n: int) -> list[SheetEntry]:
    return [
        SheetEntry(
            name=f"tiles/sheet_{i:02d}.png",
            role="GROUND",
            status="confirmed",
            confidence=0.875,
            size_text="16x16 tiles",
            kind="image",
            path=path,
            grid=(16, 16, 0, 0, 0, 0),
        )
        for i in range(n)
    ]


@pytest.mark.parametrize(("n", "pages"), [(0, 1), (1, 1), (20, 1), (21, 2), (45, 3)])
def test_the_page_count_for_n_assets(n: int, pages: int) -> None:
    assert contact_sheet.PER_PAGE == 20
    assert contact_sheet.page_count(n) == pages
    assert len(contact_sheet.render_pages(_entries(None, n))) == pages


def test_the_pdf_starts_with_its_header_and_has_every_page(tmp_path: Path) -> None:
    out = tmp_path / "sheet.pdf"
    files = contact_sheet.export(_entries(_sheet_png(tmp_path), 25), out, "pdf", "Letter")
    assert files == [out]
    data = out.read_bytes()
    assert data.startswith(b"%PDF-")
    assert (
        data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + data.count(b"/Type/Page") >= 2
    )


def test_a_fixed_input_gives_the_same_png(tmp_path: Path) -> None:
    source = _sheet_png(tmp_path)
    entries = _entries(source, 3) + [
        SheetEntry("music/theme.ogg", "MUSIC", "auto_detected", 0.5, "", "audio", None),
        SheetEntry("lost.png", "-", "missing", 0.0, "", "image", tmp_path / "gone.png"),
    ]
    a = contact_sheet.export(
        entries, tmp_path / "a.png", "png", "A4", grid_overlay=True, title="Demo"
    )
    b = contact_sheet.export(
        entries, tmp_path / "b.png", "png", "A4", grid_overlay=True, title="Demo"
    )
    assert len(a) == len(b) == 1
    with Image.open(a[0]) as first, Image.open(b[0]) as second:
        assert first.size == contact_sheet.page_size("A4") == (1240, 1754)
        assert first.tobytes() == second.tobytes()
        pixels = hashlib.sha256(first.tobytes()).hexdigest()
    plain = contact_sheet.render_pages(entries, "A4", grid_overlay=False, title="Demo")[0]
    assert hashlib.sha256(plain.tobytes()).hexdigest() != pixels  # the overlay draws something


def test_several_png_pages_are_numbered_and_a_cancel_writes_nothing(tmp_path: Path) -> None:
    files = contact_sheet.export(_entries(None, 41), tmp_path / "sheet.png", "png")
    assert [f.name for f in files] == ["sheet-01.png", "sheet-02.png", "sheet-03.png"]
    out = tmp_path / "cancelled.pdf"
    assert contact_sheet.export(_entries(None, 41), out, "pdf", is_cancelled=lambda: True) == []
    assert not out.exists()
    with pytest.raises(ValueError):
        contact_sheet.export([], tmp_path / "x.tiff", "tiff")


def test_entries_follow_the_catalog_facets() -> None:
    from rpggen.core import catalog as catalog_mod

    asset = catalog_mod.Asset(
        "a1", "pack", "assets/packs/pack/chars/hero.png", "0" * 64, "image", "needs_review",
        {"usage": "sprite", "role": "PLAYER", "frame": [32, 48]}, {"role": "NPC"},
        confidence=0.42,
    )  # fmt: skip
    entry = contact_sheet.entry_for(asset, lambda a: None)
    assert (entry.name, entry.role, entry.status) == ("chars/hero.png", "NPC", "needs_review")
    assert entry.size_text == "32x48 frames" and entry.frame == (32, 48) and entry.path is None
