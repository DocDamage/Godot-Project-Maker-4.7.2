"""T15.04: the icon set (plain SVG files drawn in a colour of the theme)."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtWidgets import QPushButton

from rpggen.gui import icons, theme

REPO = Path(__file__).resolve().parents[2]
GUI = REPO / "rpggen" / "gui"
FOLDER = GUI / "icons"
FIXED_COLOUR = {"app"}  # the application's own mark, in its own colours (About)

# the ways the code names an icon: icons.icon("x"), icons.pixmap("x"), set_icon(w, "x"),
# icon_only(w, "x"), a themed icon's ``.name = "x"`` and the template's @icon(x, token)
CALLS = (
    re.compile(r"icons\.(?:icon|pixmap)\(\s*\"([a-z0-9-]+)\""),
    re.compile(
        r"(?:set_icon|icon_only)\(\s*[^,()]+(?:\([^()]*\))?,\s*\"([a-z0-9]+(?:-[a-z0-9]+)*)\"\s*[,)]"
    ),
    re.compile(r"\.name = \"([a-z0-9-]+)\" if [^\n]+ else \"([a-z0-9-]+)\""),
    # a table entry ``kind: ("icon", "token")``, as the banners have
    re.compile(r": \(\"([a-z0-9-]+)\", \"(?:accent|warning|danger|success|text_muted)\"\)"),
)


def _names() -> list[str]:
    return sorted(path.stem for path in FOLDER.glob("*.svg"))


def test_every_icon_is_a_well_formed_svg_in_the_current_colour() -> None:
    names = _names()
    assert len(names) >= 40
    for name in names:
        text = (FOLDER / f"{name}.svg").read_text(encoding="utf-8")
        root = ET.fromstring(text)
        assert root.tag.endswith("svg"), name
        if name in FIXED_COLOUR:
            continue
        assert root.attrib["viewBox"] == "0 0 24 24", name
        assert "currentColor" in text, name
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(", text), f"{name} has a fixed colour"


def test_every_icon_the_code_asks_for_exists() -> None:
    asked: set[str] = set()
    for path in GUI.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in CALLS:
            for match in pattern.finditer(text):
                asked.update(group for group in match.groups() if group)
    template = re.sub(r"/[*].*?[*]/", "", theme.template_text(), flags=re.S)  # not its comments
    asked.update(re.findall(r"@icon[(]\s*([a-z0-9-]+)\s*,", template))
    assert len(asked) >= 25, sorted(asked)  # the scan really finds the calls
    missing = sorted(asked - set(_names()))
    assert not missing, missing
    with pytest.raises(KeyError):
        icons.pixmap("no-such-icon")


def test_the_folder_is_what_the_tool_writes() -> None:
    sys.path.insert(0, str(REPO / "tools"))
    try:
        import make_ui_icons
    finally:
        sys.path.pop(0)
    assert make_ui_icons.main(["--check"]) == 0
    assert sorted(make_ui_icons.ICONS | make_ui_icons.FIXED_COLOUR) == _names()
    assert not set(make_ui_icons.ICONS) & set(make_ui_icons.FIXED_COLOUR)


def test_an_icon_has_the_device_pixels_of_the_screen(qtbot) -> None:
    one = icons.pixmap("check", "text", 16, ratio=1.0)
    two = icons.pixmap("check", "text", 16, ratio=2.0)
    assert (one.width(), two.width()) == (16, 32)
    assert two.devicePixelRatio() == 2.0 and two.deviceIndependentSize().width() == 16
    assert icons.pixmap("check", "text", 16, ratio=1.5).width() == 24


def test_an_icon_is_drawn_in_the_token_and_follows_the_theme(qtbot) -> None:
    theme.apply_theme("dark", remember=False)
    try:
        image = icons.pixmap("square", "accent", 16, ratio=1.0).toImage()
        colours = {
            image.pixelColor(x, y).name()
            for x in range(16)
            for y in range(16)
            if image.pixelColor(x, y).alpha() == 255
        }
        assert theme.hex_of("accent") in colours
        button = QPushButton("x")
        qtbot.addWidget(button)
        themed = icons.set_icon(button, "check")
        assert not button.icon().isNull() and button._themed_icon is themed
        assert icons.cached() > 0
        before = icons.pixmap("check", None, 16, ratio=1.0)
        theme.apply_theme("light", remember=False)
        # the pictures of the old theme are gone, and the button was given the new one
        after = icons.pixmap("check", None, 16, ratio=1.0)
        assert after is not before
        assert after.toImage() != before.toImage()
        assert not button.icon().isNull()
    finally:
        theme.apply_theme("dark", remember=False)


def test_the_package_and_the_frozen_build_carry_the_icons_and_the_template() -> None:
    spec = (REPO / "packaging" / "rpggen.spec").read_text(encoding="utf-8")
    assert '"icons"' in spec and "style.qss.in" in spec and ".svg" in spec
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "gui/icons/*.svg" in pyproject and "gui/*.qss.in" in pyproject
