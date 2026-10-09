"""T12.31: role chips, confidence bars, audio and font cards, and playback in the detail panel."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
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


# ------------------------------------------------------------------------ the preview's overlay (T13.03)


def test_overlay_marks_by_usage() -> None:
    from rpggen.gui.widgets.asset_detail import overlay_marks

    # an object: its footprint (the default is the bottom 30%) and its origin
    marks = overlay_marks({"usage": "object", "origin": [8, 30]}, (16, 40))
    assert marks == [("footprint", 0, 28, 16, 12), ("origin", 8, 30, 0, 0)]
    marks = overlay_marks({"usage": "object", "footprint": [2, 20, 12, 10]}, (16, 40))
    assert marks == [("footprint", 2, 20, 12, 10)]
    # a sprite: the frames where the attack hits, and the frame the transport is on
    eff = {
        "usage": "sprite",
        "frame": [16, 16],
        "grid": {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]},
        "animations": {
            "attack": {"frames": [[0, 2], [1, 2], [2, 2]], "fps": 8, "active_frames": [1, 9]}
        },
    }
    assert overlay_marks(eff, (64, 64), "attack", 2) == [
        ("active", 16, 32, 16, 16),
        ("current", 32, 32, 16, 16),
    ]
    assert overlay_marks(eff, (64, 64)) == [], "no animation chosen: only the grid"
    # the other usages have no marks (tiles get their grid from the view itself)
    for usage in ("tiles", "ui", "portrait", "background"):
        assert overlay_marks({"usage": usage, "origin": [1, 1]}, (16, 16)) == []


def test_the_overlay_follows_a_grid_edit_and_a_usage_change_without_reopening(qtbot) -> None:
    from PySide6.QtWidgets import QApplication

    from rpggen.core import catalog
    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers
    from rpggen.gui.pages.audit_page import AuditPage
    from rpggen.gui.state import WizardState

    synth = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
    state = WizardState(pack_sources=[synth / "basic16"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.show()
    page.enter(state)
    page.grid.chips["chipAll"].click()
    QApplication.processEvents()
    tiles = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "tiles")
    page.grid.select_ids([tiles.id])
    detail = page.detail
    assert detail is not None and not detail.anim_box.isVisibleTo(detail)
    lines_before = len(detail.preview.grid_items)
    grid = dict(catalog.effective(tiles)["grid"])
    grid["cell"] = [grid["cell"][0] * 2, grid["cell"][1] * 2]
    assert page.session is not None and page.session.set_override(tiles.id, "grid", grid)
    assert detail.asset_id == tiles.id
    assert 0 < len(detail.preview.grid_items) < lines_before, "fewer, larger cells are drawn"
    # as an object it has a footprint and no grid
    assert page.session.set_override(tiles.id, "usage", "object")
    assert detail.preview.grid_items == []
    assert [m[0] for m in detail.preview.marks][:1] == ["footprint"]


# ------------------------------------------------------------------------ waveforms and loops (T13.17)


def test_an_audio_card_draws_the_decoded_waveform_of_an_ogg(tmp_path: Path) -> None:
    import numpy
    import soundfile

    t = numpy.arange(8000) / 8000
    tone = (0.8 * numpy.sin(2 * numpy.pi * 220 * t)).astype("float32")
    loud = tmp_path / "loud.ogg"
    soundfile.write(str(loud), tone, 8000)
    quiet = tmp_path / "quiet.ogg"
    soundfile.write(str(quiet), tone * 0.05, 8000)
    broken = tmp_path / "broken.ogg"
    broken.write_bytes(b"OggS" + bytes(64))
    cards = {p.name: thumbnails.render_audio_card(p, 1.0) for p in (loud, quiet, broken)}
    assert cards["loud.ogg"] != cards["quiet.ogg"], "the waveform is drawn from the samples"
    assert cards["loud.ogg"] != cards["broken.ogg"]
    # a file that cannot be decoded: the flat bar, and never an error
    from PIL import Image as PilImage

    image = PilImage.open(io.BytesIO(cards["broken.ogg"]))
    row = [image.getpixel((x, round(62 * image.width / 96))) for x in range(image.width)]
    assert sum(1 for px in row if px[:3] == (104, 168, 240)) > image.width // 2, "a flat bar"
    assert thumbnails.CARD_VERSION == 2, "cards cached before the waveforms are drawn again"


def _music(cat):
    return next(a for a in cat.assets if a.path.endswith("overworld_theme.wav"))


def test_the_detail_panel_shows_the_waveform_and_the_loop_row_for_music(qtbot) -> None:
    cat, root = _build("audio_basic")
    detail = _detail(qtbot, cat, root)
    music = _music(cat)
    detail.set_asset(music.id)
    assert detail.waveform.isVisibleTo(detail)
    assert detail.waveform.peaks is not None and len(detail.waveform.peaks) == detail.PEAK_COLUMNS
    assert detail.waveform.duration_ms == 30000
    assert detail.loop_box.isVisibleTo(detail)
    assert detail.waveform.markers
    # no loop points yet: the whole track
    assert (detail.loop_start_spin.value(), detail.loop_end_spin.value()) == (0, 30000)
    assert not detail.loop_clear_button.isEnabled()
    # a sound effect has the waveform but no loop row
    sfx = next(a for a in cat.assets if a.path.endswith("hit.wav"))
    detail.set_asset(sfx.id)
    assert detail.waveform.isVisibleTo(detail) and not detail.loop_box.isVisibleTo(detail)
    assert not detail.waveform.markers
    # a picture has neither
    picture = next(a for a in cat.assets if a.kind == "image")
    detail.set_asset(picture.id)
    assert not detail.waveform.isVisibleTo(detail) and not detail.loop_box.isVisibleTo(detail)


def test_loop_points_are_facets_and_every_change_is_one_undo_step(qtbot) -> None:
    cat, root = _build("audio_basic")
    detail = _detail(qtbot, cat, root)
    session = detail.session
    music = _music(cat)
    detail.set_asset(music.id)

    def audio() -> dict:
        return catalog.effective(session.catalog.asset(music.id))["audio"]

    # typing the numbers
    detail.loop_end_spin.setValue(20000)
    assert (audio()["loop_start_ms"], audio()["loop_end_ms"]) == (0, 20000)
    detail.loop_start_spin.setValue(1500)
    assert (audio()["loop_start_ms"], audio()["loop_end_ms"]) == (1500, 20000)
    assert audio()["type"] == "music" and audio()["loop"] is True, "the other facts stay"
    assert detail.waveform.loop() == (1500, 20000)
    assert detail.loop_clear_button.isEnabled()
    # an end before the start is refused with a note
    detail.loop_end_spin.setValue(1000)
    assert "after the start" in detail.loop_note.text()
    assert audio()["loop_end_ms"] == 20000
    # the catalog with loop points is valid, and they survive a round trip
    from rpggen import schema

    data = session.catalog.to_json()
    schema.validate("catalog", data)
    again = catalog.Catalog.from_json(data)
    assert catalog.effective(again.asset(music.id))["audio"]["loop_start_ms"] == 1500
    # undo, one step per change
    session.undo_stack.undo()
    assert (audio()["loop_start_ms"], audio()["loop_end_ms"]) == (0, 20000)
    assert detail.loop_start_spin.value() == 0
    session.undo_stack.undo()
    assert "loop_start_ms" not in audio() and "loop_end_ms" not in audio()
    assert detail.loop_end_spin.value() == 30000
    # Whole track takes both points away again
    assert detail.set_loop(2000, 9000)
    detail.loop_clear_button.click()
    assert "loop_start_ms" not in audio() and "loop_end_ms" not in audio()
    assert not detail.clear_loop(), "nothing left to clear"
    schema.validate("catalog", session.catalog.to_json())


def test_dragging_a_marker_moves_one_loop_point(qtbot) -> None:
    cat, root = _build("audio_basic")
    detail = _detail(qtbot, cat, root)
    music = _music(cat)
    detail.set_asset(music.id)
    view = detail.waveform
    view.resize(408, 80)  # 400 px of track: 75 ms a pixel
    assert view.ms_at(view.x_of(15000)) == 15000
    assert view.marker_at(view.x_of(0)) == "start" and view.marker_at(view.x_of(30000)) == "end"
    assert view.marker_at(view.x_of(15000)) is None
    y = view.height() // 2
    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(view.x_of(30000), y))
    qtbot.mouseMove(view, QPoint(view.x_of(24000), y))
    assert view.loop() == (0, 24000), "the marker follows the mouse"
    before = detail.session.undo_stack.count()
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(view.x_of(24000), y))
    audio = catalog.effective(detail.session.catalog.asset(music.id))["audio"]
    assert (audio["loop_start_ms"], audio["loop_end_ms"]) == (0, 24000)
    assert detail.session.undo_stack.count() == before + 1, "one step for the whole drag"
    assert detail.loop_end_spin.value() == 24000
    # the markers never cross
    view.drag_to("start", 99999)
    assert view.loop() == (23999, 24000)
    view.drag_to("end", 0)
    assert view.loop() == (23999, 24000)


def test_guess_fills_the_loop_points(qtbot, tmp_path: Path, monkeypatch) -> None:
    cat, root = _build("audio_basic")
    detail = _detail(qtbot, cat, root)
    music = _music(cat)
    detail.set_asset(music.id)
    monkeypatch.setattr(audio_info, "guess_loop", lambda path: (4000, 12000))
    detail.loop_guess_button.click()
    assert detail.loop_points() == (4000, 12000)
    assert (detail.loop_start_spin.value(), detail.loop_end_spin.value()) == (4000, 12000)
    monkeypatch.setattr(audio_info, "guess_loop", lambda path: None)
    assert not detail.guess_loop()
    assert detail.loop_note.text() == "No loop found"
    assert detail.loop_points() == (4000, 12000)
