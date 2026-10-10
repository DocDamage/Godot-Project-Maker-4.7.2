"""T15.23: every page looks as its golden picture does, in both themes and both window sizes.

The goldens are in ``tests/gui/goldens`` and are rewritten by
``python -m rpggen.dev update-ui-goldens``. A page that differs leaves its picture and a picture
of the difference in ``tests/gui/goldens/_failed``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from rpggen import dev
from rpggen.core import godot
from rpggen.gui import app as gui_app

FAILED = dev.UI_GOLDENS / "_failed"


def _picture(shift: int = 0, button: str = "#3b82f6") -> QImage:
    """A page in small: a surface, a button and three lines of text, ``shift`` pixels down."""
    image = QImage(320, 200, QImage.Format.Format_RGB888)
    image.fill(QColor("#1c1f26"))
    painter = QPainter(image)
    painter.fillRect(200, 150 + shift, 96, 28, QColor(button))
    painter.setPen(QColor("#e6e8ec"))
    for row in range(3):
        for column in range(0, 150, 6):  # strokes as wide and as far apart as letters
            painter.drawLine(20 + column, 30 + shift + row * 18, 20 + column, 40 + shift + row * 18)
    painter.end()
    return image


def _differs(shown: QImage, golden: QImage) -> bool:
    mean, block, _diff = dev.compare_pictures(shown, golden)
    return mean >= dev.MEAN_LIMIT or block >= dev.BLOCK_LIMIT


def test_the_same_picture_is_no_difference() -> None:
    mean, block, diff = dev.compare_pictures(_picture(), _picture())
    assert (mean, block) == (0.0, 0.0)
    assert diff.size() == _picture().size()


def test_a_moved_button_is_a_difference() -> None:
    assert _differs(_picture(shift=12), _picture())


def test_a_recoloured_button_is_a_difference() -> None:
    assert _differs(_picture(button="#f2706d"), _picture())


def test_softer_edges_are_no_difference() -> None:
    """What another build of the same font does to a picture: every edge a little lighter."""
    golden = _picture()
    shown = golden.copy()
    painter = QPainter(shown)
    painter.setOpacity(0.01)
    painter.fillRect(shown.rect(), Qt.GlobalColor.white)
    painter.end()
    assert not _differs(shown, golden)


def test_another_size_is_a_difference() -> None:
    assert _differs(_picture().scaled(300, 200), _picture())


@pytest.mark.slow
def test_every_page_looks_as_its_golden(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made_with = dev.ui_goldens_font()
    assert made_with, "no goldens: python -m rpggen.dev update-ui-goldens"
    gui_app.create_app()
    original = QApplication.font()
    monkeypatch.setattr(godot, "auto_find_godot", godot.auto_find_godot)  # the renderer's patch
    family = dev.ensure_real_font()
    if family != made_with:
        QApplication.setFont(original)
        pytest.skip(f"the goldens were rendered with {made_with}; this machine has {family}")
    shutil.rmtree(FAILED, ignore_errors=True)
    expected = {path.stem for path in dev.UI_GOLDENS.glob("*.png")}
    seen: set[str] = set()
    problems: list[str] = []
    try:
        for name, shown in dev.ui_golden_pictures(tmp_path):
            seen.add(name)
            golden = QImage(str(dev.UI_GOLDENS / f"{name}.png"))
            if golden.isNull():
                problems.append(f"{name}: no golden")
                continue
            mean, block, diff = dev.compare_pictures(shown, golden)
            if mean >= dev.MEAN_LIMIT or block >= dev.BLOCK_LIMIT:
                FAILED.mkdir(parents=True, exist_ok=True)
                shown.save(str(FAILED / f"{name}.png"))
                diff.save(str(FAILED / f"{name}.diff.png"))
                theme_name, size_name, _number, page = name.split("_", 3)
                problems.append(
                    f"{page} ({theme_name}, {size_name}): {mean:.1%} of the picture differs, "
                    f"{block:.0%} of one block (limits {dev.MEAN_LIMIT:.1%} and "
                    f"{dev.BLOCK_LIMIT:.0%}); see {FAILED / name}.diff.png"
                )
    finally:
        QApplication.setFont(original)
    assert not problems, "\n".join(problems)
    assert seen == expected, f"goldens without a page, or pages without one: {seen ^ expected}"
