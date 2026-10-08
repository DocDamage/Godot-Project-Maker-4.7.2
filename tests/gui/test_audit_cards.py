"""T12.31: role chips, confidence bars, audio and font cards, and playback in the detail panel."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QStyleOptionViewItem

from rpggen.core import archive, audio_info, catalog, inventory, labels
from rpggen.gui import edits, thumbnails
from rpggen.gui.widgets import asset_detail, audio_preview
from rpggen.gui.widgets import asset_grid as ag

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _build(pack: str):
    opened = archive.open_pack(SYNTH / pack, set())
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    return cat, opened.root


def _resolver(root: Path):
    def resolve(asset):
        parts = asset.path.split("/", 3)
        return root / parts[3] if parts[:2] == ["assets", "packs"] else None

    return resolve


def test_the_delegate_paints_a_role_chip_and_a_confidence_bar(qtbot) -> None:
    cat, root = _build("basic16")
    model = ag.AssetListModel()
    model.set_catalog(cat, _resolver(root))
    row = next(
        i
        for i in range(model.rowCount())
        if model.asset_at(i).status in ("AUTO_DETECTED", "NEEDS_REVIEW")
    )
    index = model.index(row, 0)
    delegate = ag.AssetCardDelegate()
    assert delegate.chip_text(index) == labels.role_label(str(index.data(ag.RoleRole)))
    cell = ag.grid_size_for(delegate.thumb)
    image = QImage(cell, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, cell.width(), cell.height())
    delegate.paint(painter, option, index)
    painter.end()
    chip = delegate.chip_rect(option.rect.adjusted(2, 2, -2, -2))
    base = option.palette.base().color().rgb()
    assert any(
        image.pixelColor(x, y).rgb() != base
        for x in range(chip.left(), chip.right())
        for y in range(chip.top(), chip.bottom())
    ), "the chip area is empty"
    bar_y = 2 + delegate.thumb + 6 + 1
    assert image.pixelColor(2 + delegate.STRIP + 6, bar_y).rgb() != base, "no confidence bar"
    assert chip.bottom() <= cell.height() - 2


def test_format_duration_and_waveform(tmp_path: Path) -> None:
    assert audio_info.format_duration(None) == "--"
    assert audio_info.format_duration(3.24) == "3.2 s"
    assert audio_info.format_duration(125) == "2:05"
    path = tmp_path / "ramp.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(int(i * 30).to_bytes(2, "little", signed=True) for i in range(1000)))
    peaks = audio_info.waveform(path, bins=10)
    assert peaks is not None and len(peaks) == 10
    assert peaks[-1] > peaks[0] and all(0 <= p <= 1 for p in peaks)
    assert audio_info.waveform(tmp_path / "x.ogg") is None
    assert audio_info.waveform(tmp_path / "missing.wav") is None


def test_an_audio_card_shows_its_duration(tmp_path: Path) -> None:
    wav = SYNTH / "audio_basic" / "sfx" / "hit.wav"
    short = thumbnails.render_audio_card(wav, 1.5)
    long = thumbnails.render_audio_card(wav, 95)
    assert short != long  # the duration is drawn on the card
    card = Image.open(io.BytesIO(short))
    assert card.size == (96, 96)
    # a drawn waveform: some pixels in the strip are the waveform colour
    assert any(card.getpixel((x, 62))[2] > 200 for x in range(8, 88))
    # a format without a waveform still gets a card
    ogg = thumbnails.render_audio_card(SYNTH / "audio_basic" / "sfx" / "cursor_move.ogg", None)
    assert Image.open(io.BytesIO(ogg)).size == (96, 96)


def test_audio_and_font_cards_are_not_blank_squares(qtbot, tmp_path: Path) -> None:
    cat, root = _build("audio_basic")
    model = ag.AssetListModel()
    model.set_catalog(cat, _resolver(root))
    row = next(i for i in range(model.rowCount()) if model.asset_at(i).kind == "audio")
    index = model.index(row, 0)
    assert isinstance(index.data(Qt.ItemDataRole.DecorationRole), QPixmap)
    qtbot.waitUntil(lambda: len(model.cache) > 0, timeout=10000)
    shown = index.data(Qt.ItemDataRole.DecorationRole)
    assert shown.toImage().pixelColor(2, 2).getRgb()[:3] != (200, 200, 200)  # not the grey square
    bad = tmp_path / "broken.ttf"
    bad.write_bytes(b"not a font")
    font_card = thumbnails.render_font_card(bad)
    assert Image.open(io.BytesIO(font_card)).size == (96, 96)
    req = thumbnails.request_for("abc", bad, {"usage": "font"}, kind="font")
    assert req.key != thumbnails.request_for("abc", bad, {"usage": "font"}).key


def _detail(qtbot, cat, root):
    session = edits.EditSession(cat)
    detail = asset_detail.AssetDetail(session)
    qtbot.addWidget(detail)
    detail.resolver = _resolver(root)
    detail.show()
    return detail


def test_the_detail_panel_for_audio_has_play_and_no_picture_box(qtbot, monkeypatch) -> None:
    cat, root = _build("audio_basic")
    detail = _detail(qtbot, cat, root)
    audio = next(a for a in cat.assets if a.kind == "audio")
    monkeypatch.setattr(audio_preview, "available", lambda: True)
    detail.set_asset(audio.id)
    assert not detail.preview.isVisibleTo(detail)
    assert detail.audio_box.isVisibleTo(detail)
    assert detail.play_button.isVisibleTo(detail)
    text = detail.audio_info_label.text()
    assert audio.path.rsplit(".", 1)[-1].upper() in text
    assert any(ch.isdigit() for ch in text)  # the duration


def test_play_is_hidden_when_nothing_can_play(qtbot, monkeypatch) -> None:
    cat, root = _build("audio_basic")
    detail = _detail(qtbot, cat, root)
    audio = next(a for a in cat.assets if a.kind == "audio")
    monkeypatch.setattr(audio_preview, "available", lambda: False)
    detail.set_asset(audio.id)
    assert not detail.play_button.isVisibleTo(detail)
    detail.toggle_playback()  # nothing happens, nothing raises


def test_images_keep_their_preview_and_have_no_audio_box(qtbot) -> None:
    cat, root = _build("basic16")
    detail = _detail(qtbot, cat, root)
    detail.set_asset(next(a.id for a in cat.assets if a.kind == "image"))
    assert detail.preview.isVisibleTo(detail)
    assert not detail.audio_box.isVisibleTo(detail)


@pytest.mark.parametrize("pack", ["audio_basic"])
def test_toggle_plays_and_stops(qtbot, monkeypatch, pack: str) -> None:
    cat, root = _build(pack)
    detail = _detail(qtbot, cat, root)
    played: list[Path] = []
    state = {"playing": False}
    monkeypatch.setattr(audio_preview, "available", lambda: True)
    monkeypatch.setattr(
        audio_preview, "play", lambda p: played.append(p) or state.update(playing=True) or True
    )
    monkeypatch.setattr(audio_preview, "stop", lambda: state.update(playing=False))
    monkeypatch.setattr(audio_preview, "is_playing", lambda: state["playing"])
    detail.set_asset(next(a.id for a in cat.assets if a.kind == "audio"))
    detail.toggle_playback()
    assert len(played) == 1 and detail.play_button.text() == "Stop"
    detail.toggle_playback()
    assert not state["playing"] and detail.play_button.text() == "Play"
